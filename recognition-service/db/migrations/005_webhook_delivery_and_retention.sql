CREATE TABLE IF NOT EXISTS webhook_deliveries (
    event_id TEXT PRIMARY KEY,
    presence_id BIGINT NOT NULL REFERENCES presencas(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    next_attempt_at TIMESTAMPTZ,
    last_error TEXT,
    dead_lettered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS webhook_deliveries_retry_idx
    ON webhook_deliveries (status, next_attempt_at);
