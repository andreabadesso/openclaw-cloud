# Single-node k3s server (runs both control plane and workloads)
{ pkgs, config, clusterConfig, ... }:
{
  services.k3s = {
    enable      = true;
    role        = "server";
    tokenFile   = config.sops.secrets.k3s_token.path;
    extraFlags  = builtins.concatStringsSep " " [
      "--tls-san=${clusterConfig.server.publicIp}"
      "--cluster-cidr=10.42.0.0/16"
      "--service-cidr=10.43.0.0/16"
      "--disable traefik"
      "--disable servicelb"
      "--flannel-backend=host-gw"
      "--write-kubeconfig-mode=0644"
      "--node-label=openclaw/role=server"
    ];
  };

  # Open K3s API port for remote kubectl access
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
