import json
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from openclaw_api.config import Settings
from openclaw_api.deps import get_current_customer_id, get_db, get_redis
from openclaw_api.main import app
from openclaw_api.models import (
    Base,
    Box,
    BoxStatus,
    Customer,
    CustomerConnection,
    OperatorJob,
    Subscription,
    SubscriptionStatus,
    Tier,
    UsageMonthly,
)

TEST_CUSTOMER_ID = "00000000-0000-0000-0000-000000000001"
TEST_BOX_ID = "00000000-0000-0000-0000-000000000010"
TEST_SUB_ID = "00000000-0000-0000-0000-000000000020"

engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.close()


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


mock_redis = AsyncMock(spec=aioredis.Redis)


async def override_get_redis() -> aioredis.Redis:
    mock_redis.reset_mock()
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
