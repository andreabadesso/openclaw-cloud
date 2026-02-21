# K3s worker node
{ config, lib, inputs, ... }:

let
  clusterConfig = builtins.fromJSON (builtins.readFile ../cluster.json);
in {
  # hostname set per-node in colmena config via networking.hostName

  services.k3s = {
    enable      = true;
    role        = "agent";
    tokenFile   = config.sops.secrets.k3s_token.path;
    serverAddr  = "https://${clusterConfig.controlPlane.ip}:6443";
    extraFlags  = builtins.concatStringsSep " " [
      "--node-label=openclaw/role=worker"
      "--flannel-iface=ens10"
    ];
  };

  # Workers need no inbound ports — K3s handles its own flannel UDP
  networking.firewall.allowedUDPPorts = [ 8472 ];   # VXLAN / WireGuard
}
