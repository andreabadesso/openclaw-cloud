-- 001_initial.sql
-- Initial schema for openclaw_cloud database.

BEGIN;

-- ============================================================
-- Enums
-- ============================================================

CREATE TYPE subscription_status AS ENUM (
    'trialing', 'active', 'past_due', 'suspended', 'cancelled'
);

CREATE TYPE tier AS ENUM ('starter', 'pro', 'team');

CREATE TYPE box_status AS ENUM (
    'pending',
    'provisioning',
    'active',
    'updating',
    'suspended',
    'unhealthy',
    'destroying',
    'destroyed'
);

CREATE TYPE onboarding_state AS ENUM (
    'new', 'greeting', 'gathering_use_case', 'gathering_telegram',
    'gathering_preferences', 'recommending_tier',
    'awaiting_payment', 'provisioning', 'complete', 'failed', 'abandoned'
);

CREATE TYPE job_type AS ENUM (
    'provision', 'update', 'destroy', 'suspend', 'reactivate', 'resize', 'health_check'
);

CREATE TYPE job_status AS ENUM ('queued', 'running', 'complete', 'failed');

-- ============================================================
-- Tables
-- ============================================================

-- customers
CREATE TABLE customers (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email              TEXT NOT NULL UNIQUE,
    stripe_customer_id TEXT UNIQUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at         TIMESTAMPTZ,
    CONSTRAINT email_format CHECK (email ~* '^[^@]+@[^@]+\.[^@]+$')
);

CREATE INDEX idx_customers_stripe_customer_id ON customers (stripe_customer_id);
CREATE INDEX idx_customers_email_active ON customers (email) WHERE deleted_at IS NULL;

-- subscriptions
CREATE TABLE subscriptions (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id            UUID NOT NULL REFERENCES customers(id),
    stripe_subscription_id TEXT UNIQUE,
    stripe_price_id        TEXT,
    tier                   tier NOT NULL,
    status                 subscription_status NOT NULL DEFAULT 'active',
    tokens_limit           BIGINT NOT NULL,
    current_period_start   TIMESTAMPTZ NOT NULL,
    current_period_end     TIMESTAMPTZ NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_subscriptions_customer_id ON subscriptions (customer_id);
CREATE INDEX idx_subscriptions_stripe_subscription_id ON subscriptions (stripe_subscription_id);

-- boxes
CREATE TABLE boxes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES customers(id),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id),

    -- K8s identity
    k8s_namespace   TEXT NOT NULL UNIQUE,

    -- OpenClaw config
    telegram_user_ids  BIGINT[] NOT NULL DEFAULT '{}',
    language           TEXT NOT NULL DEFAULT 'en',
    model              TEXT NOT NULL DEFAULT 'kimi-coding/k2p5',
    thinking_level     TEXT NOT NULL DEFAULT 'medium',

    -- State
    status          box_status NOT NULL DEFAULT 'pending',
    health_failures INT NOT NULL DEFAULT 0,
    last_seen       TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at    TIMESTAMPTZ,
    last_updated    TIMESTAMPTZ,
    destroyed_at    TIMESTAMPTZ
);

CREATE INDEX idx_boxes_customer_id ON boxes (customer_id);
CREATE INDEX idx_boxes_status_active ON boxes (status) WHERE status NOT IN ('destroyed');

-- proxy_tokens
CREATE TABLE proxy_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    box_id      UUID NOT NULL REFERENCES boxes(id),
    token_hash  TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ
);

CREATE INDEX idx_proxy_tokens_hash_active ON proxy_tokens (token_hash) WHERE revoked_at IS NULL;
CREATE INDEX idx_proxy_tokens_customer_id ON proxy_tokens (customer_id);

-- usage_monthly
CREATE TABLE usage_monthly (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id  UUID NOT NULL REFERENCES customers(id),
    period_start TIMESTAMPTZ NOT NULL,
    period_end   TIMESTAMPTZ NOT NULL,
    tokens_used  BIGINT NOT NULL DEFAULT 0,
    tokens_limit BIGINT NOT NULL,
    reset_at     TIMESTAMPTZ,
    UNIQUE (customer_id, period_start)
);

CREATE INDEX idx_usage_monthly_customer_period ON usage_monthly (customer_id, period_start DESC);

-- usage_events
CREATE TABLE usage_events (
    id                BIGSERIAL PRIMARY KEY,
    customer_id       UUID NOT NULL REFERENCES customers(id),
    box_id            UUID NOT NULL REFERENCES boxes(id),
    timestamp         TIMESTAMPTZ NOT NULL DEFAULT now(),
    model             TEXT NOT NULL,
    prompt_tokens     INT NOT NULL,
    completion_tokens INT NOT NULL,
    total_tokens      INT GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED,
    request_id        TEXT
);

CREATE INDEX idx_usage_events_customer_timestamp ON usage_events (customer_id, timestamp DESC);

-- onboarding_sessions
CREATE TABLE onboarding_sessions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id      UUID REFERENCES customers(id),
    session_token    TEXT NOT NULL UNIQUE,
    state            onboarding_state NOT NULL DEFAULT 'new',
    messages         JSONB NOT NULL DEFAULT '[]',
    derived_config   JSONB,
    telegram_user_id BIGINT,
    detected_language TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at       TIMESTAMPTZ NOT NULL DEFAULT now() + interval '24 hours'
);

CREATE INDEX idx_onboarding_sessions_token ON onboarding_sessions (session_token);
CREATE INDEX idx_onboarding_sessions_expires ON onboarding_sessions (expires_at) WHERE state NOT IN ('complete', 'failed');

-- operator_jobs
CREATE TABLE operator_jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id  UUID NOT NULL REFERENCES customers(id),
    box_id       UUID REFERENCES boxes(id),
    job_type     job_type NOT NULL,
    status       job_status NOT NULL DEFAULT 'queued',
    payload      JSONB NOT NULL DEFAULT '{}',
    error_log    TEXT,
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_operator_jobs_customer_created ON operator_jobs (customer_id, created_at DESC);
CREATE INDEX idx_operator_jobs_status_active ON operator_jobs (status) WHERE status IN ('queued', 'running');

COMMIT;
