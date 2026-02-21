{ ... }: {
  kubernetes.resources = {
    configMaps.postgres-init = {
      metadata = { name = "postgres-init"; namespace = "platform"; };
      data = {
        "000_init-multiple-dbs.sh" = builtins.readFile ../../db/init-multiple-dbs.sh;
        "001_initial.sql"          = builtins.readFile ../../db/migrations/001_initial.sql;
        "002_connections.sql"      = builtins.readFile ../../db/migrations/002_connections.sql;
      };
    };

    statefulSets.postgres = {
      metadata = { name = "postgres"; namespace = "platform"; };
      spec = {
        serviceName = "postgres";
        replicas    = 1;
        selector.matchLabels.app = "postgres";
        template = {
          metadata.labels.app = "postgres";
          spec = {
            containers.postgres = {
              image = "postgres:16-alpine";
              env = [
                { name = "POSTGRES_USER";     valueFrom.secretKeyRef = { name = "platform-secrets"; key = "postgres_user"; }; }
                { name = "POSTGRES_PASSWORD"; valueFrom.secretKeyRef = { name = "platform-secrets"; key = "postgres_password"; }; }
                { name = "POSTGRES_DB";       valueFrom.secretKeyRef = { name = "platform-secrets"; key = "postgres_db"; }; }
                { name = "PGDATA";            value = "/var/lib/postgresql/data/pgdata"; }
              ];
              ports = [{ containerPort = 5432; }];
              resources = {
                requests = { cpu = "200m"; memory = "256Mi"; };
                limits   = { cpu = "1000m"; memory = "1Gi"; };
              };
              readinessProbe = {
                exec.command = [ "pg_isready" "-U" "openclaw" ];
                initialDelaySeconds = 5;
                periodSeconds = 5;
              };
              volumeMounts = [
                { name = "data"; mountPath = "/var/lib/postgresql/data"; }
                { name = "init"; mountPath = "/docker-entrypoint-initdb.d"; readOnly = true; }
              ];
            };
            volumes = [{
              name = "init";
              configMap.name = "postgres-init";
            }];
          };
        };
        volumeClaimTemplates = [{
          metadata.name = "data";
          spec = {
            accessModes = [ "ReadWriteOnce" ];
            resources.requests.storage = "10Gi";
          };
        }];
      };
    };

    services.postgres = {
      metadata = { name = "postgres"; namespace = "platform"; };
      spec = {
        selector.app = "postgres";
        ports = [{ port = 5432; targetPort = 5432; }];
        clusterIP = "None";  # headless for StatefulSet
      };
    };
  };
}
