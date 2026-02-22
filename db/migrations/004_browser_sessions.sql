-- Browser session tracking for the browser-proxy service
CREATE TABLE IF NOT EXISTS browser_sessions (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,
    box_id TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    duration_ms INTEGER
);

CREATE INDEX idx_browser_sessions_customer ON browser_sessions(customer_id);
CREATE INDEX idx_browser_sessions_started ON browser_sessions(started_at);
