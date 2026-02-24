#!/usr/bin/env bash
set -euo pipefail

# Production bootstrap script — run after `colmena apply` to set up the K8s layer.
# Usage: ./scripts/prod-bootstrap.sh <server-ip>

SERVER_IP="${1:?Usage: $0 <server-ip>}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Copying kubeconfig from server..."
mkdir -p ~/.kube
scp "root@${SERVER_IP}:/etc/rancher/k3s/k3s.yaml" ~/.kube/config
sed -i "s|127.0.0.1|${SERVER_IP}|g" ~/.kube/config
chmod 600 ~/.kube/config

echo "==> Waiting for node to be ready..."
kubectl wait --for=condition=Ready node --all --timeout=120s

echo "==> Installing ingress-nginx..."
helm upgrade --install ingress-nginx ingress-nginx \
  --repo https://kubernetes.github.io/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.hostNetwork=true \
  --set controller.kind=DaemonSet \
  --set controller.service.enabled=false \
  --wait

echo "==> Installing cert-manager..."
helm upgrade --install cert-manager cert-manager \
  --repo https://charts.jetstack.io \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true \
  --wait

echo "==> Applying ClusterIssuer for Let's Encrypt..."
kubectl apply -f - <<'EOF'
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: andre.abadesso@gmail.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
EOF

echo "==> Creating platform namespace..."
kubectl create namespace platform --dry-run=client -o yaml | kubectl apply -f -

echo "==> Checking for platform-secrets..."
if ! kubectl get secret platform-secrets -n platform &>/dev/null; then
  echo ""
  echo "WARNING: platform-secrets not found in the platform namespace."
  echo "Run ./scripts/gen-secrets.sh to generate the secret creation command."
  echo ""
fi

echo "==> Building and applying K8s manifests..."
cd "$REPO_ROOT"
nix build .#k8s-manifests
kubectl apply -f result/

echo "==> Running database migrations..."
DB_POD=$(kubectl get pods -n platform -l app=postgres -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$DB_POD" ]; then
  for migration in "$REPO_ROOT"/db/migrations/*.sql; do
    echo "    Applying $(basename "$migration")..."
    kubectl exec -n platform "$DB_POD" -- psql -U openclaw -d openclaw -f - < "$migration"
  done
else
  echo ""
  echo "WARNING: No postgres pod found. Run migrations manually once the database is available:"
  echo "  for f in db/migrations/*.sql; do kubectl exec -n platform <postgres-pod> -- psql -U openclaw -d openclaw -f - < \$f; done"
fi

echo ""
echo "==> Bootstrap complete!"
echo ""
echo "Next steps:"
echo "  1. Create platform-secrets if not done: ./scripts/gen-secrets.sh"
echo "  2. Push gateway image: nix build .#openclaw-image.copyToRegistry"
echo "  3. Set DNS A records for app/api/proxy/nango.openclaw.trustbit.co.in → ${SERVER_IP}"
echo "  4. Verify: curl https://api.openclaw.trustbit.co.in/health"
