# Shared NixOS config for all cluster nodes
{ pkgs, inputs, ... }: {
  imports = [
    inputs.disko.nixosModules.disko
    inputs.sops-nix.nixosModules.sops
  ];

  # Disk layout (Hetzner cloud BIOS VMs)
  disko.devices.disk.sda = {
    type   = "disk";
    device = "/dev/sda";
    content = {
      type = "gpt";
      partitions = {
        boot = { size = "1M";   type = "EF02"; };
        root = { size = "100%"; content = { type = "filesystem"; format = "ext4"; mountpoint = "/"; }; };
      };
    };
  };

  boot.loader.grub = { enable = true; device = "/dev/sda"; };

  # Networking
  networking.firewall = {
    enable           = true;
    allowedTCPPorts  = [ 22 ];          # K3s opens its own ports
    trustedInterfaces = [ "flannel.1" "cni0" ];  # K8s overlay network
  };

  # Nix settings
  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    trusted-users          = [ "root" ];
  };
  nix.gc = { automatic = true; dates = "weekly"; options = "--delete-older-than 14d"; };

  # Base packages
  environment.systemPackages = with pkgs; [ vim curl wget htop git jq ];

  # SSH hardening
  services.openssh = {
    enable                 = true;
    settings.PasswordAuthentication = false;
    settings.PermitRootLogin        = "prohibit-password";
  };

  # SOPS secrets — token shared with all cluster nodes
  sops.defaultSopsFile  = ../secrets/cluster.yaml;
  sops.age.sshKeyPaths  = [ "/etc/ssh/ssh_host_ed25519_key" ];
  sops.secrets.k3s_token = {};

  system.stateVersion = "25.11";
}
