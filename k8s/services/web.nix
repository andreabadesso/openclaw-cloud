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
              env = [
                { name = "NEXT_PUBLIC_NANGO_URL"; value = "https://nango.openclaw.trustbit.co.in"; }
                { name = "PORT";                value = "3000"; }
                { name = "API_URL";             value = "http://api.platform.svc.cluster.local:8000"; }
              ];
              ports = [{ containerPort = 3000; protocol = "TCP"; }];
              resources = {
                requests = { cpu = "100m"; memory = "128Mi"; };
                limits   = { cpu = "500m"; memory = "512Mi"; };
              };
              readinessProbe = {
                httpGet = { path = "/"; port = 3000; };
                initialDelaySeconds = 5;
              };
              livenessProbe = {
                httpGet = { path = "/"; port = 3000; };
                initialDelaySeconds = 10;
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
        ports = [{ port = 3000; targetPort = 3000; protocol = "TCP"; }];
      };
    };
  };
}
