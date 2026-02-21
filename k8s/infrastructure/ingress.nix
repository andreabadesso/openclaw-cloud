{ ... }: {
  kubernetes.resources.ingresses.platform = {
    metadata = {
      name      = "platform";
      namespace = "platform";
      annotations = {
        "cert-manager.io/cluster-issuer"              = "letsencrypt-prod";
        "nginx.ingress.kubernetes.io/ssl-redirect"    = "true";
        "nginx.ingress.kubernetes.io/proxy-read-timeout" = "300";
      };
    };
    spec = {
      ingressClassName = "nginx";
      tls = [{
        hosts      = [ "app.openclaw.cloud" "api.openclaw.cloud" "proxy.openclaw.cloud" ];
        secretName = "openclaw-tls";
      }];
      rules = [
        {
          host = "app.openclaw.cloud";
          http.paths = [{
            path     = "/";
            pathType = "Prefix";
            backend.service = { name = "web";  port.number = 3000; };
          }];
        }
        {
          host = "api.openclaw.cloud";
          http.paths = [{
            path     = "/";
            pathType = "Prefix";
            backend.service = { name = "api";  port.number = 8000; };
          }];
        }
        {
          host = "proxy.openclaw.cloud";
          http.paths = [{
            path     = "/";
            pathType = "Prefix";
            backend.service = { name = "token-proxy"; port.number = 8080; };
          }];
        }
      ];
    };
  };
}
