"""Async database engine, session factory, and ORM models for OpenClaw Cloud."""

from __future__ import annotations

import enum
import os
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, BIGINT, JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ---------------------------------------------------------------------------
# Engine & session
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://localhost/openclaw_cloud"
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session() as session:
        yield session


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Python enums (mirror Postgres enums)
# ---------------------------------------------------------------------------


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class Tier(str, enum.Enum):
    STARTER = "starter"
    PRO = "pro"
    TEAM = "team"


class BoxStatus(str, enum.Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    UPDATING = "updating"
    SUSPENDED = "suspended"
    UNHEALTHY = "unhealthy"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"


class OnboardingState(str, enum.Enum):
    NEW = "new"
    GREETING = "greeting"
    GATHERING_USE_CASE = "gathering_use_case"
    GATHERING_TELEGRAM = "gathering_telegram"
    GATHERING_PREFERENCES = "gathering_preferences"
    RECOMMENDING_TIER = "recommending_tier"
    AWAITING_PAYMENT = "awaiting_payment"
    PROVISIONING = "provisioning"
    COMPLETE = "complete"
    FAILED = "failed"
    ABANDONED = "abandoned"


class JobType(str, enum.Enum):
    PROVISION = "provision"
    UPDATE = "update"
    DESTROY = "destroy"
    SUSPEND = "suspend"
    REACTIVATE = "reactivate"
    RESIZE = "resize"
    HEALTH_CHECK = "health_check"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="customer")
    boxes: Mapped[list["Box"]] = relationship(back_populates="customer")
    proxy_tokens: Mapped[list["ProxyToken"]] = relationship(back_populates="customer")
    onboarding_sessions: Mapped[list["OnboardingSession"]] = relationship(
        back_populates="customer"
    )
    operator_jobs: Mapped[list["OperatorJob"]] = relationship(back_populates="customer")

    __table_args__ = (
        CheckConstraint(r"email ~* '^[^@]+@[^@]+\.[^@]+$'", name="email_format"),
        Index("idx_customers_stripe_customer_id", "stripe_customer_id"),
        Index("idx_customers_email_active", "email", postgresql_where="deleted_at IS NULL"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text, unique=True)
    stripe_price_id: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[Tier] = mapped_column(
        Enum(Tier, name="tier", create_type=False), nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status", create_type=False),
        nullable=False,
        server_default="active",
    )
    tokens_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    customer: Mapped["Customer"] = relationship(back_populates="subscriptions")
    boxes: Mapped[list["Box"]] = relationship(back_populates="subscription")

    __table_args__ = (
        Index("idx_subscriptions_customer_id", "customer_id"),
        Index("idx_subscriptions_stripe_subscription_id", "stripe_subscription_id"),
    )


class Box(Base):
    __tablename__ = "boxes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False
    )
    k8s_namespace: Mapped[str] = mapped_column(Text, unique=True, nullable=False)

    # OpenClaw config
    telegram_user_ids: Mapped[list[int]] = mapped_column(
        ARRAY(BIGINT), nullable=False, server_default="{}"
    )
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="en")
    model: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="kimi-coding/k2p5"
    )
    thinking_level: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="medium"
    )

    # State
    status: Mapped[BoxStatus] = mapped_column(
        Enum(BoxStatus, name="box_status", create_type=False),
        nullable=False,
        server_default="pending",
    )
    health_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    customer: Mapped["Customer"] = relationship(back_populates="boxes")
    subscription: Mapped["Subscription"] = relationship(back_populates="boxes")
    proxy_tokens: Mapped[list["ProxyToken"]] = relationship(back_populates="box")

    __table_args__ = (
        Index("idx_boxes_customer_id", "customer_id"),
        Index(
            "idx_boxes_status_active",
            "status",
            postgresql_where="status NOT IN ('destroyed')",
        ),
    )


class ProxyToken(Base):
    __tablename__ = "proxy_tokens"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    box_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("boxes.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    customer: Mapped["Customer"] = relationship(back_populates="proxy_tokens")
    box: Mapped["Box"] = relationship(back_populates="proxy_tokens")

    __table_args__ = (
        Index(
            "idx_proxy_tokens_hash_active",
            "token_hash",
            postgresql_where="revoked_at IS NULL",
        ),
        Index("idx_proxy_tokens_customer_id", "customer_id"),
    )


class UsageMonthly(Base):
    __tablename__ = "usage_monthly"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    tokens_used: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    tokens_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("customer_id", "period_start"),
        Index("idx_usage_monthly_customer_period", "customer_id", "period_start"),
    )


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    box_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("boxes.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        Computed("prompt_tokens + completion_tokens", persisted=True),
    )
    request_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_usage_events_customer_timestamp", "customer_id", "timestamp"),
    )


class OnboardingSession(Base):
    __tablename__ = "onboarding_sessions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    customer_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id")
    )
    session_token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    state: Mapped[OnboardingState] = mapped_column(
        Enum(OnboardingState, name="onboarding_state", create_type=False),
        nullable=False,
        server_default="new",
    )
    messages: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default="'[]'")
    derived_config: Mapped[Any] = mapped_column(JSONB)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    detected_language: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now() + interval '24 hours'",
    )

    customer: Mapped["Customer | None"] = relationship(
        back_populates="onboarding_sessions"
    )

    __table_args__ = (
        Index("idx_onboarding_sessions_token", "session_token"),
        Index(
            "idx_onboarding_sessions_expires",
            "expires_at",
            postgresql_where="state NOT IN ('complete', 'failed')",
        ),
    )


class OperatorJob(Base):
    __tablename__ = "operator_jobs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    box_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("boxes.id")
    )
    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, name="job_type", create_type=False), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", create_type=False),
        nullable=False,
        server_default="queued",
    )
    payload: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default="'{}'")
    error_log: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    customer: Mapped["Customer"] = relationship(back_populates="operator_jobs")

    __table_args__ = (
        Index("idx_operator_jobs_customer_created", "customer_id", "created_at"),
        Index(
            "idx_operator_jobs_status_active",
            "status",
            postgresql_where="status IN ('queued', 'running')",
        ),
    )
