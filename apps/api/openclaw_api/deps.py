from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException
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
    x_customer_id: str | None = Header(None),
) -> str:
    """Placeholder auth dependency. Will be replaced with JWT validation tomorrow."""
    if not x_customer_id:
        raise HTTPException(status_code=401, detail="Missing X-Customer-Id header")
    return x_customer_id


async def get_active_box_or_none(customer_id: str, db: AsyncSession):
    from openclaw_api.models import Box, BoxStatus

    result = await db.execute(
        select(Box)
        .where(Box.customer_id == customer_id)
        .where(Box.status == BoxStatus.active)
        .limit(1)
    )
    return result.scalar_one_or_none()
