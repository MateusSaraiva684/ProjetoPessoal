"""Exclui embeddings expirados para cumprir a politica de retencao."""

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone

from app.core.config import BIOMETRIC_RETENTION_DAYS
from app.core.database import get_connection

logger = logging.getLogger(__name__)


def purge_expired_embeddings() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=BIOMETRIC_RETENTION_DAYS)
    deleted = 0
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM embeddings WHERE created_at < %s RETURNING aluno_id",
                    (cutoff,),
                )
                deleted = cur.rowcount
                cur.execute(
                    """
                    UPDATE alunos a
                    SET embedding = latest.embedding
                    FROM (
                        SELECT DISTINCT ON (aluno_id) aluno_id, embedding
                        FROM embeddings
                        ORDER BY aluno_id, created_at DESC, id DESC
                    ) latest
                    WHERE a.id = latest.aluno_id
                    """
                )
                cur.execute(
                    """
                    UPDATE alunos
                    SET embedding = NULL
                    WHERE NOT EXISTS (
                        SELECT 1 FROM embeddings WHERE embeddings.aluno_id = alunos.id
                    )
                    """
                )
        logger.info("Retencao de embeddings concluida deleted=%d cutoff=%s", deleted, cutoff.isoformat())
        return deleted
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=86400)
    args = parser.parse_args()
    while True:
        purge_expired_embeddings()
        if not args.loop:
            return
        time.sleep(max(args.interval_seconds, 60))


if __name__ == "__main__":
    main()
