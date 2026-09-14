import logging
from typing import Any

from psycopg2.extras import Json

from app.core.database import get_connection

logger = logging.getLogger(__name__)


def _clean_error(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("\r", " ").replace("\n", " ")[:500]


def record_recognition_event(
    *,
    status: str,
    school_id: str,
    camera_id: str,
    external_id: str | None = None,
    aluno_id: int | None = None,
    face_sample_id: int | None = None,
    confidence: float | None = None,
    distance: float | None = None,
    presence_id: int | None = None,
    candidates: list[dict[str, Any]] | None = None,
    webhook_sent: bool = False,
    webhook_error: str | None = None,
    metadata: dict[str, Any] | None = None,
    cur: Any | None = None,
) -> None:
    """
    Registra auditoria operacional sem armazenar imagem ou embedding bruto.
    """
    params = (
        status,
        school_id,
        external_id,
        camera_id,
        aluno_id,
        face_sample_id,
        confidence,
        distance,
        presence_id,
        Json(candidates) if candidates is not None else None,
        webhook_sent,
        _clean_error(webhook_error),
        Json(metadata) if metadata is not None else None,
    )
    sql = """
        INSERT INTO recognition_events (
            status,
            school_id,
            external_id,
            camera_id,
            aluno_id,
            face_sample_id,
            confidence,
            distance,
            presence_id,
            candidates,
            webhook_sent,
            webhook_error,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    try:
        if cur is not None:
            cur.execute(sql, params)
            return

        conn = get_connection()
        try:
            with conn:
                with conn.cursor() as local_cur:
                    local_cur.execute(sql, params)
        finally:
            conn.close()
    except Exception:
        logger.error("Falha ao registrar recognition_event status=%s", status, exc_info=True)


def fetch_recent_ambiguous_events(limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 200))
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    school_id,
                    external_id,
                    camera_id,
                    aluno_id,
                    face_sample_id,
                    confidence,
                    distance,
                    candidates,
                    created_at
                FROM recognition_events
                WHERE status = 'ambiguous_match'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (safe_limit,),
            )
            return [
                {
                    "id": row[0],
                    "school_id": row[1],
                    "external_id": row[2],
                    "camera_id": row[3],
                    "aluno_id": row[4],
                    "face_sample_id": row[5],
                    "confidence": row[6],
                    "distance": row[7],
                    "candidates": row[8] or [],
                    "created_at": row[9].isoformat() if row[9] else None,
                }
                for row in cur.fetchall()
            ]
    finally:
        conn.close()
