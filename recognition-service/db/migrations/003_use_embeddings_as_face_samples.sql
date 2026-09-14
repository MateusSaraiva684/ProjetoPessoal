INSERT INTO embeddings (aluno_id, embedding, created_at)
SELECT a.id, a.embedding, COALESCE(a.created_at, now())
FROM alunos a
WHERE NOT EXISTS (
    SELECT 1
    FROM embeddings e
    WHERE e.aluno_id = a.id
);

CREATE INDEX IF NOT EXISTS embeddings_embedding_l2_idx
    ON embeddings USING ivfflat (embedding vector_l2_ops)
    WITH (lists = 100);

ANALYZE embeddings;
