# Token Proxy

The token proxy is the mechanism by which we:
1. Keep the Kimi API key centralized (customers never see it)
2. Meter every token used by every customer
3. Enforce hard monthly limits per tier
4. Provide usage data for the dashboard and billing

---

## Architecture

The proxy is a custom HTTP service (Go or Python FastAPI) deployed behind a K8s LoadBalancer with TLS termination.

> **Why not Envoy?** Envoy's Lua scripting is possible but complex for stateful token counting. A lightweight Go or Python proxy gives us full control, is easy to test, and performs well enough at our scale.

**Deployment**: 3 replicas, HPA scaled on CPU. Each request is synchronous but token writes are async (fire-and-forget via Redis stream → background consumer → Postgres).

---

## How Customer VMs Use the Proxy

During provisioning, each customer's `box.toml` sets:

```toml
[openclaw.env]
KIMI_BASE_URL = "https://proxy.openclaw.cloud/v1"
KIMI_API_KEY  = "/run/secrets/kimi_proxy_token"
```

The `kimi_proxy_token` is a customer-specific token (UUID, 32 chars) stored encrypted in the box's SOPS secrets. The token-proxy maps it to a `customer_id`.

From the OpenClaw gateway's perspective, it's just talking to a compatible OpenAI-style API. No code changes needed in OpenClaw itself.

---

## Request Flow

```
Customer VM
  │
  │  POST https://proxy.openclaw.cloud/v1/chat/completions
  │  Authorization: Bearer {kimi_proxy_token}
  │  Content-Type: application/json
  │  {messages: [...], model: "kimi-coding/k2p5", ...}
  │
  ▼
token-proxy
  1. Authenticate: lookup proxy_token → customer_id (Redis cache, 5min TTL)
  2. Check limits:
     a. Load {customer_id: {used, limit, tier}} from Redis (1min TTL)
     b. If used >= limit → return 429 {error: "monthly_limit_exceeded"}
     c. If used >= limit * 0.9 → add warning header X-Token-Warning: 90%
  3. Forward: proxy request to api.moonshot.cn/v1 with real KIMI_API_KEY
  4. Stream response back to customer VM (streaming supported)
  5. On response complete: extract usage from response body
     usage = response.usage.prompt_tokens + response.usage.completion_tokens
  6. Async write: push {customer_id, usage, timestamp, model} to Redis Stream
  7. Return response to customer VM
```

---

## Token Limit Enforcement

Limits by tier:

| Tier | Monthly Token Limit | Warning at |
|---|---|---|
| Starter | 1,000,000 | 900,000 (90%) |
| Pro | 5,000,000 | 4,500,000 (90%) |
| Team | 20,000,000 | 18,000,000 (90%) |

At 90%: customer gets an email warning + dashboard banner. The agent continues to work.
At 100%: proxy returns 429. The OpenClaw agent responds to the user: "I've reached my monthly AI limit. My owner can upgrade at app.openclaw.cloud/billing."

Limits reset on billing period renewal (Stripe invoice paid event resets `usage_monthly.tokens_used = 0`).

---

## Token Usage Accounting

### Write Path (async, non-blocking)

```
proxy → Redis Stream "usage:events" → consumer worker → Postgres
```

The consumer worker (runs as a goroutine / asyncio task in the proxy) batches writes:
- Flush every 5 seconds OR when batch size reaches 100 events
- On flush: `INSERT INTO usage_events (...) ON CONFLICT DO NOTHING`
- On flush: `UPDATE usage_monthly SET tokens_used = tokens_used + batch_total WHERE customer_id = ? AND period = current_period()`
- After each Postgres write: update Redis cache for that customer

### Read Path (dashboard)

```
GET /me/usage
  → SELECT tokens_used, tokens_limit, period_start, period_end
    FROM usage_monthly
    JOIN subscriptions USING (customer_id)
    WHERE customer_id = ? AND period = current_period()
```

### Read Path (enforcement, cached)

```
proxy cache lookup:
  key: "limit:{customer_id}"
  value: {used: 412345, limit: 5000000, tier: "pro"}
  TTL: 60 seconds

On cache miss:
  SELECT tokens_used, tokens_limit FROM usage_monthly JOIN subscriptions ...
  SET in Redis with TTL 60s
```

The 60s cache means a customer could briefly exceed their limit by at most 60 seconds of usage before the hard stop kicks in. This is acceptable — we're not running a nuclear reactor.

---

## Streaming Support

Kimi API supports SSE streaming (`stream: true`). The proxy handles this by:

1. Detecting `"stream": true` in the request body
2. Opening a streaming response upstream
3. Piping SSE chunks directly to the customer VM
4. Accumulating token counts from `data: {"usage": ...}` chunks (Kimi sends final usage in the last chunk)
5. Recording usage only after the stream completes (last chunk received)

---

## Proxy Token Management

| Operation | Trigger | Actor |
|---|---|---|
| Token created | Provision job starts | Operator |
| Token stored | As SOPS secret in box | Operator |
| Token registered | POST /internal/tokens | Operator → token-proxy |
| Token validated | Every request | token-proxy → Redis/Postgres |
| Token revoked | Destroy job | Operator → token-proxy |

Token registry is stored in Postgres (`proxy_tokens` table) with a Redis cache (by token value → customer_id).

---

## Security Considerations

- The proxy's `KIMI_API_KEY` is mounted as a K8s Secret from Vault, never in env plaintext
- All proxy traffic is TLS (cert-manager + Let's Encrypt)
- Customer proxy tokens are rotated annually or on customer request
- The proxy validates tokens in constant time (no timing oracle)
- Rate limiting: max 10 req/s per customer (Redis token bucket), prevents runaway loops
- The proxy does not log request bodies (privacy) — only metadata: customer_id, model, token count, timestamp

---

## Monitoring

Key metrics exported to Prometheus:

```
# Total tokens forwarded
token_proxy_tokens_total{customer_id, tier, model}

# Request latency (p50/p95/p99)
token_proxy_request_duration_seconds{upstream}

# Blocked requests (limit exceeded)
token_proxy_blocked_total{customer_id, reason}

# Upstream errors
token_proxy_upstream_errors_total{status_code}
```

Grafana dashboard: one row per metric, with tier breakdown. Alert on:
- `token_proxy_upstream_errors_total` spike (Kimi outage)
- `token_proxy_request_duration_seconds{p99}` > 5s
- Any customer hitting 100% limit (ops review)
