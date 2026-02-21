# openclaw-cloud — Overview

> **One chat. One agent. Zero setup.**
> A fully managed SaaS that provisions a personal OpenClaw AI agent for anyone, no coding required.

---

## What is this?

`openclaw-cloud` is a multi-tenant SaaS platform that sells managed OpenClaw instances to non-technical users. A user starts a chat with an onboarding AI agent, answers a few natural-language questions, pays via Stripe, and within **seconds** has their own fully configured OpenClaw agent running — accessible via Telegram.

---

## Core Design Decisions

### 1. K8s pods per customer (not dedicated VMs)

OpenClaw is a lightweight process (~64–256 MB RAM, mostly idle). It talks to Telegram and Kimi over HTTPS — that's it. It does not need a dedicated kernel, systemd, or a full NixOS install.

Each customer gets a **dedicated Kubernetes namespace** (`customer-{id}`) with a single OpenClaw pod. Resource quotas per namespace enforce tier limits. Provisioning takes **seconds** (`kubectl apply`), not 10 minutes.

At ~50–100 pods per worker node, a small 3-node K3s cluster handles hundreds of customers. Scaling to thousands means adding worker nodes — Colmena deploys them in minutes.

### 2. Full Nix stack — deterministic from node to pod

The entire infrastructure is a single Nix flake:

| Layer | Tool | What it does |
|---|---|---|
| K8s cluster nodes | NixOS + Colmena | Declarative fleet management of K3s nodes |
| K8s workloads | kubenix | Generates K8s manifests from Nix expressions |
| Container images | nix2container | Builds reproducible OCI images without Dockerfiles |

No Ansible. No Terraform state drift. No mystery `:latest` images. One `flake.lock` pins everything.

### 3. Token proxy — Kimi API key never leaves the control plane

Customer pods never hold a Kimi API key. All LLM traffic routes through our `token-proxy` service using a per-customer proxy token. The proxy meters usage, enforces hard monthly limits, and forwards with the platform's shared Kimi key.

### 4. Onboarding is 100% conversational

A Kimi-powered onboarding agent interviews the user, infers the right config, and triggers provisioning on payment. No forms, no TOML, no SSH.

---

## Technology Stack

| Concern | Choice |
|---|---|
| K8s distribution | K3s (on NixOS nodes) |
| Cluster management | Colmena |
| K8s manifests | kubenix |
| Container images | nix2container |
| Initial node provisioning | nixos-anywhere (cluster nodes only) |
| Per-customer provisioning | `kubectl apply` (operator service) |
| AI backend | Kimi Code (kimi-coding/k2p5) |
| Token metering proxy | Python (FastAPI) — Go rewrite when needed |
| API | FastAPI (Python) |
| Frontend | Next.js + Tailwind + shadcn/ui |
| Database | PostgreSQL (Supabase, Phase 1) |
| Queue | Redis |
| Billing | Stripe |
| Cloud | Hetzner Cloud |
| DNS | Cloudflare |

---

## Repository Layout

```
openclaw-cloud/
├── flake.nix                  # Single flake: Colmena + kubenix + nix2container
├── cluster.json               # Cluster IPs (gitignored — copy from cluster.example.json)
├── cluster.example.json       # Template for cluster.json
│
├── nodes/                     # NixOS configs for K8s cluster nodes (managed by Colmena)
│   ├── common.nix             # Shared: disk, SSH, Nix settings, K3s token secret
│   ├── control-plane.nix      # K3s server, etcd backups
│   └── worker.nix             # K3s agent
│
├── k8s/                       # kubenix: platform service manifests
│   ├── default.nix            # Entry point
│   ├── namespaces.nix
│   ├── infrastructure/
│   │   ├── redis.nix
│   │   └── ingress.nix
│   └── services/
│       ├── api.nix
│       ├── web.nix
│       ├── token-proxy.nix
│       ├── operator.nix
│       ├── onboarding-agent.nix
│       └── billing-worker.nix
│
├── images/
│   └── openclaw-gateway.nix   # nix2container image for customer pods
│
├── apps/
│   ├── api/                   # FastAPI — auth, boxes, usage, webhooks
│   ├── operator/              # Provisions/manages customer K8s namespaces + pods
│   ├── token-proxy/           # Kimi API metering proxy
│   ├── onboarding-agent/      # Conversational onboarding (Kimi + LangChain)
│   ├── billing-worker/        # Stripe webhook handler
│   └── web/                   # Next.js dashboard + marketing
│
├── db/
│   └── migrations/            # SQL migrations (Alembic)
│
├── secrets/                   # SOPS-encrypted cluster secrets (gitignored contents)
│
└── docs/                      # This document set
```

---

## Document Index

| Doc | Contents |
|---|---|
| `01-architecture.md` | Full system architecture + data flow |
| `02-onboarding-agent.md` | Conversational onboarding design + example flows |
| `03-provisioning.md` | Customer pod lifecycle: create → update → destroy |
| `04-token-proxy.md` | Token metering, hard limits, proxy design |
| `05-tiers-billing.md` | Pricing tiers, Stripe integration, enforcement |
| `06-kubernetes.md` | Colmena, kubenix, nix2container — the full Nix K8s stack |
| `07-security.md` | Namespace isolation, secrets, threat model |
| `08-data-model.md` | PostgreSQL schema |
| `09-roadmap.md` | Phased build plan |
| `diagrams/` | Architecture + flow diagrams |
