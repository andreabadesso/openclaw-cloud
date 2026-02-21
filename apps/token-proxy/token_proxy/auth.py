from __future__ import annotations

import json
import logging

import bcrypt
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

TOKEN_CACHE_PREFIX = "proxy_token:"
TOKEN_CACHE_TTL = 300  # 5 minutes


async def authenticate_token(
    token: str,
    redis: Redis,
    db: AsyncSession,
) -> str | None:
    """Validate a proxy token and return the customer_id, or None if invalid."""
    cache_key = f"{TOKEN_CACHE_PREFIX}{token}"

    # Check Redis cache first
    cached = await redis.get(cache_key)
    if cached is not None:
        data = json.loads(cached)
        return data["customer_id"]

    # Cache miss — query Postgres
    result = await db.execute(
        text(
            "SELECT id, customer_id, token_hash FROM proxy_tokens "
            "WHERE revoked_at IS NULL"
        )
    )
    rows = result.fetchall()

    # Constant-time bcrypt comparison against all active tokens
    for row in rows:
        token_id, customer_id, token_hash = row
        if bcrypt.checkpw(token.encode(), token_hash.encode()):
            # Cache the mapping
            await redis.set(
                cache_key,
                json.dumps({"customer_id": str(customer_id), "token_id": str(token_id)}),
                ex=TOKEN_CACHE_TTL,
            )
            return str(customer_id)

    return None


async def get_token_info(
    token: str,
    redis: Redis,
) -> dict | None:
    """Get cached token info (customer_id, token_id) without DB fallback."""
    cache_key = f"{TOKEN_CACHE_PREFIX}{token}"
    cached = await redis.get(cache_key)
    if cached is not None:
        return json.loads(cached)
    return None
