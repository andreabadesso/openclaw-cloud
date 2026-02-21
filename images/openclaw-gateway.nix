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
    MODEL_ID="''${MODEL#*/}"
    THINKING="''${OPENCLAW_THINKING:-medium}"
    ALLOW_FROM="''${TELEGRAM_ALLOW_FROM:-0}"
    TOKEN="''${TELEGRAM_BOT_TOKEN:-}"
    API_KEY="''${KIMI_API_KEY:-}"
    BASE_URL="''${KIMI_BASE_URL:-}"

    # Write the bot token to a file
    TOKEN_FILE="$OPENCLAW_STATE_DIR/telegram-token"
    printf '%s' "$TOKEN" > "$TOKEN_FILE"

    # Build allowFrom JSON array from comma-separated string
    ALLOW_JSON=$(printf '%s' "$ALLOW_FROM" | jq -R 'split(",") | map(select(. != "") | tonumber)')

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

You have access to external services via an authenticated proxy. Use the \`exec\` tool to run \`curl\` commands.

**IMPORTANT**: The \`web_fetch\` tool does NOT support custom headers. You MUST use \`exec\` with \`curl\` for all proxy requests.

## Connected Services

$CONN_LIST

## How to Make API Calls

Use the \`exec\` tool to run curl commands against the Nango proxy at \`$NANGO_PROXY_URL/proxy\`.

Required headers for every proxy request:
\`\`\`
Authorization: Bearer $NANGO_SECRET_KEY
Connection-Id: <connection_id from the list above>
Provider-Config-Key: <provider name>
\`\`\`

### Google Drive Example

List files:
\`\`\`
curl -s "$NANGO_PROXY_URL/proxy/drive/v3/files?pageSize=10" \\
  -H "Authorization: Bearer $NANGO_SECRET_KEY" \\
  -H "Connection-Id: <google_connection_id>" \\
  -H "Provider-Config-Key: google"
\`\`\`

### Google Sheets Example

\`\`\`
curl -s "$NANGO_PROXY_URL/proxy/v4/spreadsheets/<spreadsheet_id>" \\
  -H "Authorization: Bearer $NANGO_SECRET_KEY" \\
  -H "Connection-Id: <google_connection_id>" \\
  -H "Provider-Config-Key: google"
\`\`\`

### Requesting New Connections

If the user asks for a service that is not connected:

\`\`\`
curl -s -X POST "$AGENT_API_URL/internal/agent/connect-link" \\
  -H "Authorization: Bearer $AGENT_API_SECRET" \\
  -H "Content-Type: application/json" \\
  -d '{"customer_id":"$AGENT_CUSTOMER_ID","provider":"<provider_name>"}'
\`\`\`

This returns a URL. Send it to the user so they can complete OAuth in their browser.

Available providers: github, google, slack, linear, notion, jira
EOAGENTS
    fi

    # Build openclaw config JSON using jq (avoids heredoc quoting issues)
    CONFIG=$(jq -n \
      --arg provider "$PROVIDER" \
      --arg model "$MODEL" \
      --arg model_id "$MODEL_ID" \
      --arg thinking "$THINKING" \
      --arg token_file "$TOKEN_FILE" \
      --arg workspace "$WORKSPACE_DIR" \
      --arg api_key "$API_KEY" \
      --arg base_url "$BASE_URL" \
      --argjson allow_from "$ALLOW_JSON" \
      '{
        commands: { native: "auto", nativeSkills: "auto", restart: true },
        gateway: { mode: "local" },
        auth: {
          profiles: { default: { provider: $provider, mode: "api_key" } },
          order: { "*": ["default"] }
        },
        agents: {
          defaults: {
            workspace: $workspace,
            model: { primary: $model },
            thinkingDefault: $thinking
          }
        },
        channels: {
          telegram: { tokenFile: $token_file, allowFrom: $allow_from }
        }
      }
      | if $base_url != "" then
          .models = {
            mode: "merge",
            providers: {
              ($provider): {
                baseUrl: $base_url,
                apiKey: $api_key,
                api: "openai-completions",
                models: [{
                  id: $model_id,
                  name: $model_id,
                  reasoning: false,
                  input: ["text"],
                  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
                  contextWindow: 256000,
                  maxTokens: 8192
                }]
              }
            }
          }
        else . end
      ')

    printf '%s' "$CONFIG" > "$OPENCLAW_STATE_DIR/openclaw.json"

    exec ${openclaw}/bin/openclaw gateway
  '';

in n2c.buildImage {
  name   = "ghcr.io/andreabadesso/openclaw-cloud/openclaw-gateway";
  tag    = "latest";

  copyToRoot = pkgs.buildEnv {
    name  = "root";
    paths = [ caCerts pkgs.tzdata pkgs.coreutils pkgs.gnused pkgs.jq pkgs.curl pkgs.bash ];
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
