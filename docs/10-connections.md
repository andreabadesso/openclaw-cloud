# Connections — OAuth Integrations for Customer Agents

> **The agent is only as useful as the services it can reach.**
> Connections let customers authorize their agent to access Google Drive, GitHub, Slack, and more — securely, via OAuth. The agent becomes a real tool, not just a chatbot.

---

## Why This Matters

Without connections, an OpenClaw agent can only:
- Chat via Telegram
- Call Kimi for AI reasoning

With connections, it can:
- Read and write Google Docs/Sheets/Drive files
- Open PRs, review code, manage issues on GitHub
- Post to Slack channels, read threads
- Access Notion databases, Jira boards, Linear issues
- Pull data from any OAuth2-compatible API

This is the difference between a toy and a tool. Connections make churn plummet because the agent becomes embedded in the customer's workflow.

---

## Design Principles

1. **Customer pods never see OAuth tokens** — same pattern as the Kimi API key. All external API calls go through `connection-proxy`, which injects the token.
2. **Platform-managed OAuth apps** — we register one GitHub app, one Google app, etc. Customers don't create their own OAuth clients.
3. **Proxy model, not credential injection** — tokens live only in the platform namespace. Customer pods call the proxy, the proxy calls GitHub/Google/etc.
4. **Transparent to the agent** — the OpenClaw agent calls what looks like a normal REST API. The proxy handles auth, refresh, and rate limiting.
5. **Declarative provider config** — adding a new provider = adding a YAML entry + registering an OAuth app.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   CONTROL PLANE  (platform namespace)               │
│                                                                     │
│  ┌──────────┐    ┌──────────────────┐    ┌─────────────────────┐   │
│  │   web    │───▶│   api            │    │  connection-proxy   │   │
│  │ (Next.js)│    │   (FastAPI)      │    │  (FastAPI)          │   │
│  └────┬─────┘    │                  │    │                     │   │
│       │          │  POST /oauth/    │    │  Authenticates      │   │
│  OAuth popup     │    callback      │    │  proxy token →      │   │
│  opens provider  │  GET /me/        │    │  customer_id        │   │
│  auth page       │    connections   │    │                     │   │
│       │          │  DELETE /me/     │    │  Verifies connection │   │
│       │          │    connections/  │    │  belongs to customer │   │
│       │          │    {id}          │    │                     │   │
│       │          └──────┬──────────┘    │  Decrypts token,    │   │
│       │                 │               │  refreshes if needed │   │
│       │                 ▼               │                     │   │
│       │          ┌──────────────┐       │  Proxies request to │   │
│       │          │  PostgreSQL  │       │  external API with  │   │
│       │          │              │       │  injected auth      │   │
│       │          │  connections │       └──────────┬──────────┘   │
│       │          │  table       │                  │               │
│       │          └──────────────┘                  │               │
│       │                                            ▼               │
│       │          ┌──────────────┐          ┌──────────────┐       │
│       │          │    Redis     │          │  External    │       │
│       │          │              │          │  APIs        │       │
│       │          │  - refresh   │          │  (GitHub,    │       │
│       │          │    locks     │          │   Google,    │       │
│       │          │  - token     │          │   Slack)     │       │
│       │          │    cache     │          └──────────────┘       │
│       │          └──────────────┘                                  │
└───────┼────────────────────────────────────────────────────────────┘
        │
        │   NetworkPolicy: allow egress to connection-proxy (port 8081)
        │
  ┌─────▼──────────────┐
  │  customer-{id}     │
  │                    │
  │  Agent calls:      │
  │  connection-proxy  │
  │  .platform.svc     │
  │  .cluster.local    │
  │  :8081             │
  │  /github/user/repos│
  └────────────────────┘
```

---

## How It Works — End to End

### Step 1: Customer Connects a Service (Web Dashboard)

```
1. Customer clicks "Connect GitHub" in dashboard
2. web → api: POST /me/connections/github/authorize
   → api generates a state token (random, Redis, 5min TTL)
   → api returns authorization URL with state
3. web opens popup to: https://github.com/login/oauth/authorize
     ?client_id={PLATFORM_GITHUB_CLIENT_ID}
     &redirect_uri=https://api.openclaw.cloud/oauth/callback
     &state={state_token}
     &scope=repo,read:user
