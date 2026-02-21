# K3s worker node
{ config, lib, ... }: {
  # hostname set per-node in colmena config via networking.hostName

  services.k3s = {
    enable      = true;
    role        = "agent";
    tokenFile   = config.sops.secrets.k3s_token.path;
    serverAddr  = "https://10.0.0.10:6443";   # control-plane IP
    extraFlags  = "--node-label=openclaw/role=worker";
  };

  # Workers need no inbound ports — K3s handles its own flannel UDP
  networking.firewall.allowedUDPPorts = [ 8472 ];   # VXLAN / WireGuard
}
