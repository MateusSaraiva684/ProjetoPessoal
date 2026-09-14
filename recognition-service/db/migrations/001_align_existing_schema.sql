CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE alunos
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;

UPDATE alunos
SET created_at = COALESCE(created_at, now())
WHERE created_at IS NULL;

ALTER TABLE alunos
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN created_at SET NOT NULL,
    ALTER COLUMN nome SET NOT NULL,
    ALTER COLUMN embedding SET NOT NULL;

ALTER TABLE presencas
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'presencas'
          AND column_name = 'data'
    ) THEN
        EXECUTE 'UPDATE presencas
                 SET created_at = COALESCE(created_at, data AT TIME ZONE ''UTC'', now())
                 WHERE created_at IS NULL';
    ELSE
        UPDATE presencas
        SET created_at = COALESCE(created_at, now())
        WHERE created_at IS NULL;
    END IF;
END $$;

ALTER TABLE presencas
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN created_at SET NOT NULL,
    ALTER COLUMN aluno_id SET NOT NULL,
    ALTER COLUMN nome SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'presencas_aluno_id_fkey'
          AND conrelid = 'presencas'::regclass
    ) THEN
        ALTER TABLE presencas
            ADD CONSTRAINT presencas_aluno_id_fkey
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE;
    END IF;
END $$;

ALTER TABLE embeddings
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;

UPDATE embeddings
SET created_at = COALESCE(created_at, now())
WHERE created_at IS NULL;

ALTER TABLE embeddings
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN created_at SET NOT NULL,
    ALTER COLUMN aluno_id SET NOT NULL,
    ALTER COLUMN embedding SET NOT NULL;

CREATE INDEX IF NOT EXISTS alunos_embedding_l2_idx
    ON alunos USING ivfflat (embedding vector_l2_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS presencas_aluno_created_at_idx
    ON presencas (aluno_id, created_at DESC);

CREATE INDEX IF NOT EXISTS embeddings_aluno_idx
    ON embeddings (aluno_id);

ANALYZE alunos;
ANALYZE presencas;
ANALYZE embeddings;