4. Customer authorizes in GitHub
5. GitHub redirects to: https://api.openclaw.cloud/oauth/callback
     ?code={auth_code}&state={state_token}
6. api:
   a. Validates state token (Redis lookup + delete)
   b. Exchanges code for tokens with GitHub
   c. Encrypts token payload (AES-256-GCM)
   d. Stores in connections table
   e. Returns HTML that closes the popup + signals success
7. Dashboard refreshes, shows "GitHub: Connected"
```

### Step 2: Agent Uses the Connection (Runtime)

```
1. User tells agent via Telegram: "list my repos"
2. Agent decides to call GitHub API
3. Agent calls:
     GET http://connection-proxy.platform.svc.cluster.local:8081
       /github/user/repos
     Authorization: Bearer {proxy_token}     ← same token used for Kimi
4. connection-proxy:
   a. Authenticates proxy_token → customer_id
   b. Looks up active GitHub connection for customer_id
   c. Decrypts access token (from cache or Postgres)
   d. If expired: acquires Redis lock, refreshes, stores new tokens
   e. Proxies request to https://api.github.com/user/repos
      with Authorization: Bearer {github_access_token}
   f. Returns response to agent
5. Agent formats the repo list and sends it via Telegram
```

### Step 3: Token Refresh (Background)

```
A background worker runs every 5 minutes:

1. SELECT * FROM connections
   WHERE status = 'active'
     AND token_expires_at < now() + interval '15 minutes'
     AND token_expires_at > now()

2. For each expiring connection:
   a. Acquire Redis lock: connection:refresh:{connection_id} (30s TTL)
   b. If lock acquired:
      - Call provider's token URL with refresh_token
      - Encrypt new tokens
      - UPDATE connections SET encrypted_data=..., token_expires_at=...
      - Invalidate Redis cache for this connection
   c. If lock not acquired: skip (another worker/request is handling it)
```

---

## Provider Configuration

Providers are defined in a YAML file (`apps/connection-proxy/providers.yaml`):

```yaml
github:
  display_name: GitHub
  auth_mode: oauth2
  authorization_url: https://github.com/login/oauth/authorize
  token_url: https://github.com/login/oauth/access_token
  proxy_base_url: https://api.github.com
  default_scopes:
    - repo
    - read:user
    - read:org
  token_response_format: form   # GitHub returns form-encoded, not JSON
  refresh_strategy: reauth      # GitHub tokens don't expire, no refresh needed

google:
  display_name: Google Workspace
  auth_mode: oauth2
  authorization_url: https://accounts.google.com/o/oauth2/auth
  token_url: https://oauth2.googleapis.com/token
  proxy_base_url: https://www.googleapis.com
  available_scopes:
    drive: https://www.googleapis.com/auth/drive
    sheets: https://www.googleapis.com/auth/spreadsheets
    docs: https://www.googleapis.com/auth/documents
    gmail_readonly: https://www.googleapis.com/auth/gmail.readonly
    calendar: https://www.googleapis.com/auth/calendar
  extra_auth_params:
    access_type: offline       # required to get refresh_token
    prompt: consent            # force consent to always get refresh_token
  refresh_strategy: standard   # Google tokens expire in 1h, refresh supported

slack:
  display_name: Slack
  auth_mode: oauth2
  authorization_url: https://slack.com/oauth/v2/authorize
  token_url: https://slack.com/api/oauth.v2.access
  proxy_base_url: https://slack.com/api
  default_scopes:
    - channels:read
    - chat:write
    - users:read
  refresh_strategy: none       # Slack tokens don't expire

linear:
  display_name: Linear
  auth_mode: oauth2
  authorization_url: https://linear.app/oauth/authorize
  token_url: https://api.linear.app/oauth/token
  proxy_base_url: https://api.linear.app
  default_scopes:
    - read
    - write
  refresh_strategy: standard

notion:
  display_name: Notion
  auth_mode: oauth2
  authorization_url: https://api.notion.com/v1/oauth/authorize
  token_url: https://api.notion.com/v1/oauth/token
  proxy_base_url: https://api.notion.com
  default_scopes: []           # Notion uses page-level permissions, no scopes
  refresh_strategy: none       # Notion tokens don't expire

jira:
  display_name: Jira
  auth_mode: oauth2
  authorization_url: https://auth.atlassian.com/authorize
  token_url: https://auth.atlassian.com/oauth/token
  proxy_base_url: https://api.atlassian.com
  default_scopes:
    - read:jira-work
    - write:jira-work
  extra_auth_params:
    audience: api.atlassian.com
    prompt: consent
  refresh_strategy: standard

