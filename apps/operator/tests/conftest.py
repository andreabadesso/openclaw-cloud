"""Shared fixtures for operator tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    """Async DB session mock."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    # Make fetchall work on execute result
    result = MagicMock()
    result.fetchall.return_value = []
    db.execute.return_value = result
    return db


@pytest.fixture
def mock_core_v1():
    """Mock CoreV1Api."""
    return MagicMock()


@pytest.fixture
def mock_apps_v1():
    """Mock AppsV1Api."""
    return MagicMock()


@pytest.fixture
def mock_networking_v1():
    """Mock NetworkingV1Api."""
    return MagicMock()


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    r = MagicMock()
    lock = MagicMock()
    lock.acquire.return_value = True
    lock.release.return_value = None
    r.lock.return_value = lock
    r.blpop.return_value = None
    return r


@pytest.fixture(autouse=True)
def _patch_settings():
    """Ensure settings have sensible test defaults."""
    with patch("openclaw_operator.config.settings") as s:
        s.redis_url = "redis://localhost:6379/0"
        s.database_url = "postgresql+asyncpg://localhost/test"
        s.token_proxy_url = "http://token-proxy:8080"
        s.internal_api_key = "test-internal-key"
        s.openclaw_image = "openclaw-gateway:test"
        s.job_queue = "operator:jobs"
        s.health_port = 8081
        s.pod_ready_timeout = 60
        s.nango_server_url = "http://nango-server:8080"
        s.nango_secret_key = "test-nango-secret"
        s.agent_api_secret = "test-agent-secret"
        s.api_url = "http://api:8000"
        s.web_url = "http://localhost:3000"
        yield s
