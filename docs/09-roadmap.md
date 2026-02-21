# Implementation Roadmap

---

## Phase 0 — Manual MVP (Week 1–2)

**Goal**: Prove people will pay. Do everything manually. Write zero platform code.

1. Static landing page (Vercel, Carrd, whatever — doesn't matter)
2. Typeform for onboarding: collect Telegram token, use case, Telegram user ID
3. Stripe Payment Link for each tier
4. YOU manually provision: spin up a Hetzner VM, deploy `openclaw-box` with nixos-anywhere, inject their secrets
5. Email the customer when their bot is live

**What you learn**: What questions do users have? What do they actually use the agent for? What breaks? What tier do they naturally gravitate toward?

**Success criteria**: 5 paying customers. Real money. Real feedback. You have done everything manually and understand the pain you're automating.

---

## Phase 1 — K8s Platform + Automated Provisioning (Week 3–8)

**Goal**: Automate everything. Remove yourself from the loop.

### Week 3–4: Cluster Bootstrap

- [ ] Provision 3 Hetzner VMs (1 control plane, 2 workers)
- [ ] Write `nodes/common.nix`, `nodes/control-plane.nix`, `nodes/worker.nix`
- [ ] Set up SOPS for K3s token secret
- [ ] Deploy cluster with nixos-anywhere + Colmena
- [ ] Install cert-manager + ingress-nginx via Helm (or kubenix)
- [ ] Set up ghcr.io image registry access
- [ ] Verify K3s cluster is healthy (`kubectl get nodes`)

### Week 5: Build the OpenClaw Image

- [ ] Write `images/openclaw-gateway.nix` (nix2container)
- [ ] Build image: `nix build .#openclaw-image`
- [ ] Push to ghcr.io: `nix run .#openclaw-image.copyToRegistry`
- [ ] Manually test: `kubectl run test --image=ghcr.io/.../openclaw-gateway --env-file=test.env`
- [ ] Verify bot responds on Telegram

### Week 6: Operator + Provisioning

- [ ] Postgres schema: `customers`, `boxes`, `subscriptions`, `proxy_tokens`, `usage_monthly`, `operator_jobs`
- [ ] Redis running in-cluster
- [ ] `operator` service — implement `provision`, `destroy`, `suspend`, `reactivate` jobs
- [ ] Operator ClusterRole + ServiceAccount
- [ ] Token-proxy: register/revoke proxy tokens internal API
- [ ] End-to-end test: submit provision job to Redis → customer pod running → bot works

### Week 7: Token Proxy

- [ ] `token-proxy` FastAPI service
- [ ] Proxy token auth (Redis cache + Postgres lookup)
- [ ] Usage recording (async write to Postgres)
- [ ] Hard limit enforcement (429 response)
- [ ] Rate limiting (10 req/s per token)
- [ ] Deploy to cluster, configure ingress (`proxy.openclaw.cloud`)
- [ ] Update openclaw-gateway image to use proxy URL

### Week 8: API + Billing Worker

- [ ] `api` FastAPI: auth (JWT), `/me`, `/me/box`, `/me/usage`, Stripe webhook endpoint
- [ ] `billing-worker`: handle `checkout.session.completed` → enqueue provision job
- [ ] `billing-worker`: handle `invoice.payment_succeeded` → reset token counter
- [ ] `billing-worker`: handle `customer.subscription.deleted` → enqueue destroy job
- [ ] Stripe products + prices created in Stripe dashboard
- [ ] Manual end-to-end test: pay via Stripe → provision job enqueued → bot live

**Phase 1 exit criteria**: Customer pays on Stripe → bot is live on Telegram within 60 seconds. No human involvement.

---

## Phase 2 — Onboarding Agent (Week 9–12)

**Goal**: Replace the Typeform with a conversational AI flow.

### Week 9–10: Onboarding Agent Core

- [ ] `onboarding-agent` service (Python + LangChain + Kimi)
- [ ] Session state machine in Redis
- [ ] System prompt + conversation flow (see `02-onboarding-agent.md`)
- [ ] Telegram bot token validation
- [ ] Config JSON output → call API to create pending customer + trigger Stripe checkout
- [ ] WebSocket relay in `api` service (`/onboarding/chat/{session_id}`)

### Week 11: Onboarding UI

- [ ] `web` Next.js: chat interface with streaming WebSocket
- [ ] Session resume on reconnect (cookie → Redis session)
- [ ] Provisioning progress stream (WebSocket events during pod startup)
- [ ] "Your agent is live!" final screen with Telegram bot link

### Week 12: Telegram Onboarding

- [ ] Dedicated onboarding Telegram bot (`@OpenClawSetupBot`)
- [ ] Same onboarding-agent backend, Telegram transport
- [ ] Session resume via Telegram user ID
- [ ] Payment link sent via Telegram message after tier selection

**Phase 2 exit criteria**: Complete onboarding entirely through chat (web or Telegram), no forms.

---

## Phase 3 — Dashboard & Self-Serve (Week 13–16)

- [ ] Customer dashboard: pod status, token usage chart, billing link
- [ ] Agent settings editor (add/remove Telegram users, change model, change thinking level)
- [ ] `update` operator job wired to dashboard settings
- [ ] Stripe Customer Portal integration (plan change, cancel)
- [ ] Email notifications: provisioned, 90% token warning, payment failure, suspension
- [ ] Admin panel: list all customers, boxes, jobs, usage

**Phase 3 exit criteria**: Zero support tickets for "how do I change X?".

---

## Phase 4 — Reliability & Scale (Month 5–6)

- [ ] Prometheus + Grafana monitoring stack
- [ ] AlertManager → Slack + PagerDuty
- [ ] External Secrets Operator + Vault (replace manual `platform-secrets`)
- [ ] Automatic worker node scaling (Cluster Autoscaler for Hetzner)
- [ ] Load testing: 500 concurrent customer pods, 100 simultaneous provisioning jobs
- [ ] kubenix for all platform manifests (replace any remaining raw YAML)
- [ ] GitHub Actions CI: build images + manifests + deploy to staging + smoke test

---

## Key Files to Build First

This is the critical path. These files unblock everything else:

```
1. nodes/common.nix              → get the cluster running
2. images/openclaw-gateway.nix   → get the customer pod working
3. apps/token-proxy/main.py      → get Kimi calls metered
4. apps/operator/operator/main.py → get provisioning automated
5. db/migrations/001_initial.sql  → get the schema in place
6. apps/api/openclaw_api/main.py  → get auth + Stripe webhooks working
```

Everything else (web UI, onboarding agent, monitoring) is additive on top of this foundation.

---

## What Not to Build (Yet)

- Custom Telegram bot framework — openclaw-box's existing Telegram integration works
- Custom LLM inference — Kimi API is the right call at this scale
- Multi-region deployment — Hetzner single-region is fine until MRR > $50k
- Mobile app — Telegram is the mobile app
- Kubernetes operator (CRDs) for customer resources — the operator service + Redis queue is simpler and sufficient for thousands of customers

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
