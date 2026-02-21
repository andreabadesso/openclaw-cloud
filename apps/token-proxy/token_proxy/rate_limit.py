from __future__ import annotations

import time

from redis.asyncio import Redis

from token_proxy.config import settings

RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local refill_rate = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last')
local tokens = tonumber(bucket[1])
local last = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last = now
end

local elapsed = math.max(0, now - last)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens < 1 then
    return 0
end

tokens = tokens - 1
redis.call('HMSET', key, 'tokens', tokens, 'last', now)
redis.call('EXPIRE', key, 10)
return 1
"""


async def check_rate_limit(customer_id: str, redis: Redis) -> bool:
    """Token bucket rate limiter. Returns True if request is allowed."""
    key = f"ratelimit:{customer_id}"
    now = time.time()

    result = await redis.eval(
        RATE_LIMIT_SCRIPT,
        1,
        key,
        settings.rate_limit_rps,  # capacity
        now,
        settings.rate_limit_rps,  # refill_rate = capacity per second
    )
    return bool(result)
