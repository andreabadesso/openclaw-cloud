# OpenClaw Cloud -- Production Deployment

## Infrastructure Summary

**Server:**

- AWS EC2 t3.medium (2 vCPU, 4GB RAM, 30GB gp3 EBS)
- Instance ID: `i-0e645119acbe1388d`
- Elastic IP: `18.213.15.202`
- Region: `us-east-1`
- OS: NixOS 25.11 (unstable)
- Kubernetes: k3s v1.34.3+k3s3 (single-node, embedded SQLite)
- Flannel backend: `host-gw`
- Boot: SeaBIOS / legacy BIOS with GPT + BIOS boot partition (EF02)

---

## URLs & DNS

| Subdomain | URL | Backend Service | Port |
|-----------|-----|-----------------|------|
| app.openclaw.trustbit.co.in | https://app.openclaw.trustbit.co.in | web | 3000 |
| api.openclaw.trustbit.co.in | https://api.openclaw.trustbit.co.in | api | 8000 |
| proxy.openclaw.trustbit.co.in | https://proxy.openclaw.trustbit.co.in | token-proxy | 8080 |
| nango.openclaw.trustbit.co.in | https://nango.openclaw.trustbit.co.in | nango-server | 8080 |

All DNS A records point to `18.213.15.202`.

---

## TLS / Certificates

- **Issuer:** Let's Encrypt (production ACME)
- **ClusterIssuer name:** `letsencrypt-prod`
- **Email:** andre.abadesso@gmail.com
- **Solver:** HTTP-01 via ingress-nginx
- **Secret:** `openclaw-tls` in `platform` namespace
- **Valid:** Feb 24, 2026 to May 25, 2026
- **Auto-renewal:** April 25, 2026 (cert-manager handles this automatically)

The ClusterIssuer is created during bootstrap (`scripts/prod-bootstrap.sh`) and points to the production ACME directory (`https://acme-v02.api.letsencrypt.org/directory`). The Ingress resource (`k8s/infrastructure/ingress.nix`) annotates itself with `cert-manager.io/cluster-issuer: letsencrypt-prod` so that cert-manager automatically provisions and renews the certificate.

---

## NixOS Configuration

### Disk Layout (disko)

Defined in `nodes/common.nix`:

- Device: `/dev/nvme0n1` with GPT partition table
- **Partition 1:** 1MB BIOS boot partition (type `EF02`) -- required for GRUB on GPT with legacy BIOS
- **Partition 2:** Rest of disk, ext4 root filesystem mounted at `/`

### Boot

- GRUB 2 installed to `/dev/nvme0n1` MBR (i386-pc platform)
- **NOT EFI** -- AWS t3 instances use SeaBIOS, not UEFI
- Console output: `ttyS0,115200n8`
- AWS Nitro kernel modules loaded at initrd: `nvme`, `xhci_pci`, `ena`

### Networking

- DHCP enabled globally (`networking.useDHCP = true`) -- AWS assigns IPs via DHCP
- Firewall enabled with TCP ports 22, 80, 443 open
- K3s API port 6443 opened additionally on server nodes
- Flannel overlay interfaces (`flannel.1`, `cni0`) marked as trusted

### k3s Flags

From `nodes/server.nix`:

```
--tls-san=18.213.15.202
--cluster-cidr=10.42.0.0/16
--service-cidr=10.43.0.0/16
--disable traefik
--disable servicelb
--flannel-backend=host-gw
--write-kubeconfig-mode=0644
--node-label=openclaw/role=server
```

Traefik and the built-in ServiceLB are disabled because we use ingress-nginx (installed via Helm with `hostNetwork: true` as a DaemonSet) and have no cloud load balancer.

### etcd Backup

A systemd timer runs daily k3s etcd snapshots:

```
k3s etcd-snapshot save --name "snapshot-YYYYMMDD-HHMMSS"
```

### SOPS Secrets

Managed by `sops-nix`. Configuration in `.sops.yaml`:

- **Admin age key:** `age17qqsp8w74x6fyrvqa82gmn3zllk2m9r0crd0dtkrdndyz7e9q5fqq7hger`
- **Server age key:** `age102kua49dd20g6g5fyayl40klffrmt3jm3nawtlxs83sms3z86qpq0wg7vk` (derived from server SSH host key via `ssh-to-age`)
- **Encrypted file:** `secrets/cluster.yaml` (contains `k3s_token`)

