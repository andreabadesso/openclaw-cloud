{ ... }:

let image = "nangohq/nango-server:hosted";

in {
  kubernetes.resources = {
    deployments.nango-server = {
      metadata = { name = "nango-server"; namespace = "platform"; };
      spec = {
        replicas = 1;
        selector.matchLabels.app = "nango-server";
        template = {
          metadata.labels.app = "nango-server";
          spec = {
            containers.nango-server = {
              inherit image;
              env = [
                { name = "NANGO_DB_USER";       valueFrom.secretKeyRef = { name = "platform-secrets"; key = "nango_db_user"; }; }
                { name = "NANGO_DB_PASSWORD";   valueFrom.secretKeyRef = { name = "platform-secrets"; key = "nango_db_password"; }; }
                { name = "NANGO_DB_NAME";       valueFrom.secretKeyRef = { name = "platform-secrets"; key = "nango_db_name"; }; }
                { name = "NANGO_ENCRYPTION_KEY"; valueFrom.secretKeyRef = { name = "platform-secrets"; key = "nango_encryption_key"; }; }
                { name = "NANGO_SERVER_URL";    valueFrom.secretKeyRef = { name = "platform-secrets"; key = "nango_server_url"; }; }
                { name = "NANGO_DB_HOST";       value = "postgres.platform.svc.cluster.local"; }
                { name = "NANGO_DB_PORT";       value = "5432"; }
                { name = "NANGO_REDIS_URL";     valueFrom.secretKeyRef = { name = "platform-secrets"; key = "nango_redis_url"; }; }
                { name = "FLAG_AUTH_ENABLED";   value = "false"; }
              ];
              ports = [{ containerPort = 8080; protocol = "TCP"; }];
              resources = {
                requests = { cpu = "200m"; memory = "256Mi"; };
                limits   = { cpu = "500m"; memory = "512Mi"; };
              };
              readinessProbe = {
                httpGet = { path = "/health"; port = 8080; };
                initialDelaySeconds = 10;
              };
            };
          };
        };
      };
    };

    services.nango-server = {
      metadata = { name = "nango-server"; namespace = "platform"; };
      spec = {
        selector.app = "nango-server";
        ports = [{ port = 8080; targetPort = 8080; protocol = "TCP"; }];
      };
    };
  };
}
