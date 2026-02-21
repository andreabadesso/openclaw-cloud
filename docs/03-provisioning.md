# Provisioning

Customer agent provisioning is handled by the `operator` service. It runs in-cluster, watches a Redis job queue, and manages K8s resources directly via the Kubernetes API.

**No VMs. No SSH. No nixos-anywhere per customer.** Provisioning is `kubectl apply` — it takes seconds.

---

## Operator Design

The operator is a Python service with a ServiceAccount that has ClusterRole permissions to manage namespaces, secrets, deployments, and resource quotas across the cluster.

It processes jobs from a Redis list (`BLPOP operator:jobs`), one job type at a time per customer (serialized via a Redis lock on `customer_id`).

```python
# Simplified main loop
while True:
    _, raw = redis.blpop("operator:jobs")
    job = Job.from_json(raw)
    with customer_lock(job.customer_id):
        handle(job)
```

All job results are written to Postgres (`operator_jobs` table) for auditing.

---

## Tier Resource Limits

Resource quotas are enforced at the K8s namespace level. No customer can consume more than their tier allows, regardless of what's in their pod spec — K8s will reject or throttle it.

| Tier | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---|---|---|---|---|
| Starter | 250m | 500m | 128Mi | 256Mi |
| Pro | 500m | 1000m | 256Mi | 512Mi |
| Team | 1000m | 2000m | 512Mi | 1Gi |

A single worker node (Hetzner `cx41`: 8 vCPU, 16 GB) comfortably runs **~40–60 Starter customers** or **~20–30 Pro customers** alongside each other.

---

## Job: `provision`

Triggered by `billing-worker` when `checkout.session.completed` fires from Stripe.

### Steps

**1. Validate** (operator, <1s)
```
- Check customer record exists and has no active box
- Generate proxy token (UUID) → store in Postgres proxy_tokens table
- Register proxy token with token-proxy via internal API
```

**2. Create K8s namespace** (<1s)
```python
v1.create_namespace(V1Namespace(
    metadata=V1ObjectMeta(
        name=f"customer-{customer_id}",
        labels={"openclaw/customer": customer_id, "openclaw/tier": tier}
    )
))
```

**3. Create K8s Secret** (<1s)
```python
v1.create_namespaced_secret(
    namespace=f"customer-{customer_id}",
    body=V1Secret(
        metadata=V1ObjectMeta(name="openclaw-config"),
        string_data={
            "TELEGRAM_BOT_TOKEN":  telegram_bot_token,
            "TELEGRAM_ALLOW_FROM": str(telegram_user_id),
            "KIMI_API_KEY":        proxy_token,          # NOT the real Kimi key
            "KIMI_BASE_URL":       "http://token-proxy.platform.svc.cluster.local:8080/v1",
            "OPENCLAW_MODEL":      model,
            "OPENCLAW_THINKING":   thinking_level,
        }
    )
)
```

**4. Apply ResourceQuota** (<1s)
```python
v1.create_namespaced_resource_quota(
    namespace=f"customer-{customer_id}",
    body=V1ResourceQuota(
        metadata=V1ObjectMeta(name="tier-limits"),
        spec=V1ResourceQuotaSpec(hard=TIER_QUOTAS[tier])
    )
)
```

**5. Apply NetworkPolicy** (<1s)

Restricts pod to only reach `token-proxy` and Telegram. See `07-security.md`.

**6. Create Deployment** (<1s)
```python
apps_v1.create_namespaced_deployment(
    namespace=f"customer-{customer_id}",
    body=build_deployment(customer_id, tier)
)
```

The Deployment spec:
```yaml
replicas: 1
image: ghcr.io/andreabadesso/openclaw-cloud/openclaw-gateway:latest
envFrom:
  - secretRef:
      name: openclaw-config
restartPolicy: Always
resources:  # enforced by ResourceQuota anyway, but explicit is good
  requests: {cpu: 250m, memory: 128Mi}
  limits:   {cpu: 500m, memory: 256Mi}
```

