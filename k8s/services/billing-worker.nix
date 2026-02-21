{ ... }:

let image = "ghcr.io/andreabadesso/openclaw-cloud/billing-worker:latest";

in {
  kubernetes.resources = {
    deployments.billing-worker = {
      metadata = { name = "billing-worker"; namespace = "platform"; };
      spec = {
        replicas = 1;
        selector.matchLabels.app = "billing-worker";
        template = {
          metadata.labels.app = "billing-worker";
          spec = {
            containers.billing-worker = {
              inherit image;
              env = [
                { name = "POSTGRES_URL";           valueFrom.secretKeyRef = { name = "platform-secrets"; key = "postgres_url"; }; }
                { name = "REDIS_URL";              valueFrom.secretKeyRef = { name = "platform-secrets"; key = "redis_url"; }; }
                { name = "STRIPE_SECRET";          valueFrom.secretKeyRef = { name = "platform-secrets"; key = "stripe_secret_key"; }; }
                { name = "STRIPE_WEBHOOK_SECRET";  valueFrom.secretKeyRef = { name = "platform-secrets"; key = "stripe_webhook_secret"; }; }
                { name = "REDIS_OPERATOR_QUEUE";   value = "operator:jobs"; }
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
  };
}
