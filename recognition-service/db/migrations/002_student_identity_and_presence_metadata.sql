ALTER TABLE alunos
    ADD COLUMN IF NOT EXISTS school_id TEXT,
    ADD COLUMN IF NOT EXISTS external_id TEXT;

UPDATE alunos
SET
    school_id = COALESCE(NULLIF(BTRIM(school_id), ''), COALESCE(NULLIF(current_setting('app.school_id', true), ''), 'escola_1')),
    external_id = COALESCE(NULLIF(BTRIM(external_id), ''), id::text)
WHERE school_id IS NULL
   OR BTRIM(school_id) = ''
   OR external_id IS NULL
   OR BTRIM(external_id) = '';

ALTER TABLE alunos
    ALTER COLUMN school_id SET NOT NULL,
    ALTER COLUMN external_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'alunos_school_external_unique'
          AND conrelid = 'alunos'::regclass
    ) THEN
        ALTER TABLE alunos
            ADD CONSTRAINT alunos_school_external_unique UNIQUE (school_id, external_id);
    END IF;
END $$;

ALTER TABLE presencas
    ADD COLUMN IF NOT EXISTS school_id TEXT,
    ADD COLUMN IF NOT EXISTS external_id TEXT,
    ADD COLUMN IF NOT EXISTS camera_id TEXT;

UPDATE presencas p
SET
    school_id = COALESCE(NULLIF(BTRIM(p.school_id), ''), a.school_id),
    external_id = COALESCE(NULLIF(BTRIM(p.external_id), ''), a.external_id),
    camera_id = COALESCE(NULLIF(BTRIM(p.camera_id), ''), 'unknown')
FROM alunos a
WHERE p.aluno_id = a.id
  AND (
      p.school_id IS NULL
      OR BTRIM(p.school_id) = ''
      OR p.external_id IS NULL
      OR BTRIM(p.external_id) = ''
      OR p.camera_id IS NULL
      OR BTRIM(p.camera_id) = ''
  );

ALTER TABLE presencas
    ALTER COLUMN school_id SET NOT NULL,
    ALTER COLUMN external_id SET NOT NULL,
    ALTER COLUMN camera_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS presencas_identity_camera_created_at_idx
    ON presencas (school_id, camera_id, external_id, created_at DESC);

ANALYZE alunos;
ANALYZE presencas;
