# Implementation Roadmap

---

## Phase 0 — Manual MVP (Week 1–2) ✅

**Goal**: Prove people will pay. Do everything manually. Write zero platform code.

1. Static landing page
2. Typeform for onboarding: collect Telegram token, use case, Telegram user ID
3. Stripe Payment Link for each tier
4. Manually provision: spin up K8s pod, inject secrets
5. Email the customer when their bot is live

**Status**: Complete. Moved on to automated platform.

---

## Phase 1 — K8s Platform + Automated Provisioning ✅

**Goal**: Automate everything. Remove yourself from the loop.

### Cluster Bootstrap ✅

- [x] k3d local dev cluster (matching prod architecture)
- [x] kubenix for all K8s manifests (typed Nix → JSON)
- [x] nix2container for gateway image
- [x] Platform namespace with all services deployed in-cluster
- [x] NodePort services for local access

### OpenClaw Gateway Image ✅

- [x] `images/openclaw-gateway.nix` — nix2container image with entrypoint
- [x] Entrypoint: reads env vars → builds `openclaw.json` config → starts gateway
- [x] Bootstrap files: `SOUL.md`, `TOOLS.md`, `IDENTITY.md` for agent behavior
- [x] Dynamic connection discovery via API (agents curl the connections endpoint)
- [x] Browser profile config from `OPENCLAW_BROWSER_PROXY_URL`
- [x] MCP integration via mcporter config generation

### Operator ✅

- [x] Postgres schema: customers, boxes, subscriptions, proxy_tokens, usage_monthly, operator_jobs
- [x] Redis job queue (BLPOP consumer)
- [x] Jobs: provision, destroy, suspend, reactivate, resize, update_connections
- [x] Per-customer: namespace, secret, deployment, resource quota, network policy
- [x] Scale 0 → scale 1 for rolling updates (quota-safe)
- [x] Pod metrics collection (K8s metrics API → Postgres)

### Token Proxy ✅

- [x] Node.js + pi-ai (provider abstraction layer)
- [x] Proxy token auth (bcrypt-hashed, Redis-cached)
- [x] Usage recording (Redis stream → batch Postgres writes)
- [x] Hard limit enforcement (429 response)
- [x] Rate limiting (token bucket, 10 req/s per customer)
- [x] OpenAI `developer` role message support
- [x] Full tool call streaming (`toolcall_start`/`toolcall_delta` → OpenAI format)
- [x] Non-streaming tool call support with `finish_reason: "tool_calls"`

### API ✅

- [x] FastAPI + SQLAlchemy (async)
- [x] Provisioning endpoints (internal + admin)
- [x] Customer connections management (list, authorize, confirm, delete, reconnect)
- [x] Agent API: `GET /internal/agent/connections`, `POST /internal/agent/connect-link`
- [x] Connect link deep-link flow with `web_url` config (LAN/SSH tunnel friendly)
- [x] Usage tracking endpoints
- [x] Stripe webhook endpoint

### Billing Worker ✅

- [x] `checkout.session.completed` → create subscription → enqueue provision
- [x] `invoice.payment_succeeded` → reset token counter, reactivate if suspended
- [x] `invoice.payment_failed` → suspend after 3 failures
- [x] `customer.subscription.updated` → enqueue resize
- [x] `customer.subscription.deleted` → enqueue destroy

---

## Phase 1.5 — External Integrations ✅

### Nango OAuth ✅

- [x] Self-hosted Nango instance (in-cluster)
- [x] 6 providers configured: GitHub, Google, Slack, Linear, Notion, Jira
- [x] Native integrations: env var injection (GH_TOKEN, NOTION_API_KEY, SLACK_BOT_TOKEN)
- [x] MCP integrations: mcporter config generation (Linear, Jira, Google)
- [x] Connect sessions via `@nangohq/frontend` SDK
- [x] Dashboard connections page (provider grid, connect/disconnect/reconnect)
- [x] Deep-link connect page (`/en/connect/{provider}?token=...`) for agent-initiated OAuth
- [x] Connection sync: customer_connections table → operator job → pod secret update → restart