# --- API Key providers ---

openai:
  display_name: OpenAI
  auth_mode: api_key
  proxy_base_url: https://api.openai.com
  auth_header: Authorization
  auth_prefix: "Bearer "

custom:
  display_name: Custom API
  auth_mode: api_key
  proxy_base_url: null          # customer provides the base URL
  auth_header: Authorization
  auth_prefix: "Bearer "
```

Adding a new OAuth provider = add a YAML entry + register an OAuth app with that provider + add client_id/secret to `platform-secrets`.

Adding a new API key provider = add a YAML entry. That's it.

---

## Data Model

### `connections` table

```sql
CREATE TABLE connections (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id      UUID NOT NULL REFERENCES customers(id),
    provider         TEXT NOT NULL,           -- 'github', 'google', 'slack'
    display_name     TEXT,                    -- "My GitHub (work)" or auto-generated
    status           TEXT NOT NULL DEFAULT 'active',
                     -- active: working
                     -- error: refresh failed, needs reauth
                     -- revoked: customer disconnected

    -- Scopes granted by the user (may differ from requested)
    scopes           TEXT[] NOT NULL DEFAULT '{}',

    -- Encrypted token payload (AES-256-GCM)
    -- Contains: { access_token, refresh_token, token_type, raw_response }
    encrypted_data   BYTEA NOT NULL,
    encryption_key_version INT NOT NULL DEFAULT 1,

    -- Token lifecycle
    token_expires_at  TIMESTAMPTZ,           -- NULL if token doesn't expire
    last_refreshed_at TIMESTAMPTZ,
    last_used_at      TIMESTAMPTZ,

    -- Error tracking
    error_message     TEXT,                  -- populated when status='error'
    consecutive_failures INT NOT NULL DEFAULT 0,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One active connection per provider per customer
    UNIQUE (customer_id, provider) WHERE (status = 'active')
);

CREATE INDEX idx_connections_customer ON connections(customer_id) WHERE status != 'revoked';
CREATE INDEX idx_connections_refresh ON connections(token_expires_at)
    WHERE status = 'active' AND token_expires_at IS NOT NULL;
```

### `connection_usage_events` table (audit log)

```sql
CREATE TABLE connection_usage_events (
    id              BIGSERIAL PRIMARY KEY,
    customer_id     UUID NOT NULL REFERENCES customers(id),
    connection_id   UUID NOT NULL REFERENCES connections(id),
    provider        TEXT NOT NULL,
    method          TEXT NOT NULL,            -- GET, POST, etc.
    path            TEXT NOT NULL,            -- /user/repos
    status_code     INT,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conn_usage_customer ON connection_usage_events(customer_id, timestamp DESC);
```

---

## Encryption

### Token Encryption at Rest

All OAuth tokens are encrypted before storage using AES-256-GCM:

```python
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Platform-level encryption key (from env / K8s Secret)
# 32 bytes = 256 bits
ENCRYPTION_KEY = base64.b64decode(os.environ["CONNECTION_ENCRYPTION_KEY"])

def encrypt_token_data(data: dict) -> tuple[bytes, int]:
    """Encrypt token payload. Returns (ciphertext, key_version)."""
    plaintext = json.dumps(data).encode()
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(ENCRYPTION_KEY)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    # Prepend nonce to ciphertext for storage
    return nonce + ciphertext, CURRENT_KEY_VERSION

def decrypt_token_data(encrypted: bytes, key_version: int) -> dict:
    """Decrypt token payload."""
    key = get_key_for_version(key_version)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext)
```

### Key Rotation

The `encryption_key_version` column supports rotation:

1. Generate a new key, store as `CONNECTION_ENCRYPTION_KEY_V2`
2. Set `CURRENT_KEY_VERSION=2` in env
3. New connections encrypt with V2
4. Background migration job: read with old key, re-encrypt with new key, update version
5. Once all rows are V2, remove V1 key

---

## Connection Proxy — Request Flow

### URL Pattern

Customer pods call the connection proxy using a provider-prefixed path:

```
http://connection-proxy.platform.svc.cluster.local:8081/{provider}/{path}

