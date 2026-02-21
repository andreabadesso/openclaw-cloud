# openclaw-cloud

**One chat. One agent. Zero setup.**

A fully managed SaaS platform that provisions personal [OpenClaw](https://openclaw.ai) AI agents for anyone — no coding required. Users get their own isolated AI agent running on Kubernetes, accessible via Telegram, provisioned in seconds.

---

## How it works

```
User visits site  ──>  Picks a plan  ──>  Enters Telegram details
                                                    │
                                                    v
                                         API creates customer
                                         + queues provision job
                                                    │
                                                    v
                                          Operator picks up job
                                          from Redis queue
                                                    │
                                    ┌───────────────┼───────────────┐
                                    v               v               v
                              K8s Namespace    K8s Secret     K8s Deployment
                              + ResourceQuota  (bot token,    (openclaw-gateway
                              + NetworkPolicy   proxy token,   container)
                                                model config)
                                                    │
                                                    v
                                          Pod starts in ~4 seconds
                                          Telegram bot goes live
```

Each customer gets a **dedicated Kubernetes namespace** with full isolation: resource quotas, network policies, and a unique proxy token for AI API access. Customer pods never hold real API keys.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Control Plane                            │
│                                                                 │
│  ┌────────┐ ┌────────┐ ┌──────────┐ ┌───────────┐ ┌───────────┐│
│  │  Web   │ │  API   │ │ Operator │ │Token Proxy│ │   Nango   ││
│  │Next.js │─│FastAPI │─│ (Python) │ │ (FastAPI) │ │  (OAuth)  ││
│  │ :3000  │ │ :8000  │ │          │ │   :8080   │ │   :3003   ││
│  └────────┘ └───┬────┘ └────┬─────┘ └─────┬─────┘ └─────┬─────┘│
│                 │           │              │              │      │
│          ┌──────┴──────┐ ┌──┴───┐         │              │      │
│          │  PostgreSQL │ │Redis │         │              │      │
│          │    :5432    │ │:6379 │         │              │      │
│          └─────────────┘ └──────┘         │              │      │
└───────────────────────────────────────────┼──────────────┼──────┘
                                                      │
┌─────────────────────────────────────────────────────┼──────────┐
│                    K8s Cluster (K3s)                 │          │
│                                                     │          │
│  ┌─ customer-abc123 ──────────────────────────┐     │          │
│  │  Namespace + ResourceQuota + NetworkPolicy  │     │          │
│  │  ┌──────────────────────┐                   │     │          │
│  │  │  openclaw-gateway    │  ── Kimi API ──>──┼─────┘          │
│  │  │  (Telegram bot +     │     via proxy                      │
│  │  │   AI agent)          │     token                          │
│  │  └──────────────────────┘                   │                │
│  └─────────────────────────────────────────────┘                │
│                                                                 │
│  ┌─ customer-def456 ──────────┐                                 │
│  │  (another isolated pod)    │                                 │
│  └────────────────────────────┘                                 │
│                                                                 │
│  ┌─ customer-ghi789 ──────────┐                                 │
│  │  (another isolated pod)    │                                 │
│  └────────────────────────────┘                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Services

| Service | Tech | Purpose |
|---|---|---|
| **web** | Next.js 14, Tailwind, shadcn/ui | Landing page, admin panel, customer dashboard |
| **api** | Python, FastAPI | REST API for auth, provisioning, box management, agent connections |
| **operator** | Python, kubernetes client | Watches Redis queue, manages K8s resources per customer |
| **token-proxy** | Python, FastAPI | Proxies AI API calls with per-customer tokens, metering, rate limiting |
| **nango-server** | [Nango](https://nango.dev) (self-hosted) | OAuth proxy for 600+ external services (GitHub, Slack, etc.) |
| **postgres** | PostgreSQL 16 | Customers, subscriptions, boxes, usage, jobs, connections |
| **redis** | Redis 7 | Job queue (operator), rate limiting, caching |

### Key Design Decisions

- **K8s pods per customer** (not VMs) — OpenClaw is lightweight (~512MB RAM). At ~50-100 pods per worker node, a small cluster handles hundreds of customers.
- **Full Nix stack** — Single flake pins everything: NixOS nodes (Colmena), K8s manifests (kubenix), container images (nix2container). No drift.
- **Token proxy pattern** — Customer pods never hold the real AI API key. All LLM traffic goes through the proxy with per-customer tokens, metering, and hard monthly limits.
- **Nango for OAuth** — Self-hosted [Nango](https://nango.dev) handles OAuth flows, token refresh, and encrypted credential storage for 600+ external services. Agents call external APIs through the Nango proxy with automatic token management.
- **Seconds to provision** — Creating a namespace + secret + deployment is near-instant vs. minutes for a VM.

---

## Tech Stack

| Concern | Choice |
|---|---|
| K8s distribution | K3s (on NixOS nodes) |
| Cluster management | Colmena |
| K8s manifests | kubenix |
| Container images | nix2container |
| AI backend | Kimi Code (kimi-coding/k2p5) |
| API | FastAPI (Python) |
| Frontend | Next.js 14 + Tailwind + shadcn/ui |
| Database | PostgreSQL 16 |
| Queue | Redis 7 |
| Billing | Stripe (planned) |
| Cloud | Hetzner Cloud |

---

## Pricing Tiers

| | Starter | Pro | Team |
|---|---|---|---|
| **Price** | $19/mo | $49/mo | $129/mo |
| **Monthly tokens** | 1,000,000 | 5,000,000 | 20,000,000 |
| **CPU** | 250m req / 1000m limit | 500m / 2000m | 1000m / 4000m |
| **Memory** | 512Mi req / 1Gi limit | 512Mi / 1Gi | 1Gi / 2Gi |
| **Telegram users** | 1 | 1 | Up to 10 |

---

## Local Development

### Prerequisites

- [Nix](https://nixos.org/) with flakes enabled
- [Docker](https://www.docker.com/) + Docker Compose
- [k3d](https://k3d.io/) (or use `nix run nixpkgs#k3d`)

### Quick Start

```bash
# 1. Clone and enter dev shell
git clone git@github.com:andreabadesso/openclaw-cloud.git
cd openclaw-cloud
nix develop   # or: direnv allow

# 2. Copy env file
cp .env.example .env
# Edit .env — set KIMI_API_KEY to a real key for AI to work

# 3. Start infrastructure
docker compose up -d

# 4. Create local K8s cluster
nix run nixpkgs#k3d -- cluster create openclaw-dev \
  --agents 1 \
  --k3s-arg "--disable=traefik@server:0"

# 5. Build and load the OpenClaw gateway image into k3d
nix build .#openclaw-image.copyTo
# The output path contains a copy-to script:
result/bin/copy-to docker-archive:/tmp/oc.tar:ghcr.io/andreabadesso/openclaw-cloud/openclaw-gateway:latest
docker load -i /tmp/oc.tar
nix run nixpkgs#k3d -- image import \
  ghcr.io/andreabadesso/openclaw-cloud/openclaw-gateway:latest \
  --cluster openclaw-dev
rm /tmp/oc.tar

# 6. Connect operator to k3d
# Copy k3d kubeconfig for the operator container:
nix run nixpkgs#k3d -- kubeconfig get openclaw-dev > /tmp/operator-kubeconfig.yaml
# Restart operator to pick up kubeconfig
docker compose restart operator

# 7. Open the admin panel
open http://localhost:3000/admin
```

### Services & Ports

| Service | URL | Description |
|---|---|---|
| Web | http://localhost:3000 | Frontend (landing, admin, dashboard) |
| API | http://localhost:8000 | REST API |
| Token Proxy | http://localhost:8080 | AI API proxy |
| Nango | http://localhost:3003 | OAuth admin dashboard |
| PostgreSQL | localhost:5432 | Database |
| Redis | localhost:6379 | Queue & cache |

### Provisioning a Test Instance

From the admin panel at `/admin`, fill in:
- Customer email
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Telegram user ID (from [@userinfobot](https://t.me/userinfobot))
- Tier, model, thinking level

Or via curl:

```bash
curl -X POST http://localhost:8000/internal/provision \
  -H "Content-Type: application/json" \
  -d '{
    "customer_email": "user@example.com",
    "telegram_bot_token": "123456:ABC-DEF...",
    "telegram_user_id": 123456789,
    "tier": "starter",
    "model": "kimi-coding/k2p5",
    "thinking_level": "medium",
    "language": "en"
  }'
```

The operator picks up the job, creates the K8s namespace + resources, and the pod starts in ~4 seconds.

### Managing Instances

```bash
# List all customer pods
kubectl get pods --all-namespaces -l app=openclaw-gateway

# Check a specific customer's pod
kubectl logs -n customer-<uuid> -l app=openclaw-gateway

# Suspend via API
curl -X POST http://localhost:8000/internal/suspend/<box_id>

# Destroy via API
curl -X POST http://localhost:8000/internal/destroy/<box_id>
```

---

## Repository Structure

```
openclaw-cloud/
├── flake.nix                     # Nix flake: Colmena + kubenix + nix2container
├── cluster.example.json          # Template for cluster node IPs
├── docker-compose.yml            # Local dev orchestration
│
├── apps/
│   ├── api/                      # FastAPI — provisioning, box management, usage
│   │   └── openclaw_api/
│   │       ├── main.py           # App entry + CORS + router setup
│   │       ├── routes/
│   │       │   ├── internal.py   # /internal/provision, /suspend, /destroy, /boxes
│   │       │   ├── boxes.py      # /me/box — customer-facing
│   │       │   ├── usage.py      # /me/usage
│   │       │   └── connections.py# OAuth connections, agent API endpoints
│   │       ├── nango_client.py   # Async httpx Nango API wrapper
│   │       ├── models.py         # SQLAlchemy ORM models
│   │       └── schemas.py        # Pydantic request/response schemas
│   │
│   ├── operator/                 # K8s operator — provisions customer namespaces + pods
│   │   └── openclaw_operator/
│   │       ├── main.py           # BLPOP Redis queue, dispatch jobs
│   │       ├── k8s.py            # All K8s resource creation/management
│   │       ├── tiers.py          # Tier resource definitions
│   │       └── jobs/             # Job handlers
│   │           ├── provision.py  # Full provisioning flow
│   │           ├── destroy.py    # Namespace deletion
│   │           ├── suspend.py    # Scale to 0
│   │           ├── reactivate.py # Scale back to 1
│   │           ├── resize.py     # Tier change
│   │           ├── update.py     # Config updates
│   │           └── update_connections.py  # Sync connections to pod secret
│   │
│   ├── token-proxy/              # AI API metering proxy
│   │   └── token_proxy/
│   │       ├── main.py           # Proxy entry + /v1/chat/completions
│   │       ├── auth.py           # Per-customer proxy token auth
│   │       ├── proxy.py          # HTTP forwarding to Kimi API
│   │       ├── limits.py         # Monthly token limit enforcement
│   │       ├── rate_limit.py     # Redis token bucket rate limiter
│   │       ├── usage.py          # Async usage recording
│   │       └── internal.py       # /internal/tokens — token CRUD
│   │
│   ├── web/                      # Next.js frontend
│   │   └── src/
│   │       ├── app/
│   │       │   ├── page.tsx      # Landing page
│   │       │   ├── admin/        # Admin provisioning panel
│   │       │   ├── dashboard/    # Customer dashboard
│   │       │   └── onboarding/   # Onboarding flow (placeholder)
│   │       ├── components/       # Reusable UI components
│   │       └── lib/api.ts        # API client (proxied via Next.js rewrites)
│   │
│   └── shared/                   # Shared Python library
│       └── openclaw_shared/
│           ├── database.py       # Async SQLAlchemy engine + models
│           └── redis.py          # Redis client setup
│
├── images/
│   └── openclaw-gateway.nix      # nix2container image for customer pods
│
├── nodes/                        # NixOS configs for K3s cluster nodes
│   ├── common.nix                # Shared: disk, SSH, K3s token
│   ├── control-plane.nix         # K3s server
│   └── worker.nix                # K3s agent
│
├── k8s/                          # kubenix manifests for platform services
│   ├── namespaces.nix
│   ├── infrastructure/           # Redis, ingress
│   └── services/                 # API, web, operator, token-proxy, etc.
│
├── db/
│   └── migrations/
│       ├── 001_initial.sql       # Full schema: 8 tables, 6 enums
│       └── 002_connections.sql   # customer_connections table + job type
│
└── docs/                         # Design documents
    ├── 00-overview.md
    ├── 01-architecture.md
    ├── 02-onboarding-agent.md
    ├── 03-provisioning.md
    ├── 04-token-proxy.md
    ├── 05-tiers-billing.md
    ├── 06-kubernetes.md
    ├── 07-security.md
    ├── 08-data-model.md
    └── 09-roadmap.md
```

---

## Database Schema

9 tables covering the full lifecycle:

| Table | Purpose |
|---|---|
| `customers` | Customer records (email, Stripe ID) |
| `subscriptions` | Stripe subscription state per customer |
| `boxes` | One box per customer — K8s namespace, status, config |
| `proxy_tokens` | Per-customer tokens for the AI API proxy |
| `usage_monthly` | Monthly token consumption and limits |
| `usage_events` | Individual API call logs |
| `onboarding_sessions` | Conversational onboarding state machine |
| `operator_jobs` | Async job queue with status tracking |
| `customer_connections` | OAuth connections per customer (provider, Nango connection ID) |

---

## Nix Flake Outputs

```bash
# Build K8s manifests for platform services
nix build .#k8s-manifests

# Build the OpenClaw gateway container image
nix build .#openclaw-image

# Deploy NixOS cluster nodes
colmena apply

# Enter dev shell with all tools
nix develop
```

The dev shell includes: colmena, kubectl, k9s, helm, kubie, sops, age, jq, yq, python3.

---

## Production Deployment

The production cluster runs on Hetzner Cloud with NixOS nodes managed by Colmena:

```bash
# 1. Copy and fill in cluster IPs
cp cluster.example.json cluster.json

# 2. Deploy nodes
colmena apply

# 3. Build and push platform manifests
nix build .#k8s-manifests
kubectl apply -f result/

# 4. Build and push gateway image
nix build .#openclaw-image.copyTo
result/bin/copy-to docker://ghcr.io/andreabadesso/openclaw-cloud/openclaw-gateway:latest
```

---

## Roadmap

- [x] Core API + operator + token proxy
- [x] Admin provisioning panel
- [x] K8s pod lifecycle (provision, suspend, reactivate, destroy)
- [x] OpenClaw gateway container image (nix2container)
- [x] Local dev environment (Docker Compose + k3d)
- [x] Nango-powered OAuth connections (GitHub, Slack, Linear, Google, Notion, Jira)
- [x] Agent connection discovery API + deep-link generation
- [ ] JWT RS256 authentication
- [ ] Stripe billing integration
- [ ] Conversational onboarding agent (Kimi + LangChain)
- [ ] Health monitoring + auto-restart
- [ ] Production Hetzner deployment

---

## License

Proprietary. All rights reserved.
