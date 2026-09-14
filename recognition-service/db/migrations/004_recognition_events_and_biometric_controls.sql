ALTER TABLE alunos
    ALTER COLUMN embedding DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archive_reason TEXT,
    ADD COLUMN IF NOT EXISTS merged_into_external_id TEXT;

CREATE INDEX IF NOT EXISTS alunos_school_archived_idx
    ON alunos (school_id, archived_at);

CREATE TABLE IF NOT EXISTS recognition_events (
    id BIGSERIAL PRIMARY KEY,
    status TEXT NOT NULL,
    school_id TEXT NOT NULL,
    external_id TEXT,
    camera_id TEXT NOT NULL,
    aluno_id BIGINT REFERENCES alunos(id) ON DELETE SET NULL,
    face_sample_id BIGINT,
    confidence DOUBLE PRECISION,
    distance DOUBLE PRECISION,
    presence_id BIGINT REFERENCES presencas(id) ON DELETE SET NULL,
    candidates JSONB,
    webhook_sent BOOLEAN NOT NULL DEFAULT false,
    webhook_error TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recognition_events_school_created_at_idx
    ON recognition_events (school_id, created_at DESC);

CREATE INDEX IF NOT EXISTS recognition_events_camera_created_at_idx
    ON recognition_events (camera_id, created_at DESC);

CREATE INDEX IF NOT EXISTS recognition_events_external_created_at_idx
    ON recognition_events (external_id, created_at DESC);

CREATE INDEX IF NOT EXISTS recognition_events_status_created_at_idx
    ON recognition_events (status, created_at DESC);

ANALYZE alunos;
ANALYZE recognition_events;
