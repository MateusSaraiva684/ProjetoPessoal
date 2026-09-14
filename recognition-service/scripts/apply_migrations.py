import logging
import os
from pathlib import Path

import psycopg2

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL nao configurada")
    return database_url


def _get_school_id() -> str:
    return os.getenv("SCHOOL_ID", "escola_1").strip() or "escola_1"


def _ensure_migrations_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def _applied_versions(cur) -> set[str]:
    cur.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cur.fetchall()}


def apply_migrations() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        logger.info("Nenhuma migration encontrada em %s", MIGRATIONS_DIR)
        return

    conn = psycopg2.connect(_get_database_url())
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure_migrations_table(cur)
                cur.execute("SELECT set_config('app.school_id', %s, false)", (_get_school_id(),))
                applied = _applied_versions(cur)

                for migration_file in migration_files:
                    version = migration_file.name
                    if version in applied:
                        logger.info("Migration ja aplicada: %s", version)
                        continue

                    logger.info("Aplicando migration: %s", version)
                    cur.execute(migration_file.read_text(encoding="utf-8"))
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (version,),
                    )
                    logger.info("Migration aplicada: %s", version)
    finally:
        conn.close()


if __name__ == "__main__":
    apply_migrations()
