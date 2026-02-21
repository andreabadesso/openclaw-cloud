from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


# Upstream Kimi API
KIMI_API_KEY: str = _require("KIMI_API_KEY")
KIMI_BASE_URL: str = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")

# Postgres
DATABASE_URL: str = _require("DATABASE_URL")  # asyncpg:// or postgresql+asyncpg://

# Redis
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Internal API shared secret
INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")

# Rate limiting
RATE_LIMIT_RPS: int = int(os.getenv("RATE_LIMIT_RPS", "10"))

# Usage consumer tuning
USAGE_FLUSH_INTERVAL_S: float = float(os.getenv("USAGE_FLUSH_INTERVAL_S", "5"))
USAGE_FLUSH_BATCH_SIZE: int = int(os.getenv("USAGE_FLUSH_BATCH_SIZE", "100"))
