import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, BIGINT, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


# --- Enums ---


class SubscriptionStatus(str, enum.Enum):
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    suspended = "suspended"
    cancelled = "cancelled"


class Tier(str, enum.Enum):
    starter = "starter"
    pro = "pro"
    team = "team"


class BoxStatus(str, enum.Enum):
    pending = "pending"
    provisioning = "provisioning"
    active = "active"
    updating = "updating"
    suspended = "suspended"
    unhealthy = "unhealthy"
    destroying = "destroying"
    destroyed = "destroyed"


class OnboardingState(str, enum.Enum):
    new = "new"
    greeting = "greeting"
    gathering_use_case = "gathering_use_case"
    gathering_telegram = "gathering_telegram"
    gathering_preferences = "gathering_preferences"
    recommending_tier = "recommending_tier"
    awaiting_payment = "awaiting_payment"
    provisioning = "provisioning"
    complete = "complete"
    failed = "failed"
    abandoned = "abandoned"


class JobType(str, enum.Enum):
    provision = "provision"
    update = "update"
    destroy = "destroy"
    suspend = "suspend"
    reactivate = "reactivate"
    resize = "resize"
    health_check = "health_check"
    update_connections = "update_connections"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    complete = "complete"
    failed = "failed"


# --- Models ---


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="customer")
    boxes: Mapped[list["Box"]] = relationship(back_populates="customer")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text, unique=True)
    stripe_price_id: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[Tier] = mapped_column(Enum(Tier, name="tier", create_constraint=False, native_enum=False), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status", create_constraint=False, native_enum=False),
        nullable=False,
        server_default="active",
    )
    tokens_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="subscriptions")

    __table_args__ = (
        Index("ix_subscriptions_customer_id", "customer_id"),
        Index("ix_subscriptions_stripe_subscription_id", "stripe_subscription_id"),
    )


class Box(Base):
    __tablename__ = "boxes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    subscription_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("subscriptions.id"), nullable=False)
    k8s_namespace: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    telegram_user_ids: Mapped[list[int]] = mapped_column(ARRAY(BIGINT), nullable=False, server_default="{}")
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="en")
    model: Mapped[str] = mapped_column(Text, nullable=False, server_default="kimi-coding/k2p5")
    thinking_level: Mapped[str] = mapped_column(Text, nullable=False, server_default="medium")
    status: Mapped[BoxStatus] = mapped_column(
        Enum(BoxStatus, name="box_status", create_constraint=False, native_enum=False),
        nullable=False,
        server_default="pending",
    )
    health_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    customer: Mapped["Customer"] = relationship(back_populates="boxes")

    __table_args__ = (
        Index("ix_boxes_customer_id", "customer_id"),
        Index("ix_boxes_status", "status", postgresql_where="status != 'destroyed'"),
    )


class ProxyToken(Base):
    __tablename__ = "proxy_tokens"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    box_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("boxes.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_proxy_tokens_token_hash_active", "token_hash", postgresql_where="revoked_at IS NULL"),
        Index("ix_proxy_tokens_customer_id", "customer_id"),
    )


class UsageMonthly(Base):
    __tablename__ = "usage_monthly"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tokens_used: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    tokens_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("customer_id", "period_start"),
        Index("ix_usage_monthly_customer_period", "customer_id", "period_start"),
    )


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    box_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("boxes.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_usage_events_customer_timestamp", "customer_id", "timestamp"),)


class OnboardingSession(Base):
    __tablename__ = "onboarding_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    customer_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("customers.id"))
    session_token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    state: Mapped[OnboardingState] = mapped_column(
        Enum(OnboardingState, name="onboarding_state", create_constraint=False, native_enum=False),
        nullable=False,
        server_default="new",
    )
    messages: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="'[]'")
    derived_config: Mapped[dict | None] = mapped_column(JSONB)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    detected_language: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_onboarding_sessions_session_token", "session_token"),
        Index("ix_onboarding_sessions_expires_at", "expires_at", postgresql_where="state NOT IN ('complete', 'failed')"),
    )


class CustomerConnection(Base):
    __tablename__ = "customer_connections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    nango_connection_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_customer_connections_customer_id", "customer_id"),
        UniqueConstraint("customer_id", "provider", name="uq_customer_connections_customer_provider"),
    )


class OperatorJob(Base):
    __tablename__ = "operator_jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    box_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("boxes.id"))
    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, name="job_type", create_constraint=False, native_enum=False), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", create_constraint=False, native_enum=False),
        nullable=False,
        server_default="queued",
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="'{}'")
    error_log: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_operator_jobs_customer_created", "customer_id", "created_at"),
        Index("ix_operator_jobs_status_active", "status", postgresql_where="status IN ('queued', 'running')"),
    )
