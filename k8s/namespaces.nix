{ ... }: {
  kubernetes.resources.namespaces = {
    platform    = { metadata.name = "platform"; };
    monitoring  = { metadata.name = "monitoring"; };
    # Customer namespaces are created dynamically by the operator
    # Pattern: customer-{customer_id}
  };
}
