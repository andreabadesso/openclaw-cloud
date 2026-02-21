{ ... }:

let image = "ghcr.io/andreabadesso/openclaw-cloud/onboarding-agent:latest";

in {
  kubernetes.resources = {
    deployments.onboarding-agent = {
      metadata = { name = "onboarding-agent"; namespace = "platform"; };
      spec = {
        replicas = 2;
        selector.matchLabels.app = "onboarding-agent";
        template = {
          metadata.labels.app = "onboarding-agent";
          spec = {
            containers.onboarding-agent = {
              inherit image;
              env = [
                { name = "REDIS_URL";     valueFrom.secretKeyRef = { name = "platform-secrets"; key = "redis_url"; }; }
                { name = "POSTGRES_URL";  valueFrom.secretKeyRef = { name = "platform-secrets"; key = "postgres_url"; }; }
                { name = "KIMI_API_KEY";  valueFrom.secretKeyRef = { name = "platform-secrets"; key = "kimi_api_key"; }; }
                { name = "KIMI_BASE_URL"; value = "https://api.moonshot.cn/v1"; }
                { name = "API_INTERNAL_URL"; value = "http://api.platform.svc.cluster.local:8000"; }
                { name = "PORT"; value = "9000"; }
              ];
              ports = [{ containerPort = 9000; }];
              resources = {
                requests = { cpu = "500m"; memory = "512Mi"; };
                limits   = { cpu = "2000m"; memory = "2Gi"; };
              };
            };
          };
        };
      };
    };

    services.onboarding-agent = {
      metadata = { name = "onboarding-agent"; namespace = "platform"; };
      spec = {
        selector.app = "onboarding-agent";
        ports = [{ port = 9000; targetPort = 9000; }];
      };
    };
  };
}
