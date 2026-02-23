from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openclaw_api.config import settings
from openclaw_api.database import async_session

_redis_pool: aioredis.Redis | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None


async def get_current_customer_id(
    request: Request,
    x_customer_id: str | None = Header(None),
) -> str:
    """Extract customer_id from JWT Bearer token, with debug fallback to X-Customer-Id header."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ")
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            return payload["sub"]
        except (JWTError, KeyError):
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    if settings.debug and x_customer_id:
        return x_customer_id

    raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")


async def get_active_box_or_none(customer_id: str, db: AsyncSession):
    from openclaw_api.models import Box, BoxStatus

    result = await db.execute(
        select(Box)
        .where(Box.customer_id == customer_id)
        .where(Box.status == BoxStatus.active)
        .limit(1)
    )
    return result.scalar_one_or_none()
