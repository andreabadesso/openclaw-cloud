import json
import sqlite3
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, StaticPool, String, Text, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.types import TypeDecorator

from openclaw_api.config import Settings
from openclaw_api.deps import get_current_customer_id, get_db, get_redis
from openclaw_api.main import app
from openclaw_api.models import (
    Base,
    Box,
    BoxStatus,
    Bundle,
    Customer,
    CustomerConnection,
    OperatorJob,
    Subscription,
    SubscriptionStatus,
    Tier,
    UsageMonthly,
)


# --- SQLite compatibility ---
# PostgreSQL-specific types must be compiled as SQLite-compatible equivalents.

@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


class JSONArray(TypeDecorator):
    """Store Python lists as JSON strings in SQLite (replaces PG ARRAY)."""
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        if isinstance(value, str):
            return json.loads(value)
        return value


# Walk all model columns and swap PG-specific types for SQLite-compatible ones.
for table in Base.metadata.tables.values():
    for col in table.columns:
        if isinstance(col.type, JSONB):
            col.type = JSON()
            # Fix PG-specific server_defaults: "'{}'" → "{}", "'[]'" → "[]"
            if col.server_default is not None:
                default_text = str(col.server_default.arg)
                if default_text.startswith("'") and default_text.endswith("'"):
                    col.server_default.arg = default_text[1:-1]
        elif isinstance(col.type, ARRAY):
            col.type = JSONArray()
            if col.server_default is not None:
                default_text = str(col.server_default.arg)
                # PG array default "{}" → JSON "[]"
                if default_text == "{}":
                    col.server_default.arg = "[]"

# Patch UUID primary key columns: replace server_default with Python-side default
# so SQLite doesn't need INSERT...RETURNING to populate primary keys.
from sqlalchemy.schema import ColumnDefault

_uuid_default = ColumnDefault(lambda: str(uuid.uuid4()))

for table in Base.metadata.tables.values():
    for col in table.columns:
        if col.primary_key and isinstance(col.type, PG_UUID):
            col.server_default = None
            col.default = _uuid_default

# SQLite type adapters
sqlite3.register_adapter(list, lambda val: json.dumps(val))
sqlite3.register_adapter(dict, lambda val: json.dumps(val))


# --- Test constants ---

TEST_CUSTOMER_ID = "00000000-0000-0000-0000-000000000001"
TEST_BOX_ID = "00000000-0000-0000-0000-000000000010"
TEST_SUB_ID = "00000000-0000-0000-0000-000000000020"
TEST_BUNDLE_ID = "00000000-0000-0000-0000-000000000030"

engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_compat(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.close()
    dbapi_conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))
    dbapi_conn.create_function("now", 0, lambda: datetime.now(timezone.utc).isoformat())


test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session() as session:
        yield session


mock_redis = AsyncMock()
mock_redis.rpush = AsyncMock()


@pytest_asyncio.fixture(autouse=True)
async def _reset_redis():
    """Reset the mock redis before each test so call counts are isolated."""
    mock_redis.reset_mock()
    mock_redis.rpush = AsyncMock()
    yield


async def override_get_redis() -> aioredis.Redis:
    return mock_redis


async def override_get_customer_id() -> str:
    return TEST_CUSTOMER_ID


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_redis] = override_get_redis
app.dependency_overrides[get_current_customer_id] = override_get_customer_id


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db():
    async with test_session() as session:
        yield session


@pytest_asyncio.fixture
async def seed_customer(db: AsyncSession):
    customer = Customer(id=TEST_CUSTOMER_ID, email="test@example.com")
    db.add(customer)
    await db.commit()
    return customer


@pytest_asyncio.fixture
async def seed_subscription(db: AsyncSession, seed_customer):
    now = datetime.now(timezone.utc)
    sub = Subscription(
        id=TEST_SUB_ID,
        customer_id=TEST_CUSTOMER_ID,
        tier=Tier.starter,
        status=SubscriptionStatus.active,
        tokens_limit=1_000_000,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db.add(sub)
    await db.commit()
    return sub


@pytest_asyncio.fixture
async def seed_box(db: AsyncSession, seed_subscription):
    box = Box(
        id=TEST_BOX_ID,
        customer_id=TEST_CUSTOMER_ID,
        subscription_id=TEST_SUB_ID,
        k8s_namespace=f"customer-{TEST_CUSTOMER_ID}",
        telegram_user_ids=[12345],
        status=BoxStatus.active,
    )
    db.add(box)
    await db.commit()
    return box


@pytest_asyncio.fixture
async def seed_usage(db: AsyncSession, seed_customer):
    now = datetime.now(timezone.utc)
    usage = UsageMonthly(
        customer_id=TEST_CUSTOMER_ID,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=29),
        tokens_used=500_000,
        tokens_limit=1_000_000,
    )
    db.add(usage)
    await db.commit()
    return usage


@pytest_asyncio.fixture
async def seed_bundle(db: AsyncSession):
    bundle = Bundle(
        id=TEST_BUNDLE_ID,
        slug="general-assistant",
        name="General Assistant",
        description="A versatile AI assistant",
        icon="🤖",
        color="#10B981",
        status="published",
        prompts={"system": "You are a helpful assistant."},
        default_model="kimi-coding/k2p5",
        default_thinking_level="medium",
        default_language="en",
        providers=[{"provider": "github", "required": False}],
        mcp_servers={},
        skills=["web-search"],
        sort_order=0,
    )
    db.add(bundle)
    await db.commit()
    return bundle


@pytest_asyncio.fixture
async def seed_connection(db: AsyncSession, seed_customer):
    conn = CustomerConnection(
        customer_id=TEST_CUSTOMER_ID,
        provider="github",
        nango_connection_id=f"{TEST_CUSTOMER_ID}_github",
        status="active",
    )
    db.add(conn)
    await db.commit()
    return conn
