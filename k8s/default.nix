# kubenix entry point — imports all platform service manifests
{ inputs, ... }:

{
  imports = [
    inputs.kubenix.modules.k8s

    ./namespaces.nix
    ./infrastructure/redis.nix
    ./infrastructure/ingress.nix
    ./services/api.nix
    ./services/web.nix
    ./services/token-proxy.nix
    ./services/operator.nix
    ./services/onboarding-agent.nix
    ./services/billing-worker.nix
  ];

  kubernetes.version = "1.31";
}
