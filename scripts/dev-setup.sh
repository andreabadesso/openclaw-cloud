#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

echo "==> Creating k3d cluster (if not exists)..."
k3d cluster list 2>/dev/null | grep -q openclaw-dev || k3d cluster create --config k3d.yaml

echo "==> Building kubenix manifests..."
nix build .#k8s-manifests

echo "==> Applying secrets + manifests + local nodeports..."
kubectl apply -f k8s/local/secrets.yaml
kubectl apply -f result/
kubectl apply -f k8s/local/nodeports.yaml

echo "==> Waiting for postgres to be ready..."
kubectl -n platform rollout status statefulset/postgres --timeout=120s

echo "==> Building service images..."
docker compose build api operator token-proxy web

echo "==> Importing images into k3d..."
for svc in api operator token-proxy web; do
  image="openclaw-cloud-${svc}:latest"
  k3d image import -c openclaw-dev "$image"
done

echo "==> Restarting deployments to pick up local images..."
for svc in api operator token-proxy web; do
  kubectl -n platform rollout restart "deployment/${svc}"
done

echo ""
echo "Done. Services available at:"
echo "  Web:         http://localhost:3000"
echo "  API:         http://localhost:8000"
echo "  Nango:       http://localhost:3003"
echo "  Token-Proxy: http://localhost:8080"
echo "  PostgreSQL:  localhost:5432"
