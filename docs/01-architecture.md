# Architecture

---

## Two Layers

```
┌─────────────────────────────────────────────────────────────┐
│            CONTROL PLANE  (K3s on NixOS, Hetzner)           │
│                                                             │
│   web · api · onboarding-agent · operator                   │
│   token-proxy · billing-worker · redis · postgres           │
└────────────────────────────┬────────────────────────────────┘
                             │  kubectl (in-cluster)
┌────────────────────────────▼────────────────────────────────┐
│            CUSTOMER PODS  (same K3s cluster)                │
│                                                             │
│   namespace: customer-abc123                                │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Deployment: openclaw-gateway                       │  │
│   │  Secret:     openclaw-config (Telegram token, etc.) │  │
│   │  ResourceQuota: per-tier CPU/memory limits          │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
│   namespace: customer-def456  (another customer)           │
│   ...                                                       │
└─────────────────────────────────────────────────────────────┘
```

The control plane and customer pods run on the **same K3s cluster**. Customer namespaces are isolated via K8s RBAC and NetworkPolicy — pods in `customer-abc123` cannot reach pods in `customer-def456` or the `platform` namespace (except `token-proxy`, which they call out to for Kimi API).

---

## Control Plane Services

### `api` (FastAPI)

The public-facing API and internal coordination hub.

- JWT auth (RS256, 1h access + 7d refresh)
- REST routes for customer dashboard (box status, usage)
- WebSocket endpoint relaying onboarding chat to/from `onboarding-agent`
- Stripe webhook endpoint (verified → forwarded to `billing-worker` via Redis)
- Internal routes used by `operator` and `token-proxy`

### `web` (Next.js)

- Marketing page + pricing
- Onboarding chat UI (streaming WebSocket)
- Customer dashboard: pod status, token usage gauge, billing link

### `onboarding-agent` (Python + LangChain + Kimi)

Runs the conversational onboarding flow. Maintains session state in Redis. On completion, outputs a structured config that the `api` uses to create a pending customer record and trigger Stripe checkout. See `02-onboarding-agent.md`.

### `operator` (Python)

Watches a Redis job queue and manages the K8s resources for each customer:

- **provision**: create namespace, Secret, ResourceQuota, Deployment
- **update**: patch Secret or Deployment (config changes from dashboard)
- **destroy**: delete namespace (cascades to all resources)
- **suspend**: scale Deployment replicas to 0
- **reactivate**: scale Deployment replicas back to 1

The operator runs **in-cluster** with a ServiceAccount that has ClusterRole permissions to manage namespaces, secrets, and deployments. No SSH, no nixos-anywhere, no external VMs per customer.

### `token-proxy` (FastAPI)

Transparent HTTP proxy between customer pods and Kimi API. Customer pods are configured to call `http://token-proxy.platform.svc.cluster.local:8080/v1` — this is the only way they can reach the LLM. See `04-token-proxy.md`.

### `billing-worker` (Python)

Stripe webhook processor. Translates Stripe events into operator jobs. See `05-tiers-billing.md`.

---

## Customer Pod Anatomy

When a customer is provisioned, the operator creates these resources in `customer-{id}`:

```
namespace: customer-{id}
│
├── Secret: openclaw-config
│   ├── TELEGRAM_BOT_TOKEN:     {customer's bot token}
│   ├── TELEGRAM_ALLOW_FROM:    {customer's Telegram user ID}
│   ├── KIMI_API_KEY:           {per-customer proxy token}
│   ├── KIMI_BASE_URL:          http://token-proxy.platform.svc.cluster.local:8080/v1
│   ├── OPENCLAW_MODEL:         kimi-coding/k2p5
│   └── OPENCLAW_THINKING:      medium
│
├── ResourceQuota: tier-limits
│   ├── requests.cpu:    250m   (Starter) | 500m  (Pro) | 1000m (Team)
│   ├── requests.memory: 128Mi  (Starter) | 256Mi (Pro) | 512Mi (Team)
│   ├── limits.cpu:      500m   (Starter) | 1000m (Pro) | 2000m (Team)
│   └── limits.memory:   256Mi  (Starter) | 512Mi (Pro) | 1Gi   (Team)
│
└── Deployment: openclaw-gateway
    └── Pod: openclaw-gateway-{hash}
        └── Container: openclaw-gateway
            image: ghcr.io/.../openclaw-gateway:latest  (nix2container build)
            envFrom: secretRef openclaw-config
```

The `openclaw-gateway` image is built with `nix2container` from `images/openclaw-gateway.nix`. It contains only the OpenClaw binary and CA certificates — no shell, no package manager, no OS cruft.

---

## Data Flow: Customer Message → LLM Response

```
Telegram user
    │  sends message to their bot
    ▼
Telegram servers
    │  webhook / polling
    ▼
customer pod (openclaw-gateway)
    │  POST /v1/chat/completions
    │  Authorization: Bearer {proxy-token}
    ▼
token-proxy (platform namespace, internal K8s DNS)
    │  1. authenticate proxy-token → customer_id
    │  2. check Redis: tokens_used < tokens_limit
    │  3. forward to Kimi API with platform key
    │  4. stream response back
    │  5. async: record token usage
    ▼
Kimi API (api.moonshot.cn)
    │  response
    ▼
token-proxy → customer pod → Telegram → user
```

---

## Nix Build Pipeline

```
flake.nix
├── Colmena (cluster node configs)
│   └── colmena apply → SSH → nixos-rebuild on each NixOS node
│
├── kubenix (platform manifests)
│   └── nix build .#k8s-manifests → YAML → kubectl apply
│
└── nix2container (customer pod image)
    └── nix build .#openclaw-image → OCI image → push to ghcr.io
```

All three outputs are produced from the same `flake.lock`. One `nix flake update` upgrades everything in lockstep. One `git revert` rolls everything back.

---

## Network Policy

Customer pods have restricted networking enforced by K8s NetworkPolicy:

```
customer-{id} namespace:
  ALLOW egress  → token-proxy.platform (port 8080)     # Kimi API via proxy
  ALLOW egress  → api.telegram.org (port 443)           # Telegram
  DENY  egress  → all other destinations
  DENY  ingress → all (no inbound connections)
  DENY  egress  → platform namespace (except token-proxy)
  DENY  egress  → other customer-* namespaces
```

Customer pods cannot reach the `api`, `operator`, `redis`, or `postgres` services. They can only call the token-proxy (for Kimi) and Telegram (for bot traffic).

---

## Failure Modes

| Failure | Impact | Recovery |
|---|---|---|
| Customer pod crashes | Telegram bot offline | K8s restarts pod automatically (restartPolicy: Always) |
| `token-proxy` pod crash | All Kimi calls fail | 3 replicas + HPA; pod restarts automatically |
| `operator` pod crash | Provisioning jobs queue up | Redis queue persists; operator drains queue on restart |
| K8s worker node crash | Pods rescheduled to other workers | K8s default behavior; takes ~1–2 min |
| Kimi API outage | All agent calls fail | Proxy returns 503; agents tell users "AI unavailable" |
| Postgres unavailable | API + proxy degrade | Proxy uses Redis cache for limit checks (60s TTL) |