Examples:
  GET  /github/user/repos
  POST /google/drive/v3/files
  GET  /slack/conversations.list
  POST /linear/graphql
  GET  /notion/v1/databases/{id}/query
```

### Proxy Logic

```python
@app.api_route("/{provider}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_request(provider: str, path: str, request: Request):
    # 1. Authenticate — same proxy_token as token-proxy
    customer_id = await authenticate_proxy_token(request)

    # 2. Find active connection
    connection = await get_active_connection(customer_id, provider)
    if not connection:
        return JSONResponse(
            status_code=422,
            content={
                "error": "no_connection",
                "provider": provider,
                "message": f"No active {provider} connection. "
                           f"Connect at app.openclaw.cloud/dashboard/connections"
            }
        )

    # 3. Get valid access token (refresh if needed)
    access_token = await get_valid_token(connection)

    # 4. Proxy the request
    provider_config = PROVIDERS[provider]
    upstream_url = f"{provider_config.proxy_base_url}/{path}"

    response = await httpx.AsyncClient().request(
        method=request.method,
        url=upstream_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": request.headers.get("content-type", "application/json"),
        },
        content=await request.body(),
        params=request.query_params,
    )

    # 5. Log usage (async, non-blocking)
    await log_connection_usage(customer_id, connection.id, provider,
                               request.method, path, response.status_code)

    # 6. Return response
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers={"Content-Type": response.headers.get("content-type", "application/json")},
    )
```

### Token Refresh with Locking

```python
async def get_valid_token(connection: Connection) -> str:
    """Get a valid access token, refreshing if necessary."""
    # Check Redis cache first
    cached = await redis.get(f"conn:token:{connection.id}")
    if cached:
        return cached

    # Decrypt token data
    token_data = decrypt_token_data(connection.encrypted_data,
                                     connection.encryption_key_version)

    # If token doesn't expire or isn't expiring soon, use it
    if (connection.token_expires_at is None or
        connection.token_expires_at > utcnow() + timedelta(minutes=5)):
        await redis.setex(f"conn:token:{connection.id}", 240, token_data["access_token"])
        return token_data["access_token"]

    # Token needs refresh — acquire lock
    lock_key = f"conn:refresh:{connection.id}"
    lock = await redis.set(lock_key, "1", nx=True, ex=30)

    if not lock:
        # Another process is refreshing, wait and retry
        for _ in range(10):
            await asyncio.sleep(1)
            cached = await redis.get(f"conn:token:{connection.id}")
            if cached:
                return cached
        raise HTTPException(503, "Token refresh in progress, try again")

    try:
        # Refresh the token
        provider_config = PROVIDERS[connection.provider]
        new_tokens = await refresh_oauth_token(
            token_url=provider_config.token_url,
            refresh_token=token_data["refresh_token"],
            client_id=provider_config.client_id,
            client_secret=provider_config.client_secret,
        )

        # Update stored tokens
        token_data["access_token"] = new_tokens["access_token"]
        if "refresh_token" in new_tokens:
            token_data["refresh_token"] = new_tokens["refresh_token"]

        encrypted, key_version = encrypt_token_data(token_data)
        expires_at = utcnow() + timedelta(seconds=new_tokens.get("expires_in", 3600))

        await db.execute(
            "UPDATE connections SET encrypted_data=$1, encryption_key_version=$2, "
            "token_expires_at=$3, last_refreshed_at=now(), consecutive_failures=0, "
            "status='active', updated_at=now() WHERE id=$4",
            encrypted, key_version, expires_at, connection.id
        )

        # Cache the fresh token (4 min TTL, shorter than 5 min expiry check)
        await redis.setex(f"conn:token:{connection.id}", 240, new_tokens["access_token"])

        return new_tokens["access_token"]

    except Exception as e:
        # Mark connection as errored after 3 consecutive failures
        await db.execute(
            "UPDATE connections SET consecutive_failures = consecutive_failures + 1, "
            "error_message=$1, status = CASE WHEN consecutive_failures >= 2 "
            "THEN 'error' ELSE status END, updated_at=now() WHERE id=$2",
            str(e), connection.id
        )
        raise HTTPException(502, f"Failed to refresh {connection.provider} token")

    finally:
        await redis.delete(lock_key)
