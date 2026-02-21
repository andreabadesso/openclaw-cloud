-- Connections feature migration
ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'update_connections';

CREATE TABLE customer_connections (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         UUID NOT NULL REFERENCES customers(id),
    provider            TEXT NOT NULL,
    nango_connection_id TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_customer_connections_active
    ON customer_connections (customer_id, provider) WHERE (status = 'active');
CREATE INDEX idx_customer_connections_customer
    ON customer_connections(customer_id) WHERE status = 'active';
