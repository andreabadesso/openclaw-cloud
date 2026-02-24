#!/usr/bin/env bash
set -euo pipefail

# Generate platform-secrets for the OpenClaw production cluster.
# Outputs a kubectl command you can review and run.

gen_hex() { openssl rand -hex "$1"; }
gen_b64() { openssl rand "$1" | base64; }

JWT_SECRET=$(gen_hex 32)
AGENT_API_SECRET=$(gen_hex 32)
NANGO_ENCRYPTION_KEY=$(gen_b64 32)

cat <<EOF

# ── OpenClaw Platform Secrets ──────────────────────────────────────────
# Auto-generated values are filled in. Replace the YOUR_* placeholders
# with your actual credentials before running.

kubectl create secret generic platform-secrets \\
  --namespace platform \\
  --from-literal=jwt_secret="${JWT_SECRET}" \\
  --from-literal=agent_api_secret="${AGENT_API_SECRET}" \\
  --from-literal=nango_encryption_key="${NANGO_ENCRYPTION_KEY}" \\
  --from-literal=postgres_url="YOUR_POSTGRES_URL" \\
  --from-literal=redis_url="YOUR_REDIS_URL" \\
  --from-literal=stripe_secret_key="YOUR_STRIPE_SECRET_KEY" \\
  --from-literal=stripe_webhook_secret="YOUR_STRIPE_WEBHOOK_SECRET" \\
  --from-literal=nango_secret_key="YOUR_NANGO_SECRET_KEY" \\
  --from-literal=nango_public_key="YOUR_NANGO_PUBLIC_KEY" \\
  --from-literal=nango_server_url="https://nango.openclaw.trustbit.co.in" \\
  --from-literal=web_url="https://app.openclaw.trustbit.co.in" \\
  --from-literal=browserless_api_key="YOUR_BROWSERLESS_API_KEY"

EOF
