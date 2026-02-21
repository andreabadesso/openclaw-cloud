from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

LIMIT_CACHE_PREFIX = "limit:"
LIMIT_CACHE_TTL = 60  # 60 seconds


@dataclass(frozen=True)
class LimitResult:
    allowed: bool
    warning: bool
    used: int
    limit: int
    tier: str


async def check_limits(
    customer_id: str,
    redis: Redis,
    db: AsyncSession,
) -> LimitResult:
    """Check token usage limits for a customer. Returns LimitResult."""
    cache_key = f"{LIMIT_CACHE_PREFIX}{customer_id}"

    # Try Redis cache
    cached = await redis.get(cache_key)
    if cached is not None:
        data = json.loads(cached)
        used, limit, tier = data["used"], data["limit"], data["tier"]
    else:
        # Cache miss — query DB
        result = await db.execute(
            text(
                "SELECT um.tokens_used, um.tokens_limit, s.tier "
                "FROM usage_monthly um "
                "JOIN subscriptions s ON s.customer_id = um.customer_id "
                "WHERE um.customer_id = :cid "
                "  AND um.period_start <= now() "
                "  AND um.period_end > now() "
                "  AND s.status = 'active'"
            ),
            {"cid": customer_id},
        )
        row = result.fetchone()

        if row is None:
            # No active subscription/usage record — block by default
            return LimitResult(allowed=False, warning=False, used=0, limit=0, tier="unknown")

        used, limit, tier = int(row[0]), int(row[1]), str(row[2])

        # Populate cache
        await redis.set(
            cache_key,
            json.dumps({"used": used, "limit": limit, "tier": tier}),
            ex=LIMIT_CACHE_TTL,
        )

    allowed = used < limit
    warning = used >= int(limit * 0.9)

    return LimitResult(allowed=allowed, warning=warning, used=used, limit=limit, tier=tier)
