-- Pod resource metrics for per-customer analytics

CREATE TABLE IF NOT EXISTS pod_metrics_snapshots (
    id BIGSERIAL PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(id),
    box_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    cpu_millicores INTEGER NOT NULL,
    memory_bytes BIGINT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pod_metrics_snapshots_customer_time
    ON pod_metrics_snapshots(customer_id, collected_at DESC);

CREATE TABLE IF NOT EXISTS pod_metrics_hourly (
    id BIGSERIAL PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(id),
    box_id TEXT NOT NULL,
    hour TIMESTAMPTZ NOT NULL,
    avg_cpu INTEGER NOT NULL,
    max_cpu INTEGER NOT NULL,
    avg_memory BIGINT NOT NULL,
    max_memory BIGINT NOT NULL,
    sample_count INTEGER NOT NULL,
    UNIQUE (customer_id, box_id, hour)
);

CREATE INDEX idx_pod_metrics_hourly_customer_hour
    ON pod_metrics_hourly(customer_id, hour DESC);
