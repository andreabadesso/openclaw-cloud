{ ... }:

let
  image = "ghcr.io/andreabadesso/openclaw-cloud/token-proxy:latest";

  commonEnv = [
    { name = "DATABASE_URL";    valueFrom.secretKeyRef = { name = "platform-secrets"; key = "postgres_url";    }; }
    { name = "REDIS_URL";       valueFrom.secretKeyRef = { name = "platform-secrets"; key = "redis_url";       }; }
    { name = "KIMI_API_KEY";    valueFrom.secretKeyRef = { name = "platform-secrets"; key = "kimi_api_key";    }; }
    { name = "INTERNAL_API_KEY"; valueFrom.secretKeyRef = { name = "platform-secrets"; key = "internal_api_key"; }; }
    { name = "MODEL";             value = "kimi-coding/k2p5"; }
    { name = "PORT";            value = "8080"; }
    { name = "LOG_LEVEL";       value = "info"; }
  ];

in {
  kubernetes.resources = {
    deployments.token-proxy = {
      metadata = { name = "token-proxy"; namespace = "platform"; };
      spec = {
        replicas = 3;
        selector.matchLabels.app = "token-proxy";
        template = {
          metadata.labels.app = "token-proxy";
          spec = {
            containers.token-proxy = {
              inherit image;
              env = commonEnv;
              ports = [{ containerPort = 8080; protocol = "TCP"; }];
              resources = {
                requests = { cpu = "25m"; memory = "64Mi"; };
                limits   = { cpu = "500m"; memory = "256Mi"; };
              };
              livenessProbe.httpGet  = { path = "/health"; port = 8080; };
              readinessProbe = {
                httpGet = { path = "/health"; port = 8080; };
                initialDelaySeconds = 3;
              };
            };
          };
        };
      };
    };

    services.token-proxy = {
      metadata = { name = "token-proxy"; namespace = "platform"; };
      spec = {
        selector.app = "token-proxy";
        ports = [{ port = 8080; targetPort = 8080; protocol = "TCP"; }];
      };
    };

    horizontalPodAutoscalers.token-proxy = {
      metadata = { name = "token-proxy"; namespace = "platform"; };
      spec = {
        scaleTargetRef = { apiVersion = "apps/v1"; kind = "Deployment"; name = "token-proxy"; };
        minReplicas = 3;
        maxReplicas = 12;
        metrics = [{
          type = "Resource";
          resource = { name = "cpu"; target = { type = "Utilization"; averageUtilization = 50; }; };
        }];
      };
    };
  };
}
