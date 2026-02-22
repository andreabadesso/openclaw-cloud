{ ... }:

let
  image = "ghcr.io/andreabadesso/openclaw-cloud/browser-proxy:latest";

  commonEnv = [
    { name = "DATABASE_URL";      valueFrom.secretKeyRef = { name = "platform-secrets"; key = "postgres_url";      }; }
    { name = "REDIS_URL";         valueFrom.secretKeyRef = { name = "platform-secrets"; key = "redis_url";         }; }
    { name = "BROWSERLESS_URL";   valueFrom.secretKeyRef = { name = "platform-secrets"; key = "browserless_url";   }; }
    { name = "INTERNAL_API_KEY";  valueFrom.secretKeyRef = { name = "platform-secrets"; key = "internal_api_key";  }; }
    { name = "PORT";              value = "9223"; }
    { name = "MAX_CONCURRENT_SESSIONS"; value = "2"; }
    { name = "MAX_SESSION_DURATION_MS"; value = "600000"; }
  ];

in {
  kubernetes.resources = {
    deployments.browser-proxy = {
      metadata = { name = "browser-proxy"; namespace = "platform"; };
      spec = {
        replicas = 2;
        selector.matchLabels.app = "browser-proxy";
        template = {
          metadata.labels.app = "browser-proxy";
          spec = {
            containers.browser-proxy = {
              inherit image;
              env = commonEnv;
              ports = [{ containerPort = 9223; protocol = "TCP"; }];
              resources = {
                requests = { cpu = "100m"; memory = "64Mi"; };
                limits   = { cpu = "500m"; memory = "128Mi"; };
              };
              livenessProbe.httpGet  = { path = "/health"; port = 9223; };
              readinessProbe = {
                httpGet = { path = "/health"; port = 9223; };
                initialDelaySeconds = 3;
              };
            };
          };
        };
      };
    };

    services.browser-proxy = {
      metadata = { name = "browser-proxy"; namespace = "platform"; };
      spec = {
        selector.app = "browser-proxy";
        ports = [{ port = 9223; targetPort = 9223; protocol = "TCP"; }];
      };
    };
  };
}
