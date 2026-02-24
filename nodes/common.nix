# Shared NixOS config for all cluster nodes
{ pkgs, inputs, ... }: {
  imports = [
    inputs.disko.nixosModules.disko
    inputs.sops-nix.nixosModules.sops
  ];

  # Disk layout (AWS t3 NVMe + SeaBIOS/legacy BIOS)
  disko.devices.disk.main = {
    type   = "disk";
    device = "/dev/nvme0n1";
    content = {
      type = "gpt";
      partitions = {
        boot = {
          size    = "1M";
          type    = "EF02";  # BIOS boot partition (required for GPT + legacy BIOS)
        };
        root = {
          size    = "100%";
          content = { type = "filesystem"; format = "ext4"; mountpoint = "/"; };
        };
      };
    };
  };

  boot.loader.grub = {
    enable  = true;
    # device is set automatically by disko (via mirroredBoots)
  };

  # AWS Nitro/ENA kernel modules
  boot.initrd.availableKernelModules = [ "nvme" "xhci_pci" "ena" ];
  boot.kernelParams = [ "console=ttyS0,115200n8" ];

  # Networking — DHCP on the primary interface (AWS assigns IP via DHCP)
  networking.useDHCP = true;
  networking.firewall = {
    enable           = true;
    allowedTCPPorts  = [ 22 80 443 ];
    trustedInterfaces = [ "flannel.1" "cni0" ];  # K8s overlay network
  };

  # SSH authorized keys
  users.users.root.openssh.authorizedKeys.keys = [
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIES1RNV5xRvmtkoIEu6aFjjD1GBlRRDDLfh73jCKc8eM"
  ];

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
