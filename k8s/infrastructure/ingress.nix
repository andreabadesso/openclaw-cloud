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
        hosts      = [ "app.openclaw.trustbit.co.in" "api.openclaw.trustbit.co.in" "proxy.openclaw.trustbit.co.in" "nango.openclaw.trustbit.co.in" ];
        secretName = "openclaw-tls";
      }];
      rules = [
        {
          host = "app.openclaw.trustbit.co.in";
          http.paths = [{
            path     = "/";
            pathType = "Prefix";
            backend.service = { name = "web";  port.number = 80; };
          }];
        }
        {
          host = "api.openclaw.trustbit.co.in";
          http.paths = [{
            path     = "/";
            pathType = "Prefix";
            backend.service = { name = "api";  port.number = 8000; };
          }];
        }
        {
          host = "proxy.openclaw.trustbit.co.in";
          http.paths = [{
            path     = "/";
            pathType = "Prefix";
            backend.service = { name = "token-proxy"; port.number = 8080; };
          }];
        }
        {
          host = "nango.openclaw.trustbit.co.in";
          http.paths = [{
            path     = "/";
            pathType = "Prefix";
            backend.service = { name = "nango-server"; port.number = 8080; };
          }];
        }
      ];
    };
  };
}