### Browser Proxy ✅

- [x] Node.js + ws (CDP WebSocket proxy)
- [x] HTTP `/json/*` forwarding with URL rewriting
- [x] WebSocket `/devtools/*` bidirectional piping
- [x] Per-customer auth (proxy token as Basic auth)
- [x] Session limits (max 2 concurrent, 10 min max duration)
- [x] Usage tracking: Redis stream → Postgres `browser_sessions` table
- [x] Gateway auto-config via `OPENCLAW_BROWSER_PROXY_URL`

### Web Frontend ✅

- [x] Next.js 14 + Tailwind CSS + shadcn/ui
- [x] next-intl (Portuguese BR default, English)
- [x] Niche agent marketplace landing page
- [x] Customer dashboard (connections, usage)
- [x] Deep-link OAuth connect page (Nango frontend SDK)
- [x] Admin panel
- [x] API proxy rewrites (no CORS issues from LAN)

---

## v1.0.0-beta — Tagged 2026-02-22 🏷️

Everything above is complete and working end-to-end. Agent can:
- Respond via Telegram with domain knowledge
- Make tool calls through the token proxy
- Browse the web via CDP proxy
- Discover and request OAuth connections at runtime
- Access external services (GitHub, Google, Slack, etc.) via native tools or MCP

---

## Phase 2 — Production Ready (Next)

**Goal**: Ship to real users. Harden, monitor, deploy.

### Authentication & Security
- [ ] JWT RS256 authentication (replace placeholder X-Customer-Id header)
- [ ] External Secrets Operator or SOPS-encrypted platform-secrets
- [ ] Rate limiting on public API endpoints

### Production Deployment
- [ ] Provision Hetzner VMs (control plane + workers)
- [ ] Colmena node configs (`nodes/common.nix`, `nodes/control-plane.nix`, `nodes/worker.nix`)
- [ ] cert-manager + ingress-nginx (HTTPS)
- [ ] DNS setup (openclaw.cloud)
- [ ] ghcr.io image registry access from prod cluster
- [ ] SOPS for K3s token + all secrets

### Monitoring & Reliability
- [ ] Per-customer analytics dashboard (CPU, memory, token usage, browser sessions)
- [ ] Health monitoring + auto-restart for gateway pods
- [ ] Prometheus + Grafana monitoring stack
- [ ] AlertManager → Slack notifications

### Onboarding
- [ ] Conversational onboarding agent (web chat + Telegram)
- [ ] Session state machine in Redis
- [ ] Provisioning progress stream (WebSocket events)

---

## Phase 3 — Growth (Later)

- [ ] Additional niches (legal, real estate, accounting)
- [ ] Customer self-serve dashboard (change model, thinking level, Telegram users)
- [ ] Stripe Customer Portal integration
- [ ] Email notifications (provisioned, 90% token warning, payment failure)
- [ ] Multi-region deployment
- [ ] Automatic worker node scaling

---

## Key Decisions

- **K8s pods, not VMs** — per-customer isolation with much lower overhead
- **Token proxy pattern** — customer pods never hold real API keys
- **Nango for OAuth** — self-hosted, handles 600+ providers, automatic token refresh
- **Bootstrap files over system prompt** — SOUL.md/TOOLS.md/IDENTITY.md give the agent structured behavior
- **pi-ai for LLM abstraction** — provider-agnostic, handles streaming + tool calls
- **mcporter for MCP** — lightweight stdio/HTTP bridge for MCP servers
- **kubenix for manifests** — typed Nix, no YAML drift, single `nix build` for all resources

---

## Definition of Done

A shippable product is when:

1. Someone discovers openclaw-cloud
2. Starts a chat (web or Telegram)
3. Answers 5–7 questions naturally
4. Pays with a credit card
5. Has a working AI agent on Telegram within 60 seconds
6. You did nothing manually
7. Their usage is metered and enforced
8. If they cancel, the pod is gone within minutes
