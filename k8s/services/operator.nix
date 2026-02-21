{ ... }:

let image = "ghcr.io/andreabadesso/openclaw-cloud/operator:latest";

in {
  kubernetes.resources = {
    deployments.operator = {
      metadata = { name = "operator"; namespace = "platform"; };
      spec = {
        replicas = 1;
        selector.matchLabels.app = "operator";
        template = {
          metadata.labels.app = "operator";
          spec = {
            serviceAccountName = "operator";
            containers.operator = {
              inherit image;
              env = [
                { name = "POSTGRES_URL";    valueFrom.secretKeyRef = { name = "platform-secrets"; key = "postgres_url"; }; }
                { name = "REDIS_URL";       valueFrom.secretKeyRef = { name = "platform-secrets"; key = "redis_url"; }; }
                { name = "TOKEN_PROXY_URL"; value = "http://token-proxy.platform.svc.cluster.local:8080"; }
                { name = "KUBE_NAMESPACE_PREFIX"; value = "customer-"; }
                { name = "OPENCLAW_IMAGE";  value = "ghcr.io/andreabadesso/openclaw-cloud/openclaw-gateway:latest"; }
              ];
              resources = {
                requests = { cpu = "100m"; memory = "128Mi"; };
                limits   = { cpu = "500m"; memory = "256Mi"; };
              };
            };
          };
        };
      };
    };

    # RBAC — operator needs to manage namespaces, deployments, secrets
    serviceAccounts.operator = {
      metadata = { name = "operator"; namespace = "platform"; };
    };

    clusterRoles.operator = {
      metadata.name = "openclaw:operator";
      rules = [
        { apiGroups = [ "" ];       resources = [ "namespaces" "secrets" "pods" "resourcequotas" ]; verbs = [ "create" "get" "list" "delete" "patch" ]; }
        { apiGroups = [ "apps" ];   resources = [ "deployments" ];               verbs = [ "create" "get" "list" "update" "delete" "patch" ]; }
        { apiGroups = [ "networking.k8s.io" ]; resources = [ "networkpolicies" ]; verbs = [ "create" "get" "list" "delete" "patch" ]; }
      ];
    };

    clusterRoleBindings.operator = {
      metadata.name = "openclaw:operator";
      roleRef = { apiGroup = "rbac.authorization.k8s.io"; kind = "ClusterRole"; name = "openclaw:operator"; };
      subjects = [{ kind = "ServiceAccount"; name = "operator"; namespace = "platform"; }];
    };
  };
}
