{ pkgs, n2c, nix-openclaw }:

let
  openclaw = nix-openclaw.packages.x86_64-linux.default;

  # Minimal CA certs so TLS works (Telegram + Kimi API)
  caCerts = pkgs.cacert;

  # Tiny entrypoint wrapper — reads env vars injected by K8s Secret
  entrypoint = pkgs.writeShellScript "entrypoint" ''
    set -euo pipefail
    exec ${openclaw}/bin/openclaw-gateway "$@"
  '';

in n2c.buildImage {
  name   = "ghcr.io/andreabadesso/openclaw-cloud/openclaw-gateway";
  tag    = "latest";

  # Only what the process needs — no shell, no package manager
  copyToRoot = pkgs.buildEnv {
    name  = "root";
    paths = [ caCerts pkgs.tzdata ];
    pathsToLink = [ "/etc" "/share/zoneinfo" ];
  };

  config = {
    Entrypoint = [ "${entrypoint}" ];
    Env = [
      "SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt"
      "TZ=UTC"
    ];
    # These are provided by K8s Secret at runtime:
    # KIMI_API_KEY, KIMI_BASE_URL, TELEGRAM_BOT_TOKEN,
    # TELEGRAM_ALLOW_FROM, OPENCLAW_MODEL, OPENCLAW_THINKING
  };
}
