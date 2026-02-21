# Security Model

---

## Threat Model

| Actor | Threat | Mitigation |
|---|---|---|
| Customer A | Access Customer B's agent | K8s namespace isolation + NetworkPolicy |
| Customer | Steal Kimi API key | Key never in customer namespace; proxy token is customer-specific |
| Customer | Exceed token limits | Hard limit in proxy; 429 before request reaches Kimi |
| Customer | Exhaust cluster resources | ResourceQuota per namespace enforced by K8s |
| Compromised pod | Reach other services | NetworkPolicy allows only token-proxy + Telegram |
| Compromised pod | Read other customers' secrets | K8s RBAC: ServiceAccount in namespace can only read own secrets |
| External attacker | DDoS token-proxy | Rate limiting (10 req/s per proxy token) + ingress-nginx rate limit |
| External attacker | Abuse onboarding | Stripe card required before provisioning |
| Insider | Exfiltrate customer data | RBAC on K8s, Postgres row-level security, audit log |

---

## Customer Isolation Model

Customer pods run in dedicated K8s namespaces. Isolation has three layers:

### 1. RBAC

The customer pod's ServiceAccount (auto-created with the namespace) has no permissions outside its own namespace. It cannot list other namespaces, read other secrets, or call the K8s API at all (no mounted service account token in the pod — we set `automountServiceAccountToken: false`).

### 2. NetworkPolicy

Each customer namespace gets a NetworkPolicy on provisioning:

```yaml
# Allow egress ONLY to token-proxy and Telegram
# Deny everything else — including other customer namespaces
# and platform services (except token-proxy)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: customer-isolation
  namespace: customer-{id}
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
  ingress: []   # no inbound connections accepted
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: platform
          podSelector:
            matchLabels:
              app: token-proxy
      ports:
        - port: 8080
    - to:                        # Telegram API
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8      # block private ranges (cluster internals)
              - 172.16.0.0/12
              - 192.168.0.0/16
      ports:
        - port: 443
    - ports:                     # CoreDNS (required for hostname resolution)
        - port: 53
          protocol: UDP
```

### 3. ResourceQuota

Hard limits on CPU and memory per namespace prevent one customer's runaway pod from starving others. K8s enforces this at the scheduler and container runtime level — the pod cannot consume more even if it tries.

---

## Secrets Architecture

### What lives where

| Secret | Location | Who can read it |
|---|---|---|
| Kimi API key | K8s Secret `platform-secrets` (platform ns) | `token-proxy` pods only |
| Stripe keys | K8s Secret `platform-secrets` (platform ns) | `api`, `billing-worker` only |
| JWT secret | K8s Secret `platform-secrets` (platform ns) | `api` only |
| Postgres URL | K8s Secret `platform-secrets` (platform ns) | All platform services |
| Customer Telegram token | K8s Secret `openclaw-config` (customer-{id} ns) | Customer pod only |
| Customer proxy token | K8s Secret `openclaw-config` (customer-{id} ns) | Customer pod only |
| K3s join token | SOPS `secrets/cluster.yaml` (repo) | NixOS nodes via sops-nix |

### The Kimi API key is never on customer pods

This is the core security property of the token-proxy design. Customer pods authenticate to the token-proxy with a **proxy token** — a UUID scoped to that customer. The proxy token:
- Cannot be used to call Kimi API directly (wrong auth format)
- Is rate-limited to 10 req/s
- Is hard-limited to the customer's monthly token quota
- Is revoked instantly on subscription cancellation

If a customer extracts their proxy token (by exec-ing into their pod, or by reading K8s secrets from within their namespace), they gain nothing useful — they just have a token that calls back to our proxy, which enforces their own limits.

---

## Authentication

### Customer auth (API)

- Email + password → bcrypt (min 12 rounds) → JWT (RS256)
- Access token: 1h expiry
- Refresh token: 7d expiry, stored in httpOnly cookie
- All `/me/*` routes: `customer_id` extracted from JWT, enforced server-side

### Operator auth (in-cluster)

The operator uses its K8s ServiceAccount token (mounted automatically) to authenticate to the K8s API. The ClusterRole grants only what it needs: manage namespaces, secrets, deployments, resource quotas, and network policies. Read-only on nodes.

### Token-proxy auth (proxy tokens)

Customer pods include `Authorization: Bearer {proxy_token}` on every request. The proxy:
1. Looks up the token hash in Redis (cache, 5-min TTL)
2. On cache miss: queries `proxy_tokens` table in Postgres
3. Verifies the token is not revoked
4. Returns `customer_id` for limit checking

Token verification uses constant-time comparison to prevent timing attacks.

---

## Data Privacy

### What we store

| Data | Location | Retention |
|---|---|---|
| Email | Postgres `customers` | Until deletion + 30 days |
| Telegram user ID | Postgres `boxes` | Until account deleted |
| Telegram bot token | K8s Secret (customer namespace) | Until namespace destroyed |
| Onboarding chat history | Postgres `onboarding_sessions` | 90 days |
| Token usage counts | Postgres `usage_events` | 2 years (billing audit) |
| Payment data | Stripe (not us) | Stripe's policy |

### What we never store

- Conversation content (what users say to their agents)
- Agent responses
- Code or files processed by the agent

The token-proxy logs only metadata: `customer_id`, `model`, `token_count`, `timestamp`. Request bodies are never logged.

### GDPR

- Data deletion: `DELETE FROM customers CASCADE` + operator destroys namespace
- Data export: `GET /me/export` returns all customer data as JSON
- Data residency: Hetzner EU (Nuremberg / Helsinki)

---

## Incident Response

### Compromised customer proxy token

```
1. Revoke token: operator DELETE /internal/proxy-tokens/{id}
   → token-proxy removes from Redis + marks revoked in Postgres
2. Create new proxy token
3. Patch customer K8s Secret with new token (Deployment rolls)
4. Notify customer
```
Time to revocation: **< 1 second** (Redis cache invalidated immediately).

### Compromised platform Kimi API key

```
1. Rotate key with Moonshot AI
2. kubectl patch secret platform-secrets --patch '{"stringData":{"kimi_api_key":"new_key"}}'
3. kubectl rollout restart deployment/token-proxy -n platform
   (rolling restart — zero downtime, old pods finish in-flight requests)
4. Old key invalid — no customer pods hold it
```

### Compromised `platform-secrets` K8s Secret

All platform service credentials would need rotation:
```
1. Rotate Postgres password, Stripe keys, JWT secret
2. Update platform-secrets: kubectl create secret --dry-run=client -o yaml | kubectl apply -f -
3. Rolling restart all platform deployments
```

This is the strongest reason to adopt External Secrets Operator + Vault in Phase 2 — automatic rotation without manual kubectl patching.
