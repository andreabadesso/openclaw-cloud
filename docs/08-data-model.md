# Data Model

PostgreSQL schema for the `openclaw_cloud` database. Managed via Alembic migrations in `db/migrations/`.

---

## Tables

### `customers`

```sql
CREATE TABLE customers (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email              TEXT NOT NULL UNIQUE,
    stripe_customer_id TEXT UNIQUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at         TIMESTAMPTZ,
    CONSTRAINT email_format CHECK (email ~* '^[^@]+@[^@]+\.[^@]+$')
);

CREATE INDEX ON customers (stripe_customer_id);
CREATE INDEX ON customers (email) WHERE deleted_at IS NULL;
```

---

### `subscriptions`

```sql
CREATE TYPE subscription_status AS ENUM (
    'trialing', 'active', 'past_due', 'suspended', 'cancelled'
);

CREATE TYPE tier AS ENUM ('starter', 'pro', 'team');

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

CREATE INDEX ON subscriptions (customer_id);
CREATE INDEX ON subscriptions (stripe_subscription_id);
```

---

### `boxes`

Represents a customer's OpenClaw agent instance (a K8s namespace + pod).

```sql
CREATE TYPE box_status AS ENUM (
    'pending',       -- provision job enqueued
    'provisioning',  -- kubectl apply in progress
    'active',        -- pod Running + Ready
    'updating',      -- rolling restart in progress
    'suspended',     -- Deployment scaled to 0
    'unhealthy',     -- pod not Ready for 3+ health checks
    'destroying',    -- destroy job in progress
    'destroyed'      -- namespace deleted
);

CREATE TABLE boxes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES customers(id),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id),

    -- K8s identity
    k8s_namespace   TEXT NOT NULL UNIQUE,  -- "customer-{id}"

    -- OpenClaw config (source of truth for what's in the K8s Secret)
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

CREATE INDEX ON boxes (customer_id);
CREATE INDEX ON boxes (status) WHERE status NOT IN ('destroyed');
```

---

### `proxy_tokens`

Maps per-customer proxy tokens to customer accounts. The real token value lives only in the customer's K8s Secret. We store only the hash.

```sql
CREATE TABLE proxy_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    box_id      UUID NOT NULL REFERENCES boxes(id),
    token_hash  TEXT NOT NULL UNIQUE,  -- bcrypt hash
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ
);

CREATE INDEX ON proxy_tokens (token_hash) WHERE revoked_at IS NULL;
CREATE INDEX ON proxy_tokens (customer_id);
```

---

### `usage_monthly`

Aggregated token usage per customer per billing period.

```sql
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

CREATE INDEX ON usage_monthly (customer_id, period_start DESC);
```

---

### `usage_events`

Raw token events. Written by token-proxy (async batch inserts).

```sql
CREATE TABLE usage_events (
    id                BIGSERIAL PRIMARY KEY,
    customer_id       UUID NOT NULL REFERENCES customers(id),
    box_id            UUID NOT NULL REFERENCES boxes(id),
    timestamp         TIMESTAMPTZ NOT NULL DEFAULT now(),
    model             TEXT NOT NULL,
    prompt_tokens     INT NOT NULL,
    completion_tokens INT NOT NULL,
    total_tokens      INT GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED,
    request_id        TEXT  -- Kimi request ID for dedup
);

CREATE INDEX ON usage_events (customer_id, timestamp DESC);
```

---

### `onboarding_sessions`

Stores the onboarding conversation and derived config.

```sql
CREATE TYPE onboarding_state AS ENUM (
    'new', 'greeting', 'gathering_use_case', 'gathering_telegram',
    'gathering_preferences', 'recommending_tier',
    'awaiting_payment', 'provisioning', 'complete', 'failed', 'abandoned'
);

CREATE TABLE onboarding_sessions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id      UUID REFERENCES customers(id),  -- NULL until account created
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

CREATE INDEX ON onboarding_sessions (session_token);
CREATE INDEX ON onboarding_sessions (expires_at) WHERE state NOT IN ('complete', 'failed');
```

---

### `operator_jobs`

Audit log for all operator jobs. The live queue is Redis; this is the permanent record.

```sql
CREATE TYPE job_type AS ENUM (
    'provision', 'update', 'destroy', 'suspend', 'reactivate', 'resize', 'health_check'
);
CREATE TYPE job_status AS ENUM ('queued', 'running', 'complete', 'failed');

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

CREATE INDEX ON operator_jobs (customer_id, created_at DESC);
CREATE INDEX ON operator_jobs (status) WHERE status IN ('queued', 'running');
```

---

## Key Queries

### Current token usage (dashboard)

```sql
SELECT
    um.tokens_used,
    um.tokens_limit,
    ROUND(um.tokens_used::NUMERIC / um.tokens_limit * 100, 1) AS pct_used,
    um.period_start,
    um.period_end
FROM usage_monthly um
WHERE um.customer_id = $1
  AND um.period_start <= now()
  AND um.period_end > now()
ORDER BY um.period_start DESC
LIMIT 1;
```

### Token proxy limit check (cached 60s in Redis)

```sql
SELECT um.tokens_used, um.tokens_limit, s.tier
FROM usage_monthly um
JOIN subscriptions s ON s.customer_id = um.customer_id
WHERE um.customer_id = $1
  AND um.period_start <= now()
  AND um.period_end > now()
  AND s.status = 'active';
```

### Active boxes needing health check

```sql
SELECT id, k8s_namespace, customer_id
FROM boxes
WHERE status = 'active'
  AND (last_seen IS NULL OR last_seen < now() - interval '5 minutes');
```

### Reset usage on subscription renewal

```sql
INSERT INTO usage_monthly (customer_id, period_start, period_end, tokens_limit)
VALUES ($1, $2, $3, $4)
ON CONFLICT (customer_id, period_start)
DO UPDATE SET tokens_used = 0, reset_at = now(), tokens_limit = EXCLUDED.tokens_limit;
```
