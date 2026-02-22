from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class BoxResponse(BaseModel):
    id: str
    status: str
    k8s_namespace: str
    model: str
    thinking_level: str
    language: str
    niche: str | None = None
    telegram_user_ids: list[int]
    created_at: datetime
    activated_at: datetime | None = None

    model_config = {"from_attributes": True}


class UsageResponse(BaseModel):
    tokens_used: int
    tokens_limit: int
    pct_used: float
    period_start: datetime
    period_end: datetime


class ProvisionRequest(BaseModel):
    telegram_bot_token: str
    telegram_user_id: int
    tier: str = Field(pattern=r"^(starter|pro|team)$")
    model: str = "kimi-coding/k2p5"
    thinking_level: str = "medium"
    language: str = "en"
    customer_email: str
    niche: str | None = None


class UpdateBoxRequest(BaseModel):
    telegram_user_ids: list[int] | None = None
    model: str | None = None
    thinking_level: str | None = None
    language: str | None = None


class BoxListItem(BaseModel):
    id: str
    customer_id: str
    status: str
    k8s_namespace: str
    model: str
    thinking_level: str
    language: str
    niche: str | None = None
    telegram_user_ids: list[int]
    created_at: datetime
    activated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BoxListResponse(BaseModel):
    boxes: list[BoxListItem]


class CustomerResponse(BaseModel):
    id: str
    email: str
    stripe_customer_id: str | None = None
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    customers: list[CustomerResponse]


class ProvisionResponse(BaseModel):
    customer_id: str
    box_id: str
    job_id: str


class JobEnqueuedResponse(BaseModel):
    job_id: str
    box_id: str


class ConnectionResponse(BaseModel):
    id: str
    provider: str
    status: str
    created_at: datetime | None = None


class ConnectionListResponse(BaseModel):
    connections: list[ConnectionResponse]


class ConnectSessionResponse(BaseModel):
    session_token: str
    connect_url: str


class ResizeRequest(BaseModel):
    new_tier: str = Field(pattern=r"^(starter|pro|team)$")


class BillingPortalResponse(BaseModel):
    url: str


class ConnectLinkRequest(BaseModel):
    provider: str


class ConnectLinkResponse(BaseModel):
    url: str


class TokenUsageSummary(BaseModel):
    tokens_used: int
    tokens_limit: int
    period_start: datetime | None = None
    period_end: datetime | None = None


class BrowserSessionsSummary(BaseModel):
    session_count: int
    total_duration_ms: int


class PodMetricsPoint(BaseModel):
    cpu_millicores: int
    memory_bytes: int
    ts: datetime


class AnalyticsResponse(BaseModel):
    token_usage: TokenUsageSummary
    browser_sessions: BrowserSessionsSummary
    pod_metrics_latest: PodMetricsPoint | None = None
    pod_metrics_series: list[PodMetricsPoint]
    tier: str