```

---

## NetworkPolicy Update

Customer pods need egress to `connection-proxy` in addition to `token-proxy`. The operator adds this at provisioning:

```yaml
egress:
  # Existing: token-proxy for Kimi API
  - to:
      - namespaceSelector:
          matchLabels:
            kubernetes.io/metadata.name: platform
        podSelector:
          matchLabels:
            app: token-proxy
    ports:
      - port: 8080

  # NEW: connection-proxy for external service APIs
  - to:
      - namespaceSelector:
          matchLabels:
            kubernetes.io/metadata.name: platform
        podSelector:
          matchLabels:
            app: connection-proxy
    ports:
      - port: 8081

  # Existing: Telegram + DNS
  # ...
```

---

## API Routes

### Customer-facing (authenticated via JWT)

```
GET    /me/connections
       → list all connections for the customer
       → [{id, provider, display_name, status, scopes, created_at, last_used_at}]

POST   /me/connections/{provider}/authorize
       → initiate OAuth flow
       → returns {authorization_url} (frontend opens popup)
       → optional body: {scopes: ["repo", "read:user"]}  (override defaults)

DELETE /me/connections/{id}
       → revoke connection (marks as 'revoked', clears cached tokens)

POST   /me/connections/{id}/reconnect
       → re-initiate OAuth for a broken (status='error') connection
```

### OAuth callback (public, no auth — validated via state token)

```
GET    /oauth/callback?code={code}&state={state}
       → exchanges code for tokens
       → stores encrypted in connections table
       → returns HTML that closes popup and signals success to parent window
```

### Internal (connection-proxy → api, or admin)

```
GET    /internal/connections/{customer_id}
       → used by connection-proxy to verify connection ownership
       → returns connection metadata + encrypted_data

GET    /internal/connections/{connection_id}/token
       → returns decrypted access token (only callable from within cluster)
       → used by connection-proxy when Redis cache misses
```

---

## Dashboard UI

The connections page in the web dashboard:

```
┌─────────────────────────────────────────────────────────┐
│  My Connections                                          │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │  ✅ GitHub          repo, read:user    Connected    ││
│  │     Last used: 2 hours ago            [Disconnect]  ││
│  └─────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────┐│
│  │  ❌ Google Drive    drive, sheets      Error        ││
│  │     Token expired, needs reauth       [Reconnect]   ││
│  └─────────────────────────────────────────────────────┘│
│                                                          │
│  Add a Connection:                                       │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
│  │ GitHub │ │ Google │ │ Slack  │ │ Linear │           │
│  └────────┘ └────────┘ └────────┘ └────────┘           │
│  ┌────────┐ ┌────────┐                                  │
│  │ Notion │ │ Jira   │                                  │
│  └────────┘ └────────┘                                  │
└─────────────────────────────────────────────────────────┘
```

---

## Agent Integration

### How OpenClaw Knows About Available Connections

During provisioning (or when connections change), the operator updates the customer pod's K8s Secret with a connection manifest:

```yaml
# Added to openclaw-config Secret
OPENCLAW_CONNECTIONS: |
  connection_proxy_url: http://connection-proxy.platform.svc.cluster.local:8081
  available:
    - provider: github
      scopes: [repo, read:user]
    - provider: google
      scopes: [drive, sheets]
```

The OpenClaw agent reads this at startup and knows which external APIs it can call. When a user asks "check my GitHub PRs", the agent:

1. Sees `github` in available connections
2. Calls `connection-proxy:8081/github/user/repos`
3. Gets the response as if it called GitHub directly

If the user asks for something that requires a missing connection, the agent generates a deep link on the fly (see "Runtime Connection Requests" section):

```
User: "Check my Slack messages"

Agent: "I don't have access to Slack yet. Connect it with one tap
        and I'll be able to read your channels:

        → https://app.openclaw.cloud/connect/slack?token=abc123

        Once you're done, just ask me again!"
