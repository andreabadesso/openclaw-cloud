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
kubectl apply -f result || true   # ignore HPA error on k3d
kubectl apply -f k8s/local/nodeports.yaml

echo "==> Waiting for postgres to be ready..."
kubectl -n platform rollout status statefulset/postgres --timeout=120s

echo "==> Scaling down placeholder services..."
kubectl -n platform scale deployment/onboarding-agent deployment/billing-worker --replicas=0 2>/dev/null || true

echo "==> Building service images..."
docker compose build api operator token-proxy web

echo "==> Importing images into k3d..."
for svc in api operator token-proxy web; do
  image="ghcr.io/andreabadesso/openclaw-cloud/${svc}:latest"
  k3d image import -c openclaw-dev "$image"
done

echo "==> Patching imagePullPolicy and env for local dev..."
for svc in api operator token-proxy web; do
  kubectl -n platform patch deployment "$svc" --type='json' \
    -p='[{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]'
done
kubectl -n platform set env deployment/web API_URL=http://api.platform.svc.cluster.local:8000

echo "==> Waiting for rollouts..."
for svc in api operator token-proxy web; do
  kubectl -n platform rollout status "deployment/${svc}" --timeout=60s
done

echo ""
echo "Done. Services available at:"
echo "  Web:         http://localhost:3000"
echo "  API:         http://localhost:8000"
echo "  Nango:       http://localhost:3003"
echo "  Token-Proxy: http://localhost:8080"
echo "  PostgreSQL:  localhost:5432"
