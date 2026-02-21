# Tiers & Billing

---

## Pricing Tiers

| | Starter | Pro | Team |
|---|---|---|---|
| **Price** | $19/month | $49/month | $129/month |
| **Monthly tokens** | 1,000,000 | 5,000,000 | 20,000,000 |
| **CPU limit** | 500m | 1000m | 2000m |
| **Memory limit** | 256Mi | 512Mi | 1Gi |
| **Thinking level** | medium | medium | high |
| **Telegram users** | 1 | 1 | Up to 10 |
| **Custom system prompt** | — | ✓ | ✓ |
| **Support** | Community | Email 48h | Email 24h |

---

## Unit Economics

OpenClaw pods are lightweight (~50–100m CPU idle, ~100–150Mi RAM). Hosting cost is shared across all pods on the cluster.

| | Starter | Pro | Team |
|---|---|---|---|
| Revenue | $19 | $49 | $129 |
| Hosting (est. per pod) | ~$0.50 | ~$1.00 | ~$2.00 |
| Kimi tokens (est.) | ~$2 | ~$8 | ~$28 |
| **Gross margin** | **~87%** | **~82%** | **~77%** |

Kimi token cost estimate at $2/1M tokens. Hosting cost based on ~80 Starter pods / cx41 worker node at €16/mo.

This is substantially better than the dedicated-VM model. A cx41 worker node can carry ~80 Starter customers before you need another node.

---

## Token Overage Policy

When a customer hits their limit, the token-proxy returns `429`. OpenClaw tells the user: *"I've reached my monthly AI limit. You can upgrade at app.openclaw.cloud/billing."*

No automatic overages. No surprise bills. Customers upgrade or wait for the next billing period.

**Phase 2**: opt-in overage billing at $3/1M tokens (Starter/Pro) or $2/1M (Team), charged via Stripe metered billing at period end.

---

## Billing Stack

- **Stripe** — subscriptions, hosted checkout, customer portal, webhooks
- **billing-worker** — Python service processing Stripe webhook events
- **Stripe Customer Portal** — self-serve plan changes and cancellations (no UI to build)

---

## Stripe Integration

### Products and Prices

Three Stripe Products (created in Stripe dashboard):

```
openclaw-starter  → $19/mo recurring
openclaw-pro      → $49/mo recurring
openclaw-team     → $129/mo recurring
```

Each product has metadata the billing-worker reads:
```json
{
  "tier": "starter",
  "tokens_limit": "1000000"
}
```

### Checkout Flow

```
1. Onboarding agent finishes → outputs customer config
2. api creates Stripe Customer + Checkout Session
   - price_id: per selected tier
   - mode: subscription
   - metadata: {openclaw_customer_id: "..."}
   - success_url: /onboarding/success?session={CHECKOUT_SESSION_ID}
3. User completes payment in Stripe-hosted checkout
4. Stripe fires: checkout.session.completed
5. billing-worker:
   a. Creates subscription row in Postgres
   b. Creates usage_monthly row (tokens_used=0, limit=tier.tokens_limit)
   c. Enqueues ProvisionJob in Redis
```

### Webhook Events Handled

| Event | Action |
|---|---|
| `checkout.session.completed` | Create subscription, enqueue `provision` job |
| `invoice.payment_succeeded` | Reset monthly token counter, reactivate if suspended |
| `invoice.payment_failed` | Send warning email; after 3 attempts, enqueue `suspend` job |
| `customer.subscription.updated` | If tier changed: update quota, enqueue `resize` job |
| `customer.subscription.deleted` | Enqueue `destroy` job |

### Self-Serve via Stripe Customer Portal

Customers manage their subscription entirely through the Stripe-hosted portal:
- View invoices
- Update payment method
- Upgrade / downgrade plan
- Cancel subscription

No billing UI to build on our side. Dashboard links to it:
```
POST /billing/portal-session
→ stripe.billing_portal.sessions.create(customer=stripe_customer_id)
→ redirect to portal_session.url
```

---

## Suspension vs Destruction

**Suspension** (payment failure, 3 Stripe retry attempts):
- Operator scales Deployment to 0 replicas
- Namespace and Secret survive — data preserved
- Pod restarts to 1 when payment recovers

**Destruction** (subscription cancelled):
- Operator deletes the entire namespace
- All K8s resources cascade-deleted
- Postgres records retained for 90 days (billing audit)
- No recovery possible — customer must re-onboard if they return

---

## Plan Change: Resize Flow

When a customer upgrades or downgrades (Stripe fires `customer.subscription.updated`):

```
1. billing-worker reads new tier from subscription metadata
2. Enqueues ResizeJob{customer_id, new_tier}
3. operator:
   a. Patches ResourceQuota with new tier limits
   b. Patches Deployment resource requests/limits
   c. Triggers rolling restart (new pod picks up new quota)
4. Token limit updated in usage_monthly for current period
```

Upgrade is immediate. Downgrade takes effect at next billing period start (Stripe `proration_behavior: none`).
