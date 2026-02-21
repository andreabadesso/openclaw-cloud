# Kubernetes — The Full Nix Stack

Everything that touches the cluster is a Nix expression. This document covers Colmena (node management), kubenix (manifests), and nix2container (images).

---

## Cluster Layout

```
Hetzner Cloud (private network: 10.0.0.0/24)

  control-plane-1  10.0.0.10  cx31  (4 vCPU, 8 GB)   K3s server + etcd
  worker-1         10.0.0.11  cx41  (8 vCPU, 16 GB)   K3s agent
  worker-2         10.0.0.12  cx41  (8 vCPU, 16 GB)   K3s agent

  build-host       10.0.0.20  cx41  (8 vCPU, 16 GB)   Nix build server
                                                        (not a K8s node)
```

The build host runs NixOS and is used for `nix build` operations (image builds, manifest generation). It keeps the control plane and worker nodes free from Nix build load.

### Phase 1 sizing (0–500 customers)

A single `cx41` worker node runs ~60–80 Starter-tier pods or ~30–40 Pro-tier pods. Two workers give comfortable headroom with redundancy.

### Scaling out

Add a new worker: provision a Hetzner VM with nixos-anywhere, add it to `flake.nix` Colmena config, run `colmena apply --on new-worker`. It joins K3s automatically via the shared token. The operator starts scheduling new customer pods to it immediately.

---

## Colmena — NixOS Fleet Management

Colmena manages the NixOS configuration of all K8s cluster nodes. It replaces Ansible/Terraform for server management.

### How it works

1. Node configs are defined in `flake.nix` under the `colmena` output
2. Each node imports shared modules from `nodes/common.nix` plus a role-specific module (`control-plane.nix` or `worker.nix`)
3. `colmena apply` SSHes to each node and runs `nixos-rebuild switch` with the new config
4. `colmena apply --on @worker` targets only nodes tagged `worker`

### Node configuration structure

```
flake.nix (colmena output)
├── control-plane-1
│   ├── nodes/common.nix      ← disk, SSH, Nix settings, sops, K3s token
│   └── nodes/control-plane.nix  ← K3s server role, etcd backup timer
├── worker-1
│   ├── nodes/common.nix
│   └── nodes/worker.nix      ← K3s agent role, points to control-plane IP
└── worker-2
    └── (same as worker-1)
```

### Secrets on nodes

Cluster nodes need exactly one secret: the K3s join token (used by worker nodes to authenticate to the control plane). This is managed via SOPS:

```
secrets/cluster.yaml  (SOPS-encrypted, committed to repo)
  k3s_token: "K1xyz..."
```

The `common.nix` module configures `sops-nix` to decrypt this at boot using the node's SSH host key.

### Common operations

```bash
# Deploy all nodes
colmena apply

# Deploy only workers
colmena apply --on @worker

# Deploy a specific node
colmena apply --on worker-1

# Check what would change (dry run)
colmena apply --dry-run

# Initial provisioning of a brand new node
nix run github:nix-community/nixos-anywhere -- --flake ".#worker-3" root@{ip}
colmena apply --on worker-3
```

---

## kubenix — K8s Manifests from Nix

kubenix uses the NixOS module system to generate Kubernetes YAML. You write Nix; it outputs valid, type-checked K8s manifests.

### Why not Helm?

Helm is YAML templates with Go templating bolted on — error-prone and hard to compose. kubenix gives you real Nix: module imports, deep merges, computed values, and actual type errors when you misconfigure a field.

### Structure

```
k8s/
├── default.nix          ← imports all modules below
├── namespaces.nix       ← platform + monitoring namespaces
├── infrastructure/
│   ├── redis.nix        ← Redis StatefulSet + Service
│   └── ingress.nix      ← nginx Ingress for app/api/proxy domains
└── services/
    ├── api.nix           ← FastAPI Deployment + Service + HPA
    ├── web.nix           ← Next.js Deployment + Service
    ├── token-proxy.nix   ← Proxy Deployment + Service + HPA
    ├── operator.nix      ← Operator Deployment + ServiceAccount + ClusterRole
    ├── onboarding-agent.nix
    └── billing-worker.nix
```

### Build and apply

```bash
# Build manifests to YAML
nix build .#k8s-manifests
ls result/  # → all-in-one.yaml or per-resource YAMLs

# Apply to cluster
kubectl apply -f result/

# Or pipe directly
nix build .#k8s-manifests --json | jq -r '.[0].outputs.out' | xargs kubectl apply -f
```

### Customer namespaces

