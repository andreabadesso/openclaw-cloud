"""Async Redis client for OpenClaw Cloud services."""

from __future__ import annotations

import os

import redis.asyncio as redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_pool: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return a shared async Redis client (lazy-initialized)."""
    global _pool
    if _pool is None:
        _pool = redis.from_url(REDIS_URL, decode_responses=True)
    return _pool
