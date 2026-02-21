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

    # Write openclaw config JSON
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

    # Generate AGENTS.md from OPENCLAW_CONNECTIONS if set
    WORKSPACE_DIR="$OPENCLAW_STATE_DIR/workspace"
    mkdir -p "$WORKSPACE_DIR"
    CONNECTIONS_JSON="''${OPENCLAW_CONNECTIONS:-}"
    if [ -n "$CONNECTIONS_JSON" ]; then
      AGENT_API_URL=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.api_url')
      AGENT_API_SECRET=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.api_secret')
      AGENT_CUSTOMER_ID=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.customer_id')

      cat > "$WORKSPACE_DIR/AGENTS.md" << 'EOAGENTS'
# External Service Connections

You can connect to external services (GitHub, Slack, Linear, Google, Notion, Jira)
on behalf of the user via authenticated API calls through a proxy.

## Step 1: Check available connections

Before making any external API call, first check which services are connected:

```bash
curl -s __API_URL__/internal/agent/connections \
  -H "Authorization: Bearer __API_SECRET__" \
  -H "X-Customer-Id: __CUSTOMER_ID__"
```

This returns JSON with:
- `connections`: list of connected providers with `connection_id`, plus a `proxy_url` and headers to use
- `available_providers`: list of providers the user could connect but hasn't yet

## Step 2: Make API calls through the proxy

Use the `proxy_url`, `connection_id`, and `headers` from the response above.
The response includes ready-to-use curl examples for each connected provider.

## Step 3: Request new connections

If you need a service that isn't connected, generate a one-click OAuth link:

```bash
curl -s -X POST __API_URL__/internal/agent/connect-link \
  -H "Authorization: Bearer __API_SECRET__" \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"__CUSTOMER_ID__","provider":"<provider_name>"}'
```

This returns `{"url":"..."}`. Send that URL to the user — they click it,
complete OAuth in their browser, and the connection becomes available shortly after.

Available providers: github, google, slack, linear, notion, jira
EOAGENTS

      # Substitute placeholders with actual values
      sed -i "s|__API_URL__|$AGENT_API_URL|g;s|__API_SECRET__|$AGENT_API_SECRET|g;s|__CUSTOMER_ID__|$AGENT_CUSTOMER_ID|g" "$WORKSPACE_DIR/AGENTS.md"
    fi

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
