CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS alunos (
    id BIGSERIAL PRIMARY KEY,
    school_id TEXT NOT NULL,
    external_id TEXT NOT NULL,
    nome TEXT NOT NULL,
    embedding vector(512),
    archived_at TIMESTAMPTZ,
    archive_reason TEXT,
    merged_into_external_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT alunos_school_external_unique UNIQUE (school_id, external_id)
);

CREATE INDEX IF NOT EXISTS alunos_embedding_l2_idx
    ON alunos USING ivfflat (embedding vector_l2_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS alunos_school_archived_idx
    ON alunos (school_id, archived_at);

CREATE TABLE IF NOT EXISTS presencas (
    id BIGSERIAL PRIMARY KEY,
    aluno_id BIGINT NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
    school_id TEXT NOT NULL,
    external_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    nome TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS presencas_aluno_created_at_idx
    ON presencas (aluno_id, created_at DESC);

CREATE TABLE IF NOT EXISTS embeddings (
    id BIGSERIAL PRIMARY KEY,
    aluno_id BIGINT NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
    embedding vector(512) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS embeddings_aluno_idx
    ON embeddings (aluno_id);

CREATE INDEX IF NOT EXISTS embeddings_embedding_l2_idx
    ON embeddings USING ivfflat (embedding vector_l2_ops)
    WITH (lists = 100);

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
