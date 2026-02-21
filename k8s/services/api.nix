{ ... }:

let image = "ghcr.io/andreabadesso/openclaw-cloud/api:latest";

in {
  kubernetes.resources = {
    deployments.api = {
      metadata = { name = "api"; namespace = "platform"; };
      spec = {
        replicas = 2;
        selector.matchLabels.app = "api";
        template = {
          metadata.labels.app = "api";
          spec = {
            containers.api = {
              inherit image;
              env = [
                { name = "POSTGRES_URL";     valueFrom.secretKeyRef = { name = "platform-secrets"; key = "postgres_url"; }; }
                { name = "REDIS_URL";        valueFrom.secretKeyRef = { name = "platform-secrets"; key = "redis_url"; }; }
                { name = "JWT_SECRET";       valueFrom.secretKeyRef = { name = "platform-secrets"; key = "jwt_secret"; }; }
                { name = "STRIPE_SECRET";    valueFrom.secretKeyRef = { name = "platform-secrets"; key = "stripe_secret_key"; }; }
                { name = "STRIPE_WEBHOOK_SECRET"; valueFrom.secretKeyRef = { name = "platform-secrets"; key = "stripe_webhook_secret"; }; }
                { name = "REDIS_OPERATOR_QUEUE"; value = "operator:jobs"; }
                { name = "PORT";             value = "8000"; }
              ];
              ports = [{ containerPort = 8000; protocol = "TCP"; }];
              resources = {
                requests = { cpu = "200m"; memory = "256Mi"; };
                limits   = { cpu = "1000m"; memory = "1Gi"; };
              };
              readinessProbe = {
                httpGet = { path = "/health"; port = 8000; };
                initialDelaySeconds = 5;
              };
            };
          };
        };
      };
    };

    services.api = {
      metadata = { name = "api"; namespace = "platform"; };
      spec = {
        selector.app = "api";
        ports = [{ port = 8000; targetPort = 8000; protocol = "TCP"; }];
      };
    };
  };
}
