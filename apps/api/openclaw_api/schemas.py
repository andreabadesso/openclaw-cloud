from datetime import datetime

from pydantic import BaseModel, Field


class SetupRequest(BaseModel):
    telegram_bot_token: str
    telegram_user_id: int
    tier: str = Field(pattern=r"^(starter|pro|team)$")
    bundle_id: str
    model: str | None = None
    thinking_level: str | None = None
    language: str | None = None


class MeResponse(BaseModel):
    id: str
    email: str
    name: str | None = None
    avatar_url: str | None = None
    has_box: bool


class BoxResponse(BaseModel):
    id: str
    status: str
    k8s_namespace: str
    model: str
    thinking_level: str
    language: str
    niche: str | None = None
    bundle_id: str | None = None
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
    customer_email: str
    bundle_id: str
    model: str | None = None
    thinking_level: str | None = None
    language: str | None = None


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
    bundle_id: str | None = None
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


# --- Bundle schemas ---


class BundleProvider(BaseModel):
    provider: str
    required: bool = False


class BundleResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    icon: str
    color: str
    status: str
    prompts: dict
    default_model: str
    default_thinking_level: str
    default_language: str
    providers: list[BundleProvider]
    mcp_servers: dict
    skills: list[str]
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BundleListItem(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    icon: str
    color: str
    providers: list[BundleProvider]
    skills: list[str]
    sort_order: int

    model_config = {"from_attributes": True}


class BundleListResponse(BaseModel):
    bundles: list[BundleListItem]


class CreateBundleRequest(BaseModel):
    slug: str
    name: str
    description: str = ""
    icon: str = "🤖"
    color: str = "#10B981"
    status: str = "draft"
    prompts: dict = {}
    default_model: str = "claude-sonnet-4-20250514"
    default_thinking_level: str = "medium"
    default_language: str = "en"
    providers: list[BundleProvider] = []
    mcp_servers: dict = {}
    skills: list[str] = []
    sort_order: int = 0


class UpdateBundleRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    status: str | None = None
    prompts: dict | None = None
    default_model: str | None = None
    default_thinking_level: str | None = None
    default_language: str | None = None
    providers: list[BundleProvider] | None = None
    mcp_servers: dict | None = None
    skills: list[str] | None = None
    sort_order: int | None = None
