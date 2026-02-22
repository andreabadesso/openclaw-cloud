import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_db():
    """Mock async DB session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest_asyncio.fixture
async def mock_redis():
    """Mock async Redis client."""
    r = AsyncMock()
    r.rpush = AsyncMock()
    return r


def make_stripe_event(event_type: str, data_object: dict, previous_attributes: dict | None = None) -> MagicMock:
    """Create a mock Stripe event."""
    event = MagicMock()
    event.type = event_type
    event.id = "evt_test_123"

    obj = SimpleNamespace(**data_object)
    # Support dict-style metadata access
    if "metadata" in data_object:
        obj.metadata = data_object["metadata"]

    event.data = MagicMock()
    event.data.object = obj

    if previous_attributes:
        event.data.get = MagicMock(return_value=previous_attributes)
    else:
        event.data.get = MagicMock(return_value={})

    return event


def make_db_row(*values):
    """Create a mock DB result row."""
    mock_result = MagicMock()
    row = MagicMock()
    row.__iter__ = MagicMock(return_value=iter(values))
    row.__getitem__ = MagicMock(side_effect=lambda i: values[i])
    mock_result.fetchone = MagicMock(return_value=row)
    mock_result.scalar = MagicMock(return_value=values[0] if values else None)
    return mock_result


def make_empty_result():
    """Create a mock DB result with no rows."""
    mock_result = MagicMock()
    mock_result.fetchone = MagicMock(return_value=None)
    mock_result.scalar = MagicMock(return_value=None)
    return mock_result
