from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from token_proxy.config import settings
from token_proxy.auth import authenticate_token
from token_proxy.internal import router as internal_router
from token_proxy.limits import check_limits
from token_proxy.proxy import forward_request
from token_proxy.rate_limit import check_rate_limit
from token_proxy.usage import push_usage_event, start_usage_consumer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    engine = create_async_engine(settings.database_url, pool_size=10, max_overflow=5)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.redis = redis
    app.state.http_client = http_client

    # Start background usage consumer
    consumer_task = asyncio.create_task(start_usage_consumer(redis, session_factory))

    yield

    # Shutdown
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

    await http_client.aclose()
    await redis.aclose()
    await engine.dispose()


app = FastAPI(title="OpenClaw Token Proxy", lifespan=lifespan)
app.include_router(internal_router)


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    """Provide a DB session per request."""
    if request.url.path == "/health":
        return await call_next(request)

    async with app.state.session_factory() as session:
        request.state.db = session
        response = await call_next(request)
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    redis: aioredis.Redis = request.app.state.redis
    db: AsyncSession = request.state.db
    client: httpx.AsyncClient = request.app.state.http_client

    # 1. Extract Bearer token
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"error": {"message": "Missing or invalid Authorization header", "type": "auth_error"}},
        )
    token = auth_header[7:]

    # 2. Authenticate
    customer_id = await authenticate_token(token, redis, db)
    if customer_id is None:
        return JSONResponse(
            status_code=401,
            content={"error": {"message": "Invalid proxy token", "type": "auth_error"}},
        )

    # 3. Rate limit
    if not await check_rate_limit(customer_id, redis):
        return JSONResponse(
            status_code=429,
            content={"error": {"message": "Rate limit exceeded (10 req/s)", "type": "rate_limit_error"}},
            headers={"Retry-After": "1"},
        )

    # 4. Check limits
    limit_result = await check_limits(customer_id, redis, db)
    if not limit_result.allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": "Monthly token limit exceeded. Upgrade at app.openclaw.cloud/billing.",
                    "type": "monthly_limit_exceeded",
                    "used": limit_result.used,
                    "limit": limit_result.limit,
                }
            },
        )

    # 5. Forward to upstream
    try:
        result = await forward_request(request, client)
    except httpx.HTTPError as exc:
        logger.error("Upstream error: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"error": {"message": "Upstream API error", "type": "upstream_error"}},
        )

    # 6. Build response with optional warning header
    response = result.response

    if isinstance(response, StreamingResponse):
        # For streaming, add warning header if applicable
        if limit_result.warning:
            response.headers["X-Token-Warning"] = "90%"

        # Schedule usage recording after stream completes
        # Usage is extracted during streaming — record it via a background task
        body_bytes = await request.body()
        body_json = json.loads(body_bytes)

        async def _record_after_stream():
            # Wait a bit for the stream to complete and usage to be populated
            await asyncio.sleep(0.5)
            if result.usage.total_tokens > 0:
                await push_usage_event(
                    redis=redis,
                    customer_id=customer_id,
                    box_id=None,
                    model=result.usage.model or body_json.get("model", "unknown"),
                    prompt_tokens=result.usage.prompt_tokens,
                    completion_tokens=result.usage.completion_tokens,
                    request_id=result.usage.request_id,
                )

        asyncio.create_task(_record_after_stream())
        return response

    else:
        # Non-streaming: httpx.Response object
        resp_headers = {}
        content_type = response.headers.get("content-type", "application/json")
        if limit_result.warning:
            resp_headers["X-Token-Warning"] = "90%"

        # Record usage
        if result.usage.total_tokens > 0:
            body_bytes = await request.body()
            body_json = json.loads(body_bytes)
            asyncio.create_task(
                push_usage_event(
                    redis=redis,
                    customer_id=customer_id,
                    box_id=None,
                    model=result.usage.model or body_json.get("model", "unknown"),
                    prompt_tokens=result.usage.prompt_tokens,
                    completion_tokens=result.usage.completion_tokens,
                    request_id=result.usage.request_id,
                )
            )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=resp_headers,
            media_type=content_type,
        )
