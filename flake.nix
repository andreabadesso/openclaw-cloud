{
  description = "openclaw-cloud — managed OpenClaw SaaS platform";

  inputs = {
    nixpkgs.url     = "github:nixos/nixpkgs/nixos-unstable";
    colmena.url     = "github:zhaofengli/colmena";
    disko           = { url = "github:nix-community/disko";      inputs.nixpkgs.follows = "nixpkgs"; };
    sops-nix        = { url = "github:Mic92/sops-nix";           inputs.nixpkgs.follows = "nixpkgs"; };
    nix2container   = { url = "github:nlewo/nix2container";      inputs.nixpkgs.follows = "nixpkgs"; };
    kubenix         = { url = "github:hall/kubenix";             inputs.nixpkgs.follows = "nixpkgs"; };
    nix-openclaw    = { url = "github:openclaw/nix-openclaw";    inputs.nixpkgs.follows = "nixpkgs"; };
  };

  outputs = { self, nixpkgs, colmena, disko, sops-nix, nix2container, kubenix, nix-openclaw, ... }@inputs:
  let
    system = "x86_64-linux";
    pkgs   = nixpkgs.legacyPackages.${system};
    n2c    = nix2container.packages.${system}.nix2container;

    # Load cluster node IPs from a gitignored file so secrets stay out of the repo.
    # Copy cluster.example.json → cluster.json and fill in your IPs.
    clusterConfig = builtins.fromJSON (builtins.readFile ./cluster.json);
  in
  {
    # ─── NixOS configurations (used by nixos-anywhere + colmena) ─────────────
    nixosConfigurations.server-1 = nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = { inherit inputs self clusterConfig; };
      modules = [
        ./nodes/common.nix
        ./nodes/server.nix
        { networking.hostName = "openclaw-prod"; }
      ];
    };

    # ─── K8s cluster nodes (NixOS, managed by Colmena) ──────────────────────
    colmena = {
      meta = {
        nixpkgs     = pkgs;
        specialArgs = { inherit inputs self clusterConfig; };
      };

      server-1 = {
        deployment.targetHost = clusterConfig.server.publicIp;
        deployment.targetUser = "root";
        imports = [
          ./nodes/common.nix
          ./nodes/server.nix
        ];
        networking.hostName = "openclaw-prod";
      };
    };

    # ─── Packages ──────────────────────────────────────────────────────────
    packages.${system} = {
      # Kubernetes platform manifests (kubenix)
      k8s-manifests =
        (kubenix.evalModules.${system} {
          module = import ./k8s { inherit inputs; };
        }).config.kubernetes.result;

      # OpenClaw container image (nix2container)
      openclaw-image =
        import ./images/openclaw-gateway.nix { inherit pkgs n2c nix-openclaw; };
    };

    # ─── Dev shell ──────────────────────────────────────────────────────────
    devShells.${system}.default = pkgs.mkShell {
      name = "openclaw-cloud";
      packages = with pkgs; [
        colmena.packages.${system}.colmena
        kubectl
        k9s
        kubernetes-helm
        kubie                 # kubectl context switcher
        sops
        age
        jq
        yq-go
        (python312.withPackages (ps: with ps; [ httpx rich typer ]))
      ];
      shellHook = ''
        echo "openclaw-cloud dev shell"
        echo "  colmena apply          — deploy NixOS cluster nodes"
        echo "  nix build .#k8s-manifests  — build K8s manifests"
        echo "  nix build .#openclaw-image — build container image"
      '';
    };
  };
}
