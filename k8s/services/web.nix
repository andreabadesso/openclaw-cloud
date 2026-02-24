{ ... }:

let image = "ghcr.io/andreabadesso/openclaw-cloud/web:latest";

in {
  kubernetes.resources = {
    deployments.web = {
      metadata = { name = "web"; namespace = "platform"; };
      spec = {
        replicas = 2;
        selector.matchLabels.app = "web";
        template = {
          metadata.labels.app = "web";
          spec = {
            containers.web = {
              inherit image;
              ports = [{ containerPort = 80; protocol = "TCP"; }];
              resources = {
                requests = { cpu = "50m"; memory = "32Mi"; };
                limits   = { cpu = "200m"; memory = "64Mi"; };
              };
              readinessProbe = {
                httpGet = { path = "/"; port = 80; };
                initialDelaySeconds = 2;
              };
              livenessProbe = {
                httpGet = { path = "/"; port = 80; };
                initialDelaySeconds = 5;
              };
            };
          };
        };
      };
    };

    services.web = {
      metadata = { name = "web"; namespace = "platform"; };
      spec = {
        selector.app = "web";
        ports = [{ port = 80; targetPort = 80; protocol = "TCP"; }];
      };
    };
  };
}
