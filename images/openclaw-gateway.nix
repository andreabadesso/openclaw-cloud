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

    # Write system prompt as CLAUDE.md if OPENCLAW_SYSTEM_PROMPT is set
    SYSTEM_PROMPT="''${OPENCLAW_SYSTEM_PROMPT:-}"
    if [ -n "$SYSTEM_PROMPT" ]; then
      cat > "$WORKSPACE_DIR/CLAUDE.md" << EOCLAUDE
$SYSTEM_PROMPT
EOCLAUDE
    fi

    # Generate AGENTS.md and mcporter.json from OPENCLAW_CONNECTIONS if set
    WORKSPACE_DIR="/root/workspace"
    mkdir -p "$WORKSPACE_DIR"
    CONNECTIONS_JSON="''${OPENCLAW_CONNECTIONS:-}"
    if [ -n "$CONNECTIONS_JSON" ]; then
      AGENT_API_URL=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.api_url')
      AGENT_API_SECRET=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.api_secret')
      AGENT_CUSTOMER_ID=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.customer_id')

      NANGO_PROXY_URL=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.nango_proxy_url')
      NANGO_SECRET_KEY=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.nango_secret_key')

      # Process connections: native providers get env vars, MCP providers get mcporter config
      MCPORTER_SERVERS="{}"
      CONNECTED_LIST=""

      for row in $(printf '%s' "$CONNECTIONS_JSON" | jq -c '.connections[]'); do
        CONN_PROVIDER=$(printf '%s' "$row" | jq -r '.provider')
        CONN_ID=$(printf '%s' "$row" | jq -r '.connection_id')
        NATIVE_ENV=$(printf '%s' "$row" | jq -r '.native_env // empty')
        MCP_META=$(printf '%s' "$row" | jq -c '.mcp // empty')

        # Fetch fresh token from Nango
        TOKEN_RESP=$(curl -sf "$NANGO_PROXY_URL/connection/$CONN_ID?provider_config_key=$CONN_PROVIDER" \
          -H "Authorization: Bearer $NANGO_SECRET_KEY" 2>/dev/null || true)
        ACCESS_TOKEN=$(printf '%s' "$TOKEN_RESP" | jq -r '.credentials.access_token // .credentials.api_key // empty' 2>/dev/null || true)

        if [ -z "$ACCESS_TOKEN" ]; then
          CONNECTED_LIST="$CONNECTED_LIST
- **$CONN_PROVIDER** (token fetch failed)"
          continue
        fi

        # --- Native provider: inject as env var for openclaw's built-in tools ---
        if [ -n "$NATIVE_ENV" ]; then
          export "$NATIVE_ENV=$ACCESS_TOKEN"
          CONNECTED_LIST="$CONNECTED_LIST
- **$CONN_PROVIDER**: native openclaw integration (use built-in tools)"
          continue
        fi

        # --- MCP provider: build mcporter config ---
        if [ -z "$MCP_META" ]; then
          CONNECTED_LIST="$CONNECTED_LIST
- **$CONN_PROVIDER** (no integration configured)"
          continue
        fi

        MCP_TYPE=$(printf '%s' "$MCP_META" | jq -r '.type')
        if [ "$MCP_TYPE" = "http" ]; then
          MCP_BASE_URL=$(printf '%s' "$MCP_META" | jq -r '.baseUrl')
          MCPORTER_SERVERS=$(printf '%s' "$MCPORTER_SERVERS" | jq \
            --arg p "$CONN_PROVIDER" \
            --arg url "$MCP_BASE_URL" \
            --arg tok "$ACCESS_TOKEN" \
            '. + {($p): {baseUrl: $url, headers: {Authorization: ("Bearer " + $tok)}}}')
        else
          MCP_CMD=$(printf '%s' "$MCP_META" | jq -r '.command')
          MCP_ARGS=$(printf '%s' "$MCP_META" | jq -c '.args')
          MCP_TOKEN_ENV=$(printf '%s' "$MCP_META" | jq -r '.tokenEnv')
          MCPORTER_SERVERS=$(printf '%s' "$MCPORTER_SERVERS" | jq \
            --arg p "$CONN_PROVIDER" \
            --arg cmd "$MCP_CMD" \
            --argjson args "$MCP_ARGS" \
            --arg te "$MCP_TOKEN_ENV" \
            --arg tok "$ACCESS_TOKEN" \
            '. + {($p): {command: $cmd, args: $args, env: {($te): $tok}}}')
        fi

        CONNECTED_LIST="$CONNECTED_LIST
- **$CONN_PROVIDER**: \`mcporter call $CONN_PROVIDER.<tool> <args>\`"
      done

      # Write mcporter config (only if there are MCP servers)
      if [ "$MCPORTER_SERVERS" != "{}" ]; then
        mkdir -p /root/.mcporter
        printf '%s' "{\"mcpServers\": $MCPORTER_SERVERS, \"imports\": []}" > /root/.mcporter/mcporter.json
        npx mcporter@latest --version >/dev/null 2>&1 || true
      fi

      cat > "$WORKSPACE_DIR/AGENTS.md" << EOAGENTS
# External Service Connections

You have access to external services through native openclaw tools and MCP servers.

## Connected Services
$CONNECTED_LIST

## Native Integrations (GitHub, Notion, Slack)

These work through openclaw's built-in tools and skills — no special commands needed.

- **GitHub**: Use the \`github\` skill (\`gh\` CLI). Examples: \`gh issue list\`, \`gh pr create\`, \`gh repo view\`
- **Notion**: Use the \`notion\` skill. Examples: search pages, read databases, create pages
- **Slack**: Use the built-in Slack actions tool for messaging, reactions, and channel management

## MCP Integrations (Linear, Jira, Google)

These require \`mcporter\` via the \`exec\` tool.

List available tools:
\`\`\`
mcporter list <server> --schema
\`\`\`

Call a tool:
\`\`\`
mcporter call <server>.<tool> <args> --output json
\`\`\`

### Examples

\`\`\`bash
# Linear
mcporter call linear.list_issues --output json
mcporter call linear.get_issue id:ENG-123 --output json

# Jira
mcporter call jira.search_issues jql:"project = PROJ" --output json

# Google Drive
mcporter call google.search_files query:"quarterly report" --output json
\`\`\`

## Requesting New Connections

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

    # Browser proxy config — embed proxy token as Basic auth in the URL
    BROWSER_PROXY_RAW="''${OPENCLAW_BROWSER_PROXY_URL:-}"
    if [ -n "$BROWSER_PROXY_RAW" ] && [ -n "$API_KEY" ]; then
      # Insert token as username: http://TOKEN@host:port
      BROWSER_PROXY_URL=$(printf '%s' "$BROWSER_PROXY_RAW" | sed "s|://|://$API_KEY@|")
    else
      BROWSER_PROXY_URL="$BROWSER_PROXY_RAW"
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
      --arg browser_proxy "$BROWSER_PROXY_URL" \
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
      | if $browser_proxy != "" then
          .browser = {
            enabled: true,
            defaultProfile: "cloud",
            profiles: {
              cloud: { cdpUrl: $browser_proxy, color: "#00AA00" }
            }
          }
        else . end
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
                  reasoning: true,
                  input: ["text", "image"],
                  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
                  contextWindow: 262144,
                  maxTokens: 32768
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
    paths = [ caCerts pkgs.tzdata pkgs.coreutils pkgs.gnused pkgs.jq pkgs.curl pkgs.bash pkgs.nodejs_20 ];
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
