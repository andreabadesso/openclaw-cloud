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

    exec ${openclaw}/bin/openclaw gateway
  '';

in n2c.buildImage {
  name   = "ghcr.io/andreabadesso/openclaw-cloud/openclaw-gateway";
  tag    = "latest";

  copyToRoot = pkgs.buildEnv {
    name  = "root";
    paths = [ caCerts pkgs.tzdata pkgs.coreutils pkgs.gnused ];
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