The server decrypts secrets at boot using its SSH host ed25519 key (`/etc/ssh/ssh_host_ed25519_key`).

### Nix Flake Structure

Defined in `flake.nix`:

- **Inputs:** nixpkgs (unstable), colmena, disko, sops-nix, nix2container, kubenix, nix-openclaw
- **NixOS configuration:** `nixosConfigurations.server-1` -- combines `nodes/common.nix` + `nodes/server.nix`
- **Colmena deployment target:** `server-1` with `deployment.targetHost` read from `cluster.json`
- **Packages:**
  - `k8s-manifests` -- Kubernetes manifests generated via kubenix
  - `openclaw-image` -- OpenClaw gateway container image built with nix2container
- **Dev shell:** includes colmena, kubectl, k9s, helm, kubie, sops, age, jq, yq-go, python3

### Deployment Commands

**Initial install (from scratch):**

```bash
nix shell nixpkgs#nixos-anywhere -c nixos-anywhere --flake ".#server-1" root@18.213.15.202
```

**Config updates (current workaround since Colmena has issues):**

```bash
nix build .#nixosConfigurations.server-1.config.system.build.toplevel
nix copy --to ssh://root@18.213.15.202 <store-path>
ssh root@18.213.15.202 "<store-path>/bin/switch-to-configuration switch"
```

**Colmena (once working):**

```bash
colmena apply --on server-1
```

---

## Kubernetes Services

### Helm Releases

| Release | Namespace | Notes |
|---------|-----------|-------|
| ingress-nginx | ingress-nginx | hostNetwork DaemonSet, no LoadBalancer service |
| cert-manager | cert-manager | v1.19.3 with CRDs enabled |

Both are installed by `scripts/prod-bootstrap.sh` using `helm upgrade --install`.

### Platform Namespace Pods

| Service | Replicas | Image | Status |
|---------|----------|-------|--------|
| api | 1 | ghcr.io/andreabadesso/openclaw-cloud/api:latest | Running |
| web | 1 | ghcr.io/andreabadesso/openclaw-cloud/web:latest | Running (next dev mode) |
| token-proxy | 3 | ghcr.io/andreabadesso/openclaw-cloud/token-proxy:latest | Running |
| operator | 1 | ghcr.io/andreabadesso/openclaw-cloud/operator:latest | Running |
| billing-worker | 1 | ghcr.io/andreabadesso/openclaw-cloud/billing-worker:latest | Running |
| browser-proxy | 1 | ghcr.io/andreabadesso/openclaw-cloud/browser-proxy:latest | Running |
| nango-server | 1 | nangohq/nango-server:hosted | Running |
| postgres | 1 (StatefulSet) | postgres:16-alpine | Running |
| redis | 1 (StatefulSet) | redis:7-alpine | Running |
| onboarding-agent | 0 (scaled down) | No Dockerfile exists yet | N/A |

### Secrets

Two secrets in the `platform` namespace:

**1. platform-secrets** -- contains:

| Key | Value Source |
|-----|-------------|
| `jwt_secret` | Random 64-char hex (generated by `gen-secrets.sh`) |
| `agent_api_secret` | Random 64-char hex (generated by `gen-secrets.sh`) |
| `internal_api_key` | Random 64-char hex |
| `nango_encryption_key` | From local dev: `oFXip3RDRZWdxG6hxh1o5irgQUTFmQeHQDxd3bg1sEg=` |
| `nango_secret_key` | From local dev: `7c999a69-a4f8-440a-b677-be2bee532fe3` |
| `nango_public_key` | Empty |
| `nango_server_url` | `https://nango.openclaw.trustbit.co.in` |
| `nango_redis_url` | `redis://:PASSWORD@redis.platform.svc.cluster.local:6379/1` |
| `postgres_user` | `openclaw` |
| `postgres_password` | Random 32-char |
| `postgres_db` | `openclaw` |
| `postgres_url` | `postgresql+asyncpg://openclaw:PASSWORD@postgres.platform.svc.cluster.local:5432/openclaw` |
| `redis_url` | `redis://:PASSWORD@redis.platform.svc.cluster.local:6379` |
| `web_url` | `https://app.openclaw.trustbit.co.in` |
| `kimi_api_key` | Real key from `.env` |
| `stripe_secret_key` | PLACEHOLDER |
| `stripe_webhook_secret` | PLACEHOLDER |
| `browserless_url` | PLACEHOLDER |
| `nango_db_user` | `nango` |
| `nango_db_password` | Random |
| `nango_db_name` | `nango` |

