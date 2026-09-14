import psycopg2
from psycopg2.extensions import connection

from app.core.config import DATABASE_URL, DB_CONNECT_TIMEOUT_SECONDS


def get_connection() -> connection:
    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
    )


def check_database_connection() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()
