# K3s control plane node
{ pkgs, config, ... }: {
  networking.hostName = "openclaw-cp-1";

  services.k3s = {
    enable      = true;
    role        = "server";
    tokenFile   = config.sops.secrets.k3s_token.path;
    extraFlags  = builtins.concatStringsSep " " [
      "--disable traefik"             # we run ingress-nginx instead
      "--disable servicelb"           # we use MetalLB or Hetzner CCM
      "--flannel-backend=wireguard-native"
      "--node-label=openclaw/role=control-plane"
    ];
  };

  # Open K3s API port to workers only (private network)
  networking.firewall.allowedTCPPorts = [ 6443 ];

  # etcd backup via systemd timer
  systemd.services.etcd-backup = {
    description = "K3s etcd snapshot backup";
    script = ''
      ${pkgs.k3s}/bin/k3s etcd-snapshot save \
        --name "snapshot-$(date +%Y%m%d-%H%M%S)"
    '';
    serviceConfig.Type = "oneshot";
  };
  systemd.timers.etcd-backup = {
    wantedBy = [ "timers.target" ];
    timerConfig = { OnCalendar = "daily"; Persistent = true; };
  };
}