**2. redis-secret** -- contains:

| Key | Value Source |
|-----|-------------|
| `password` | Random 32-char |

### Ingress Configuration

Defined in `k8s/infrastructure/ingress.nix`. A single Ingress resource named `platform` in the `platform` namespace:

- Ingress class: `nginx`
- TLS secret: `openclaw-tls` (covers all four subdomains)
- Annotations: `ssl-redirect=true`, `proxy-read-timeout=300`
- Four host rules routing to `web:3000`, `api:8000`, `token-proxy:8080`, `nango-server:8080`

### Nango Configuration

Defined in `k8s/services/nango.nix`. Key details:

- Image: `nangohq/nango-server:hosted`
- Database connection: `postgres.platform.svc.cluster.local:5432` with dedicated `nango` user/database
- Redis: reads URL from `platform-secrets` (`nango_redis_url`, database index 1)
- Auth: `FLAG_AUTH_ENABLED=false`
- Resources: 200m-500m CPU, 256Mi-512Mi memory
- Health check: `GET /health` on port 8080

### Database

PostgreSQL 16 (Alpine) with these tables:

- `boxes`
- `customer_connections`
- `customers`
- `onboarding_sessions`
- `operator_jobs`
- `proxy_tokens`
- `subscriptions`
- `usage_events`
- `usage_monthly`

Nango has its own database `nango` with user `nango`.

All 7 migrations applied (`001_initial` through `007_bundles`), located in `db/migrations/`.

---

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`):

- **Trigger:** On push to `master`
- **Build matrix:** api, operator, billing-worker, token-proxy, web, browser-proxy
- **Registry:** `ghcr.io/andreabadesso/openclaw-cloud/<service>`
- **Tags:** `latest` + git SHA
- **Images are currently pulling without `imagePullSecret`** (likely set to public on GHCR)

---

## Bootstrap Procedure

The full bootstrap from a fresh EC2 instance:

### Step 1: Provision the EC2 instance

Create a t3.medium in us-east-1 with 30GB gp3 EBS. Attach an Elastic IP. Note down the IP.

### Step 2: Update cluster.json

Copy `cluster.example.json` to `cluster.json` and fill in the server public IP. Force-add to git:

```bash
git add -f cluster.json
```

This file is gitignored but required for Nix flake evaluation.

### Step 3: Update SOPS keys (if new instance)

Get the server's age key from its SSH host key:

```bash
ssh root@18.213.15.202 "cat /etc/ssh/ssh_host_ed25519_key.pub" | ssh-to-age
```

Update the `&server` key in `.sops.yaml`, then re-encrypt secrets:

```bash
sops updatekeys secrets/cluster.yaml
```

### Step 4: Install NixOS

```bash
nix shell nixpkgs#nixos-anywhere -c nixos-anywhere --flake ".#server-1" root@18.213.15.202
```

### Step 5: Run the bootstrap script

```bash
./scripts/prod-bootstrap.sh 18.213.15.202
```

This will:

1. Copy kubeconfig from the server
2. Wait for the node to be ready
3. Install ingress-nginx (hostNetwork DaemonSet)
4. Install cert-manager with CRDs
5. Create the `letsencrypt-prod` ClusterIssuer
6. Create the `platform` namespace
7. Build and apply kubenix manifests
8. Run database migrations

### Step 6: Create secrets

Generate the secrets template:

```bash
./scripts/gen-secrets.sh
```

This outputs a `kubectl create secret generic platform-secrets` command with auto-generated random values for `jwt_secret`, `agent_api_secret`, and `nango_encryption_key`. Fill in the `YOUR_*` placeholders with real values and run the command.

Also create the Redis secret:

```bash
kubectl create secret generic redis-secret \
  --namespace platform \
  --from-literal=password="$(openssl rand -hex 16)"