```

The user taps the link in Telegram, authorizes Slack in their browser, and the agent picks up the new connection immediately on the next request. No pod restart, no dashboard navigation.

### System Prompt Addition

The agent's system prompt includes:

```
You have access to the following external services via your connection proxy:
{{#each connections}}
- {{provider}}: scopes={{scopes}}
  Base URL: {connection_proxy_url}/{{provider}}/
{{/each}}

To call these services, make HTTP requests to the connection proxy URL.
Authentication is handled automatically — do not add auth headers.

If a user asks for something that requires a service you're not connected to:
1. Call POST {connection_proxy_url}/internal/connect-link
   with body: {"provider": "<provider_name>"}
2. Include the returned URL in your response so the user can connect
   with one tap directly from Telegram.
3. Tell them to ask again once they've connected.
```

---

## Security Considerations

### Token Isolation

- OAuth tokens are encrypted at rest (AES-256-GCM) in Postgres
- Tokens are decrypted only in-memory in `connection-proxy` pods (platform namespace)
- Customer pods never see OAuth tokens — they authenticate with their proxy token
- The connection-proxy verifies that the requested provider connection belongs to the authenticated customer

### Scope Control

- Platform registers OAuth apps with minimum necessary scopes
- Customers can request additional scopes during connection (subset of what the provider allows)
- The proxy does not allow scope escalation at request time

### Audit Trail

- Every proxied request is logged in `connection_usage_events`
- Logs include: customer_id, provider, HTTP method, path, status code, timestamp
- Request/response bodies are never logged (privacy)

### Connection Revocation

- Customer disconnects in dashboard → `connections.status = 'revoked'`
- Redis cache invalidated immediately
- Next proxy request for this connection returns 422 (no active connection)
- Platform also calls provider's token revocation endpoint if available

### Rate Limiting

- Per-customer, per-provider rate limiting: 60 req/min (configurable per provider)
- Prevents a runaway agent loop from burning through API quotas
- Returns 429 with retry-after header

---

## Tier Limits

| | Starter | Pro | Team |
|---|---|---|---|
| Max connections | 2 | 5 | 15 |
| Providers available | GitHub, Google | All | All |
| Connection API calls/month | 10,000 | 50,000 | 200,000 |

---

## Implementation Plan

### Phase 1: Core Proxy + GitHub (1-2 weeks)

1. `connections` table migration
2. `connection-proxy` FastAPI service (proxy logic + token refresh)
3. Encryption module (AES-256-GCM)
4. GitHub as first provider (popular, no token expiry = simpler)
5. API routes: authorize, callback, list, delete
6. Operator: update NetworkPolicy to allow connection-proxy egress
7. Operator: update pod Secret with `OPENCLAW_CONNECTIONS`
8. End-to-end test: connect GitHub → agent lists repos

### Phase 2: Google + Token Refresh (1 week)

9. Google OAuth (Drive, Sheets, Docs) — tests the refresh flow
10. Background refresh worker (proactive refresh for expiring tokens)
11. Redis locking for concurrent refresh safety
12. Error → reauth flow in dashboard

### Phase 3: More Providers + Dashboard (1-2 weeks)

13. Slack, Linear, Notion, Jira providers
14. Dashboard connections page (Next.js)
15. Connection usage metrics (Prometheus)
16. Tier limit enforcement

---

## Files to Create

```
apps/connection-proxy/
├── pyproject.toml
├── openclaw_connection_proxy/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + proxy route
│   ├── config.py                # Load providers.yaml + env config
│   ├── encryption.py            # AES-256-GCM encrypt/decrypt
│   ├── providers.yaml           # Provider definitions
│   ├── auth.py                  # Proxy token authentication (shared with token-proxy)
│   ├── oauth.py                 # OAuth code exchange + token refresh
│   ├── refresh_worker.py        # Background proactive refresh
│   └── models.py                # Connection DB model

db/migrations/
└── 002_connections.sql           # connections + connection_usage_events tables

k8s/services/
└── connection-proxy.nix          # K8s Deployment + Service + HPA

apps/api/openclaw_api/routes/
└── connections.py                # /me/connections/* + /oauth/callback routes
```

---

## API Key Connections

Not all services use OAuth. Many powerful APIs (OpenAI, Anthropic, Stripe, Twilio, custom internal APIs) use static API keys. We support these as a `secret_text` connection type.

### How It Works

Instead of an OAuth popup, the customer pastes their API key in the dashboard. The key is encrypted and stored identically to OAuth tokens — the agent never sees the raw key.

```
1. Customer clicks "Add API Key" for a provider (e.g., "Custom API")
2. Dashboard shows a form: name, base URL, API key, auth header format
3. api encrypts the key (AES-256-GCM) and stores in connections table
4. Agent calls connection-proxy the same way as OAuth connections
5. Proxy injects the key as Authorization header (or custom header)
```

### Provider Config for API Key Services

```yaml
# In providers.yaml
openai:
  display_name: OpenAI
  auth_mode: api_key
  proxy_base_url: https://api.openai.com
  auth_header: "Authorization"
  auth_prefix: "Bearer "    # key is sent as "Bearer sk-..."

custom:
  display_name: Custom API
  auth_mode: api_key
  proxy_base_url: null       # customer provides the base URL
  auth_header: "Authorization"
  auth_prefix: "Bearer "
```

### Dashboard UI

```
┌─────────────────────────────────────────────────────────┐
│  Add API Key Connection                                  │
│                                                          │
│  Name:      My Company Internal API                      │
│  Base URL:  https://api.mycompany.com/v1                │
│  API Key:   ●●●●●●●●●●●●●●●●●●●●●●  [paste]           │
│  Auth Header: Authorization  (default)                   │
│  Auth Format: Bearer {key}   (default)                   │
│                                                          │
│  [Connect]                                               │
└─────────────────────────────────────────────────────────┘
```

### Schema Addition

The `connections` table already supports this — `auth_mode` is stored in the `provider` config, and `encrypted_data` holds `{"api_key": "sk-..."}` instead of OAuth tokens. No schema changes needed, just different proxy behavior (no refresh logic for API keys).

---

## Runtime Connection Requests (Deep Links)

When an agent encounters a request that requires a service the customer hasn't connected, it doesn't just say "go to the dashboard" — it sends a **direct deep link** that starts the OAuth flow for that specific provider.

### Flow

```
1. User (via Telegram): "check my Slack messages"

2. Agent checks OPENCLAW_CONNECTIONS — no Slack connection.

3. Agent responds:
   "I don't have access to Slack yet. Connect it here and I'll
    be able to read your channels:

    → https://app.openclaw.cloud/connect/slack?token={short_lived_token}

    Once you connect, just ask me again."

4. User clicks the link on their phone → opens browser →
   OAuth popup for Slack → authorizes → done.

5. connection-proxy picks up the new connection immediately
   (no pod restart needed — the proxy checks connections on
   every request).

6. User asks again: "check my Slack messages" → works.
```

### Deep Link Token

The link contains a short-lived token (15min TTL, stored in Redis) that:
- Identifies the customer (no login required if they're clicking from Telegram)
- Specifies the provider to connect
- Redirects back to a "success" page after OAuth completes

```
GET /connect/{provider}?token={connect_token}
  → Validates connect_token (Redis lookup)
  → Starts OAuth flow for that provider
  → On success: shows "Connected! Go back to Telegram."
  → On failure: shows error with retry option
```

### API Route

```
POST /internal/connect-link
  body: { customer_id, provider }
  → Generates a short-lived connect token
  → Returns { url: "https://app.openclaw.cloud/connect/slack?token=abc123" }
```

The agent calls this internal route (via the connection-proxy) to generate the link on the fly.

### Agent System Prompt Addition

```
If a user asks for something that requires a service you're not connected to,
generate a connection link by calling:
  POST http://connection-proxy.platform.svc.cluster.local:8081/internal/connect-link
  body: {"provider": "slack"}

Include the returned URL in your response so the user can connect with one tap.
```

This is a real differentiator — the agent actively helps the user expand its own capabilities. No need to explain "go to settings, find connections, click the button." One tap from Telegram and it's done.

---

## Rate Limiting

Keep it simple: **pass through provider 429s**. The proxy does not try to predict or enforce provider-side rate limits. If GitHub returns 429, we pass it to the agent, and the agent tells the user "GitHub is rate-limiting us, try again in a minute."

The only rate limiting we enforce ourselves is the per-customer, per-provider limit (60 req/min) to prevent runaway agent loops. This is purely a safety net, not a provider-aware system.

---

## Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| API keys in addition to OAuth? | **Yes** | Many useful services (OpenAI, internal APIs, Stripe) use static keys. Same proxy model, just skip the refresh logic. |
| Runtime connection requests? | **Yes** | Key differentiator. Agent sends a deep link in Telegram — one tap to connect a new service. No dashboard navigation needed. |
| Provider-side rate limits? | **Pass through 429s** | Simpler. Don't try to be smarter than the provider. Just enforce our own safety-net limit (60 req/min). |
| Multi-account per provider? | **No, one connection per provider** | Keeps it simple. The current `UNIQUE (customer_id, provider)` constraint stays. Revisit if customers ask for it. |
