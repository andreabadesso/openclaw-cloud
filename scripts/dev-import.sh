#!/usr/bin/env bash
# Quick rebuild + redeploy a single service into k3d.
# Usage: ./scripts/dev-import.sh api
set -euo pipefail

SERVICE="${1:?Usage: $0 <service>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

echo "==> Building ${SERVICE}..."
docker compose build "$SERVICE"

IMAGE="openclaw-cloud-${SERVICE}:latest"

echo "==> Importing ${IMAGE} into k3d..."
k3d image import -c openclaw-dev "$IMAGE"

echo "==> Restarting deployment/${SERVICE}..."
kubectl -n platform rollout restart "deployment/${SERVICE}"

echo "Done."
