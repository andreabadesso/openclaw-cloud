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

    # Generate workspace files from bundle prompts and connections
    WORKSPACE_DIR="/root/workspace"
    mkdir -p "$WORKSPACE_DIR"

    # Write bundle prompts as workspace markdown files
    BUNDLE_PROMPTS="''${OPENCLAW_BUNDLE_PROMPTS:-}"
    if [ -n "$BUNDLE_PROMPTS" ]; then
      # Map known keys to filenames, write each as a .md file
      for key in $(printf '%s' "$BUNDLE_PROMPTS" | jq -r 'keys[]'); do
        content=$(printf '%s' "$BUNDLE_PROMPTS" | jq -r --arg k "$key" '.[$k]')
        case "$key" in
          soul)    fname="CLAUDE.md" ;;
          rules)   fname="SOUL.md" ;;
          tools)   fname="TOOLS.md" ;;
          identity) fname="IDENTITY.md" ;;
          *)       fname="$key.md" ;;
        esac
        printf '%s\n' "$content" > "$WORKSPACE_DIR/$fname"
      done
    fi

    # Backward compat: write OPENCLAW_SYSTEM_PROMPT as CLAUDE.md if no bundle prompts
    SYSTEM_PROMPT="''${OPENCLAW_SYSTEM_PROMPT:-}"
    if [ -z "$BUNDLE_PROMPTS" ] && [ -n "$SYSTEM_PROMPT" ]; then
      printf '%s\n' "$SYSTEM_PROMPT" > "$WORKSPACE_DIR/CLAUDE.md"
    fi

    # Read bundle MCP servers for merging with connection-derived MCP servers later
    BUNDLE_MCP_SERVERS="''${OPENCLAW_BUNDLE_MCP_SERVERS:-}"

    CONNECTIONS_JSON="''${OPENCLAW_CONNECTIONS:-}"
    if [ -n "$CONNECTIONS_JSON" ]; then
      AGENT_API_URL=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.api_url')
      AGENT_API_SECRET=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.api_secret')
      AGENT_CUSTOMER_ID=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.customer_id')

      NANGO_PROXY_URL=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.nango_proxy_url')
      NANGO_SECRET_KEY=$(printf '%s' "$CONNECTIONS_JSON" | jq -r '.nango_secret_key')

      # Process connections at startup: native providers need env vars set before
      # the process starts, MCP providers need mcporter config written to disk.
      MCPORTER_SERVERS="{}"

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
          continue
        fi

        # Native provider: inject as env var for openclaw's built-in tools
        if [ -n "$NATIVE_ENV" ]; then
          export "$NATIVE_ENV=$ACCESS_TOKEN"
          continue
        fi

        # MCP provider: build mcporter config
        if [ -z "$MCP_META" ]; then continue; fi

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
      done

      # Merge bundle MCP servers with connection-derived MCP servers
      if [ -n "$BUNDLE_MCP_SERVERS" ]; then
        MCPORTER_SERVERS=$(printf '%s' "$BUNDLE_MCP_SERVERS" | jq -c ". + $MCPORTER_SERVERS")
      fi

      # Write mcporter config (only if there are MCP servers)
      if [ "$MCPORTER_SERVERS" != "{}" ]; then
        mkdir -p /root/.mcporter
        printf '%s' "{\"mcpServers\": $MCPORTER_SERVERS, \"imports\": []}" > /root/.mcporter/mcporter.json
        npx mcporter@latest --version >/dev/null 2>&1 || true
      fi

      # Only write default SOUL.md/TOOLS.md/IDENTITY.md if bundle didn't provide them
      if [ -z "$BUNDLE_PROMPTS" ] || { [ ! -f "$WORKSPACE_DIR/SOUL.md" ] && [ ! -f "$WORKSPACE_DIR/CLAUDE.md" ]; }; then
        # Write SOUL.md — persona and critical behavioral rules (gets special priority)
        if [ ! -f "$WORKSPACE_DIR/SOUL.md" ]; then
          cat > "$WORKSPACE_DIR/SOUL.md" << 'EOSOUL'
You are a helpful assistant with access to external services.

CRITICAL INSTRUCTION - READ CAREFULLY:
When the user asks about Google Drive, GitHub, Slack, Linear, Notion, Jira, or any external service:
1. Do NOT use sessions_spawn
2. Do NOT use agents_list
3. Do NOT say you don't have access
4. Instead, use the "exec" tool to run a curl command (see TOOLS.md for the exact command)
EOSOUL
        fi
      fi

      # Always write TOOLS.md with connection commands (unless bundle already provides it)
      if [ ! -f "$WORKSPACE_DIR/TOOLS.md" ]; then
        cat > "$WORKSPACE_DIR/TOOLS.md" << EOTOOLS
# How to access external services

Use the exec tool to run these curl commands. Replace PROVIDER_NAME with: google, github, slack, linear, notion, or jira.

## Check available connections
exec curl -s "$AGENT_API_URL/internal/agent/connections" -H "Authorization: Bearer $AGENT_API_SECRET" -H "X-Customer-Id: $AGENT_CUSTOMER_ID"

## Request a new connection (if not connected yet)
exec curl -s -X POST "$AGENT_API_URL/internal/agent/connect-link" -H "Authorization: Bearer $AGENT_API_SECRET" -H "Content-Type: application/json" -d '{"customer_id":"$AGENT_CUSTOMER_ID","provider":"PROVIDER_NAME"}'

Send the returned URL to the user so they can authorize the service.
EOTOOLS
      fi

      # Write IDENTITY.md only if not already provided by bundle
      if [ ! -f "$WORKSPACE_DIR/IDENTITY.md" ]; then
        cat > "$WORKSPACE_DIR/IDENTITY.md" << 'EOIDENTITY'
IMPORTANT: You have access to external services (Google Drive, GitHub, etc.) through the exec tool and curl commands described in TOOLS.md. Always check TOOLS.md before saying you cannot access a service. Never use sessions_spawn or agents_list for external services.
EOIDENTITY
      fi
    fi

    # Install bundle skills via clawhub
    BUNDLE_SKILLS="''${OPENCLAW_BUNDLE_SKILLS:-}"
    if [ -n "$BUNDLE_SKILLS" ]; then
      for slug in $(printf '%s' "$BUNDLE_SKILLS" | jq -r '.[]'); do
        echo "Installing skill: $slug"
        npx clawhub@latest install "$slug" --workspace "$WORKSPACE_DIR" 2>&1 || echo "Warning: failed to install skill $slug"
      done
    fi

    # Browser proxy config — pass proxy token as query param to avoid
    # Node.js fetch() rejecting URLs with embedded credentials
    BROWSER_PROXY_RAW="''${OPENCLAW_BROWSER_PROXY_URL:-}"
    if [ -n "$BROWSER_PROXY_RAW" ] && [ -n "$API_KEY" ]; then
      BROWSER_PROXY_URL="''${BROWSER_PROXY_RAW}?token=$API_KEY"
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
            remoteCdpTimeoutMs: 5000,
            remoteCdpHandshakeTimeoutMs: 10000,
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
