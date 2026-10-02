"""Valida um backup PostgreSQL em um banco separado e descartavel.

Uso:
    RESTORE_DATABASE_URL=... python verify_restore.py --file backups/backup.sql
"""

import argparse
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def _connection_args(database_url: str) -> tuple[list[str], dict[str, str]]:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("RESTORE_DATABASE_URL deve ser uma URL PostgreSQL")
    command = [
        f"--host={parsed.hostname}",
        f"--port={parsed.port or 5432}",
        f"--username={parsed.username or 'postgres'}",
        parsed.path.lstrip("/") or "postgres",
    ]
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    return command, env


def main() -> None:
    parser = argparse.ArgumentParser(description="Testa backup em banco PostgreSQL isolado")
    parser.add_argument("--file", required=True)
    args = parser.parse_args()
    backup = Path(args.file).resolve()
    restore_url = os.getenv("RESTORE_DATABASE_URL", "")
    source_url = os.getenv("DATABASE_URL", "")
    if not restore_url:
        raise RuntimeError("Defina RESTORE_DATABASE_URL para o banco descartavel")
    if source_url and restore_url == source_url:
        raise RuntimeError("RESTORE_DATABASE_URL nao pode ser igual a DATABASE_URL")
    if not backup.is_file() or backup.stat().st_size == 0:
        raise RuntimeError("Arquivo de backup inexistente ou vazio")

    connection_args, env = _connection_args(restore_url)
    subprocess.run(
        ["psql", *connection_args, "--set=ON_ERROR_STOP=1"],
        stdin=backup.open("r", encoding="utf-8"),
        env=env,
        check=True,
        timeout=900,
    )
    result = subprocess.run(
        ["psql", *connection_args, "--tuples-only", "--no-align", "-c",
         "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    table_count = int(result.stdout.strip())
    if table_count == 0:
        raise RuntimeError("Restauracao concluida sem tabelas publicas")
    print(f"Restauração validada: {table_count} tabelas públicas")


if __name__ == "__main__":
    main()
