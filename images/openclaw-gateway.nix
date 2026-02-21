{ pkgs, n2c, nix-openclaw }:

let
  openclaw = nix-openclaw.packages.x86_64-linux.default;

  caCerts = pkgs.cacert;

  # Entrypoint: create openclaw config from env vars, then start gateway
  entrypoint = pkgs.writeShellScript "entrypoint" ''
    set -euo pipefail

    export HOME="/root"
    export OPENCLAW_STATE_DIR="$HOME/.openclaw"
    mkdir -p "$OPENCLAW_STATE_DIR" "$OPENCLAW_STATE_DIR/agents" "$OPENCLAW_STATE_DIR/logs"

    # Read env vars from K8s Secret
    MODEL="''${OPENCLAW_MODEL:-kimi-coding/k2p5}"
    PROVIDER="''${MODEL%%/*}"
    THINKING="''${OPENCLAW_THINKING:-medium}"
    ALLOW_FROM="''${TELEGRAM_ALLOW_FROM:-0}"
    TOKEN="''${TELEGRAM_BOT_TOKEN:-}"

    # Write the bot token to a file
    TOKEN_FILE="$OPENCLAW_STATE_DIR/telegram-token"
    printf '%s' "$TOKEN" > "$TOKEN_FILE"

    # Build allowFrom JSON array from comma-separated string
    ALLOW_ARRAY=$(printf '%s' "$ALLOW_FROM" | tr ',' '\n' | sed '/^$/d' | sed 's/^/    /;s/$/,/' | sed '$ s/,$//')

    # Generate AGENTS.md from OPENCLAW_CONNECTIONS if set
    WORKSPACE_DIR="/root/workspace"
    mkdir -p "$WORKSPACE_DIR"
    CONNECTIONS_JSON="''${OPENCLAW_CONNECTIONS:-}"
    if [ -n "$CONNECTIONS_JSON" ]; then
      AGENT_API_URL=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.api_url')
      AGENT_API_SECRET=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.api_secret')
      AGENT_CUSTOMER_ID=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.customer_id')

      NANGO_PROXY_URL=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.nango_proxy_url')
      NANGO_SECRET_KEY=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.nango_secret_key')
      CONN_LIST=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.connections[] | "- **\(.provider)**: connection_id=`\(.connection_id)`"')

      cat > "$WORKSPACE_DIR/AGENTS.md" << EOAGENTS
# External Service Connections

You have access to external services via an authenticated proxy. Use \`web_fetch\` to make API calls.

## Connected Services

$CONN_LIST

## How to Make API Calls

Use the \`web_fetch\` tool to call external APIs through the Nango proxy at:
\`$NANGO_PROXY_URL/proxy\`

Required headers for every proxy request:
- \`Authorization: Bearer $NANGO_SECRET_KEY\`
- \`Connection-Id: <connection_id from above>\`
- \`Provider-Config-Key: <provider name>\`

### Google Drive Example

To list Google Drive files, use web_fetch with:
- URL: \`$NANGO_PROXY_URL/proxy/drive/v3/files?pageSize=10\`
- Headers: \`Authorization: Bearer $NANGO_SECRET_KEY\`, \`Connection-Id: <google_connection_id>\`, \`Provider-Config-Key: google\`

### Google Sheets Example

- URL: \`$NANGO_PROXY_URL/proxy/v4/spreadsheets/<spreadsheet_id>\`
- Same headers as above.

### Requesting New Connections

If the user asks for a service that is not connected, use web_fetch to POST to:
\`$AGENT_API_URL/internal/agent/connect-link\`
with headers \`Authorization: Bearer $AGENT_API_SECRET\` and \`Content-Type: application/json\`
and body \`{"customer_id":"$AGENT_CUSTOMER_ID","provider":"<provider_name>"}\`

This returns a URL. Send it to the user so they can complete OAuth in their browser.

Available providers: github, google, slack, linear, notion, jira
EOAGENTS
    fi

    # Write openclaw config JSON (after workspace setup so gateway doesn't wipe it)
    cat > "$OPENCLAW_STATE_DIR/openclaw.json" << EOJSON
{
  "commands": {
    "native": "auto",
    "nativeSkills": "auto",
    "restart": true
  },
  "gateway": {
    "mode": "local"
  },
  "auth": {
    "profiles": {
      "default": {
        "provider": "$PROVIDER",
        "mode": "api_key"
      }
    },
    "order": {
      "*": ["default"]
    }
  },
  "agents": {
    "defaults": {
      "workspace": "$WORKSPACE_DIR",
      "model": {
        "primary": "$MODEL"
      },
      "thinkingDefault": "$THINKING"
    }
  },
  "channels": {
    "telegram": {
      "tokenFile": "$TOKEN_FILE",
      "allowFrom": [
$ALLOW_ARRAY
      ]
    }
  }
}
EOJSON

    exec ${openclaw}/bin/openclaw gateway
  '';

in n2c.buildImage {
  name   = "ghcr.io/andreabadesso/openclaw-cloud/openclaw-gateway";
  tag    = "latest";

  copyToRoot = pkgs.buildEnv {
    name  = "root";
    paths = [ caCerts pkgs.tzdata pkgs.coreutils pkgs.gnused pkgs.jq pkgs.curl ];
    pathsToLink = [ "/etc" "/share/zoneinfo" "/bin" ];
  };

  config = {
    Entrypoint = [ "${entrypoint}" ];
    Env = [
      "SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt"
      "TZ=UTC"
      "HOME=/root"
    ];
  };
}