```

### Step 7: Set DNS

Create A records for all four subdomains pointing to the Elastic IP:

- `app.openclaw.trustbit.co.in` -> `18.213.15.202`
- `api.openclaw.trustbit.co.in` -> `18.213.15.202`
- `proxy.openclaw.trustbit.co.in` -> `18.213.15.202`
- `nango.openclaw.trustbit.co.in` -> `18.213.15.202`

### Step 8: Verify

```bash
curl https://api.openclaw.trustbit.co.in/health
kubectl get pods -n platform
kubectl get certificate -n platform
```

---

## Deployment History & Lessons Learned

### Instance Timeline

1. **i-0971c1f1e7870eb4a** -- First instance. `nixos-anywhere` succeeded but server was unreachable. Missing DHCP, SSH keys, AWS kernel modules (`ena`, `nvme`). Terminated.
2. **i-0963f2b5185379a7e** -- Second attempt. Still unreachable despite correct kernel params. Root cause: GRUB was installed for EFI (`efiInstallAsRemovable=true`) but AWS t3 uses SeaBIOS (legacy BIOS). The EFI bootloader was invisible to the firmware. Terminated.
3. **i-0e645119acbe1388d** -- Third (current) instance. Fixed with legacy BIOS GRUB (`device=/dev/nvme0n1`, i386-pc platform). Successfully booted.

### Key Issues & Fixes

1. **EFI vs BIOS:** AWS t3 instances use SeaBIOS, not UEFI. Must use `boot.loader.grub.device = "/dev/nvme0n1"` (not `"nodev"` with `efiSupport`).
2. **GPT + BIOS boot:** Need a 1MB EF02 (BIOS boot) partition for GRUB `core.img` on GPT disks.
3. **Flannel backend:** `--flannel-backend=local` does NOT exist in k3s. Caused silent crash loop. Use `host-gw` for single-node.
4. **SOPS key rotation:** Each new EC2 instance generates new SSH host keys, requiring SOPS key update via `ssh-to-age`.
5. **Nix flake dirty tree:** `cluster.json` must be force-added to git (`git add -f`) since it is gitignored but needed by flake evaluation.
6. **postgres_url driver:** Must use `postgresql+asyncpg://` (not `postgresql://`) -- the API uses SQLAlchemy with asyncpg.
7. **Nango permissions:** The nango postgres user needs OWNER on its database to run migrations.
8. **Redis auth:** Nango Redis URL was hardcoded without password. Fixed to read from secret.
9. **Web probe timeouts:** Next.js dev mode takes too long to compile on first request. Liveness probe kills the pod. Increased `initialDelaySeconds` to 120s.
10. **Resource limits:** t3.medium (2 vCPU) cannot run all replicas. Scaled down to 1 replica per service.

---

## Known Issues / TODO

1. **Web runs in dev mode** -- Dockerfile uses `next dev`. Should use `next build && next start` for production.
2. **Onboarding Agent** -- No Dockerfile exists. Deployment scaled to 0.
3. **Placeholder secrets** -- Stripe keys and Browserless URL need real values.
4. **Resource constraints** -- t3.medium is tight. Consider t3.large for comfortable headroom.
5. **Colmena** -- Failed with "cannot update unlocked flake input" error. Workaround: build locally + `nix copy` + `switch-to-configuration`.
6. **GHCR visibility** -- Images may need to be set to public if k8s cannot pull them (currently working without `imagePullSecret`, so they may already be public).

---

## SSH Access

```bash
ssh root@18.213.15.202
```

Key: `~/.ssh/openclaw-prod.pem`

---

## Useful Commands

```bash
# Check k3s status
ssh root@18.213.15.202 "systemctl status k3s"

# Get kubeconfig
scp root@18.213.15.202:/etc/rancher/k3s/k3s.yaml ~/.kube/config
sed -i 's|127.0.0.1|18.213.15.202|g' ~/.kube/config

# Check pods
kubectl get pods -n platform

# View logs
kubectl logs -n platform -l app=api --tail=50

# Restart a service
kubectl rollout restart deployment api -n platform

# Apply updated manifests
nix build .#k8s-manifests && kubectl apply -f result/

# Update NixOS config
nix build .#nixosConfigurations.server-1.config.system.build.toplevel
nix copy --to ssh://root@18.213.15.202 <store-path>
ssh root@18.213.15.202 "<store-path>/bin/switch-to-configuration switch"

# Update SOPS secrets after instance recreation
ssh root@18.213.15.202 "cat /etc/ssh/ssh_host_ed25519_key.pub" | ssh-to-age
# Update .sops.yaml with new age key, then:
sops updatekeys secrets/cluster.yaml

# Run database migrations manually
for f in db/migrations/*.sql; do
  kubectl exec -n platform <postgres-pod> -- psql -U openclaw -d openclaw -f - < "$f"
done

# Check certificate status
kubectl get certificate -n platform
kubectl describe certificate openclaw-tls -n platform

# View ingress
kubectl get ingress -n platform

# Force certificate renewal
kubectl delete secret openclaw-tls -n platform
# cert-manager will re-issue automatically
```