Customer-specific K8s resources (namespace, secret, deployment, quota, network policy) are **not** in kubenix. They are created dynamically by the `operator` service via the K8s API. kubenix manages only the static platform infrastructure.

---

## nix2container — Reproducible OCI Images

Container images for all platform services and the customer OpenClaw pod are built with `nix2container`. This replaces Dockerfiles entirely.

### Why nix2container over dockerTools?

`nix2container` is faster than `pkgs.dockerTools.buildImage` because it constructs images layer-by-layer without intermediate tarballs, and pushes layers directly to the registry without loading into the Docker daemon.

### The OpenClaw gateway image

Defined in `images/openclaw-gateway.nix`:

```nix
n2c.buildImage {
  name = "ghcr.io/andreabadesso/openclaw-cloud/openclaw-gateway";
  tag  = "latest";

  # Only what the binary needs — no shell, no OS
  copyToRoot = pkgs.buildEnv {
    name  = "root";
    paths = [ pkgs.cacert pkgs.tzdata ];
  };

  config = {
    Entrypoint = [ "${openclaw}/bin/openclaw-gateway" ];
    Env = [
      "SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt"
      "TZ=UTC"
    ];
    # All customer config comes from K8s Secret at runtime
  };
}
```

The image contains:
- The OpenClaw binary (from `nix-openclaw` flake input, pinned)
- CA certificates (for TLS to Telegram + Kimi)
- Timezone data

Nothing else. No shell. No package manager. No unused libraries. The image is typically **20–50 MB** vs a typical Docker image at 200–500 MB.

### Building and pushing

```bash
# Build the image
nix build .#openclaw-image

# Push to ghcr.io
nix run .#openclaw-image.copyToRegistry

# Build all service images (each app has its own image in flake.nix)
nix build .#api-image
nix build .#token-proxy-image
nix build .#operator-image
```

### Image tags and CI

In CI (GitHub Actions), images are tagged with the git commit SHA:

```bash
nix build .#openclaw-image \
  --arg tag '"'$GITHUB_SHA'"'
nix run .#openclaw-image.copyToRegistry
```

The kubenix manifests reference `image: ghcr.io/.../openclaw-gateway:latest` in development and the SHA tag in production (updated by CI before `kubectl apply`).

---

## K8s Namespaces

```
kube-system/       ← K3s internals (Flannel, CoreDNS, etc.)
cert-manager/      ← Let's Encrypt TLS automation
ingress-nginx/     ← nginx ingress controller
platform/          ← all openclaw-cloud services
monitoring/        ← Prometheus + Grafana (Phase 2)
customer-{id}/     ← one per paying customer (created by operator)
```

---

## Secrets Management

### Cluster node secrets (SOPS)

One SOPS-encrypted file at `secrets/cluster.yaml` holds the K3s join token. Committed to the repo (encrypted). Decrypted at boot by `sops-nix` using each node's SSH host key.

### Platform service secrets (K8s Secrets)

Platform services (api, token-proxy, etc.) read secrets from a K8s Secret named `platform-secrets` in the `platform` namespace. This secret is created manually on cluster bootstrap and managed by an ops engineer:

```bash
kubectl create secret generic platform-secrets \
  --namespace platform \
  --from-literal=postgres_url="postgresql://..." \
  --from-literal=redis_url="redis://..." \
  --from-literal=kimi_api_key="sk-..." \
  --from-literal=stripe_secret_key="sk_live_..." \
  --from-literal=stripe_webhook_secret="whsec_..." \
  --from-literal=jwt_secret="$(openssl rand -hex 32)"
```

Phase 2: migrate to External Secrets Operator + HashiCorp Vault for rotation and auditing.

### Customer secrets (K8s Secrets, per namespace)

Each customer's `openclaw-config` Secret is created by the operator at provisioning time. It contains their Telegram token and their proxy token (not the Kimi API key). Only the pod in that namespace can read it (enforced by K8s RBAC).

---

## CI/CD

```
GitHub Actions:

push to main →
  1. nix build all images
  2. push images to ghcr.io with SHA tag
  3. nix build .#k8s-manifests
  4. kubectl apply -f result/ (to staging cluster)
  5. run smoke tests

git tag v* →
  1. same builds
  2. kubectl apply -f result/ (to production cluster, after manual approval)
  3. colmena apply (if any node config changed)
```

---

## Monitoring (Phase 2)

- **Prometheus** scrapes all `platform` pods (via pod annotations)
- **Grafana** dashboards: per-service latency, customer pod health, token proxy throughput
- **AlertManager** → Slack + PagerDuty for critical alerts

Phase 1: rely on K8s events, pod logs (`kubectl logs`), and Postgres queries for observability.