**7. Wait for pod Ready** (<30s)
```
Poll pod status until containerStatuses[0].ready = true
Timeout: 60s — if not ready, mark job failed, alert ops
```

**8. Update Postgres + notify** (<1s)
```
boxes.status = 'active'
boxes.activated_at = now()
→ Push WebSocket event to customer's dashboard session
→ Send "your agent is live" email
```

**Total provisioning time: ~10–30 seconds.**

---

## Job: `update`

Triggered when a customer changes settings in the dashboard (add Telegram user, change thinking level, etc.).

```
1. Fetch updated config from Postgres
2. Patch K8s Secret (PATCH namespaced secret, strategic merge)
3. Rollout restart Deployment (patch annotation triggers new pod)
   kubectl.patch_namespaced_deployment(
     name="openclaw-gateway",
     namespace=f"customer-{id}",
     body={"spec": {"template": {"metadata": {"annotations":
       {"kubectl.kubernetes.io/restartedAt": datetime.utcnow().isoformat()}
     }}}}
   )
4. Wait for rollout complete (~15s)
5. Update Postgres last_updated
```

**Update time: ~15–30 seconds.** Zero downtime — K8s does rolling update (old pod stays up until new pod is Ready).

---

## Job: `destroy`

Triggered by `billing-worker` on subscription cancellation.

```
1. Delete K8s namespace (cascades: pod, secret, quota, networkpolicy all gone)
   v1.delete_namespace(f"customer-{customer_id}")
2. Revoke proxy token in token-proxy
3. Update Postgres: boxes.status = 'destroyed'
4. Retain usage_events for billing audit (90-day retention)
```

**Destroy time: <5 seconds.**

---

## Job: `suspend`

Triggered on payment failure (3 Stripe retry attempts).

```
1. Scale Deployment to 0 replicas
   kubectl.patch deployment replicas=0
2. Update Postgres: boxes.status = 'suspended'
3. Send suspension email to customer
```

The namespace and secret survive. Data is preserved. The pod simply stops running.

---

## Job: `reactivate`

Triggered when a suspended customer's payment succeeds.

```
1. Scale Deployment back to 1 replica
   kubectl.patch deployment replicas=1
2. Update Postgres: boxes.status = 'active'
3. Send "agent is back online" email
```

---

## Job: `resize`

Triggered when a customer upgrades or downgrades their tier.

```
1. Patch ResourceQuota with new tier limits
2. Patch Deployment resource requests/limits
3. Rollout restart (new pod picks up new limits)
4. Update Postgres: subscriptions.tier = new_tier
```

---

## Health Check (cron, every 5 minutes)

A scheduled K8s CronJob (or operator timer) checks all active customer deployments:

```python
for customer_id in db.get_active_customer_ids():
    ns = f"customer-{customer_id}"
    deployment = apps_v1.read_namespaced_deployment("openclaw-gateway", ns)
    ready = deployment.status.ready_replicas or 0

    if ready == 0:
        db.increment_health_failures(customer_id)
        if db.get_health_failures(customer_id) >= 3:
            alert_ops(customer_id)
            alert_customer(customer_id)
    else:
        db.reset_health_failures(customer_id)
        db.update_last_seen(customer_id)
```

---

## Cluster Node Provisioning (Colmena — separate from customer pods)

When you need to add or update K8s **worker nodes** (not customer pods — the actual servers), that's where Colmena + nixos-anywhere comes in:

```bash
# Initial provisioning of a new Hetzner VM as a K3s worker
nix run github:nix-community/nixos-anywhere -- \
  --flake ".#worker-3" root@{new-vm-ip}

# Add to flake.nix colmena config, then:
colmena apply --on worker-3

# Update all workers:
colmena apply --on @worker
```

This is the only place nixos-anywhere is used — for cluster infrastructure, not customer instances.
