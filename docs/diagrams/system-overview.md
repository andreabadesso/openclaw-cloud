# System Architecture Diagram

```
                    ┌──────────────────────────────────────────────────┐
                    │              HETZNER CLOUD CLUSTER                │
                    │                                                  │
                    │  ┌─────────────────────────────────────────────┐ │
                    │  │         K3s Control Plane (NixOS)           │ │
                    │  │         managed by Colmena                  │ │
                    │  └─────────────────────────────────────────────┘ │
                    │                                                  │
                    │  ┌──────────────────┐  ┌──────────────────────┐ │
                    │  │  Worker Node 1   │  │  Worker Node 2       │ │
                    │  │  (NixOS+K3s)     │  │  (NixOS+K3s)         │ │
                    │  │                  │  │                      │ │
                    │  │ ┌─────────────┐  │  │ ┌──────────────────┐ │ │
                    │  │ │  namespace  │  │  │ │   namespace      │ │ │
                    │  │ │  platform   │  │  │ │   customer-abc   │ │ │
                    │  │ │             │  │  │ │                  │ │ │
                    │  │ │ api         │  │  │ │ openclaw pod     │ │ │
                    │  │ │ web         │  │  │ │ (nix2container   │ │ │
                    │  │ │ token-proxy │  │  │ │  image)          │ │ │
                    │  │ │ operator    │  │  │ └──────────────────┘ │ │
                    │  │ │ onboarding  │  │  │ ┌──────────────────┐ │ │
                    │  │ │ billing     │  │  │ │   namespace      │ │ │
                    │  │ │ redis       │  │  │ │   customer-def   │ │ │
                    │  │ └─────────────┘  │  │ │                  │ │ │
                    │  └──────────────────┘  │ │ openclaw pod     │ │ │
                    │                        │ └──────────────────┘ │ │
                    │                        └──────────────────────┘ │
                    └──────────────────────────────────────────────────┘
                              │                       │
                     Customer pods call          Ingress exposes
                     token-proxy via             api / web / proxy
                     K8s internal DNS            to the internet
                              │                       │
                    ┌─────────▼──────────┐   ┌────────▼──────────┐
                    │    Kimi API        │   │   Telegram /       │
                    │  (api.moonshot.cn) │   │   Stripe / Users   │
                    └────────────────────┘   └───────────────────┘
```

---

## Nix Build Pipeline

```
flake.nix  (single source of truth, pinned by flake.lock)
     │
     ├── colmena output
     │       │
     │       └── colmena apply ──SSH──► NixOS node
     │                                  nixos-rebuild switch
     │
     ├── packages.k8s-manifests  (kubenix)
     │       │
     │       └── nix build .#k8s-manifests
     │               │
     │               └── kubectl apply -f result/
     │
     └── packages.openclaw-image  (nix2container)
             │
             └── nix build .#openclaw-image
                     │
                     └── push to ghcr.io
                             │
                             └── customer pods pull image
```

---

## Onboarding Flow

```
  User                    Web / Telegram           Onboarding Agent         Control Plane
   │                            │                        │                       │
   │  "I want an AI agent"      │                        │                       │
   ├───────────────────────────►│                        │                       │
   │                            │  new session           │                       │
   │                            ├───────────────────────►│                       │
   │◄───────────────────────────┤  "Hey! What do you     │                       │
   │  "What should it help with?│   want it to help...?" │                       │
   │                            │                        │                       │
   │  "Help me write Python     │                        │                       │
   │   and review my PRs"       │                        │                       │
   ├───────────────────────────►├───────────────────────►│                       │
   │                            │                        │ [gathers: use case,   │
   │                            │                        │  Telegram token,      │
   │                            │                        │  user ID, tier]       │
   │◄───────────────────────────┤ "Here's your setup:    │                       │
   │  tier recommendation       │  Pro · $49/mo          │                       │
   │  + payment prompt          │  5M tokens/mo"         │                       │
   │                            │                        │                       │
   │  [Stripe checkout]         │                        │                       │
   ├───────────────────────────►│                        │  POST /provision      │
   │                            ├────────────────────────┼──────────────────────►│
   │                            │                        │                       │ create namespace
   │                            │                        │                       │ create K8s Secret
   │                            │                        │                       │ kubectl apply Deployment
   │                            │                        │                       │ wait for pod Ready
   │◄───────────────────────────┤  "Your agent is live!  │                       │
   │                            │   Message @yourbot"    │                       │
```

---

## Token Proxy Flow

```
  Customer Pod              token-proxy              Redis / Postgres        Kimi API
  (openclaw-gateway)             │                        │                    │
        │                        │                        │                    │
        │  POST /v1/chat/...     │                        │                    │
        │  Authorization:        │                        │                    │
        │    Bearer {proxy-token}│                        │                    │
        ├───────────────────────►│                        │                    │
        │                        │  GET limit:{cust_id}   │                    │
        │                        ├───────────────────────►│                    │
        │                        │◄───────────────────────┤                    │
        │                        │  {used:400k,limit:5M}  │                    │
        │                        │                        │                    │
        │                        │  [within limit]        │                    │
        │                        ├────────────────────────────────────────────►│
        │                        │◄────────────────────────────────────────────┤
        │                        │  {response, usage:{prompt:1200,compl:800}} │
        │                        │                        │                    │
        │                        │  async: usage += 2000  │                    │
        │                        ├───────────────────────►│                    │
        │◄───────────────────────┤                        │                    │
        │  {completion}          │                        │                    │
        │                        │                        │                    │
        │  [over limit → 429]    │                        │                    │
        │◄───────────────────────┤                        │                    │

```

---

## Provisioning Flow (Operator)

```
  billing-worker         Redis queue          Operator           K8s API
       │                      │                  │                  │
       │  [Stripe payment OK] │                  │                  │
       │  LPUSH operator:jobs │                  │                  │
       ├─────────────────────►│                  │                  │
       │                      │  BLPOP job       │                  │
       │                      ├─────────────────►│                  │
       │                      │                  │  create namespace │
       │                      │                  ├─────────────────►│
       │                      │                  │  create Secret    │
       │                      │                  ├─────────────────►│
       │                      │                  │  create Quota     │
       │                      │                  ├─────────────────►│
       │                      │                  │  create NetPolicy │
       │                      │                  ├─────────────────►│
       │                      │                  │  create Deployment│
       │                      │                  ├─────────────────►│
       │                      │                  │  poll pod Ready   │
       │                      │                  ├─────────────────►│
       │                      │                  │◄─────────────────┤
       │                      │                  │  {ready: true}    │
       │                      │                  │                  │
       │◄─────────────────────┴──────────────────┤                  │
       │  notify: customer active                 │                  │
       │  (WebSocket + email)                     │                  │
```
