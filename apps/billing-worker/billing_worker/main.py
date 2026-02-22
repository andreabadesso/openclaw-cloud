import logging

import redis.asyncio as aioredis
import stripe
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .handlers import EVENT_HANDLERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("billing-worker")

app = FastAPI(title="OpenClaw Billing Worker", docs_url=None, redoc_url=None)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis: aioredis.Redis | None = None


@app.on_event("startup")
async def startup() -> None:
    global _engine, _session_factory, _redis
    stripe.api_key = settings.stripe_secret_key
    _engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=2)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    logger.info("Billing worker started")


@app.on_event("shutdown")
async def shutdown() -> None:
    global _engine, _redis
    if _redis:
        await _redis.aclose()
    if _engine:
        await _engine.dispose()


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="stripe-signature"),
) -> dict:
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload.decode("utf-8"),
            stripe_signature,
            settings.stripe_webhook_secret,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    handler = EVENT_HANDLERS.get(event.type)
    if handler is None:
        logger.debug("Unhandled event type: %s", event.type)
        return {"status": "ignored"}

    assert _session_factory is not None
    assert _redis is not None

    async with _session_factory() as db:
        try:
            await handler(event, db, _redis)
        except Exception:
            logger.exception("Error handling event %s (id=%s)", event.type, event.id)
            raise HTTPException(status_code=500, detail="Internal error")

    return {"status": "ok"}


def main() -> None:
    uvicorn.run(
        "billing_worker.main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
