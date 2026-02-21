{ ... }: {
  kubernetes.resources = {
    statefulSets.redis = {
      metadata = { name = "redis"; namespace = "platform"; };
      spec = {
        serviceName = "redis";
        replicas    = 1;
        selector.matchLabels.app = "redis";
        template = {
          metadata.labels.app = "redis";
          spec = {
            containers.redis = {
              image = "redis:7-alpine";
              command = [
                "redis-server"
                "--requirepass" "$(REDIS_PASSWORD)"
                "--appendonly" "yes"
                "--maxmemory" "512mb"
                "--maxmemory-policy" "allkeys-lru"
              ];
              env.REDIS_PASSWORD = {
                valueFrom.secretKeyRef = { name = "redis-secret"; key = "password"; };
              };
              ports = [{ containerPort = 6379; }];
              resources = {
                requests = { cpu = "100m"; memory = "128Mi"; };
                limits   = { cpu = "500m"; memory = "768Mi"; };
              };
              volumeMounts = [{ name = "data"; mountPath = "/data"; }];
            };
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

    services.redis = {
      metadata = { name = "redis"; namespace = "platform"; };
      spec = {
        selector.app = "redis";
        ports = [{ port = 6379; targetPort = 6379; }];
        clusterIP = "None";  # headless for StatefulSet
      };
    };
  };
}
