import logging
from typing import Any

from fastapi import APIRouter, Depends
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

from app.core.config import CAMERA_ID, REDIS_URL, SAAS_PRESENCE_WEBHOOK_URL, SCHOOL_ID
from app.core.database import get_connection
from app.core.security import require_api_key
from app.services.face_service import is_model_loaded

logger = logging.getLogger(__name__)

router = APIRouter(tags=["diagnostics"], dependencies=[Depends(require_api_key)])


def _row_to_dict(row, keys: list[str]) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        key: (value.isoformat() if hasattr(value, "isoformat") else value)
        for key, value in zip(keys, row)
    }


def build_diagnostics_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "database": "unknown",
        "redis": "unknown",
        "queue": "unknown",
        "insightface_model_loaded": is_model_loaded(),
        "school_id": SCHOOL_ID,
        "camera_id": CAMERA_ID,
        "webhook_configured": bool(SAAS_PRESENCE_WEBHOOK_URL),
        "last_presence": None,
        "last_recognition_event": None,
        "last_webhook_error": None,
    }

    try:
        redis_conn = Redis.from_url(REDIS_URL, socket_connect_timeout=3, socket_timeout=3)
        redis_conn.ping()
        payload["redis"] = "ok"
        queue = Queue("recognition", connection=redis_conn)
        payload["queue"] = {"status": "ok", "name": queue.name, "queued_jobs": queue.count}
    except RedisError as exc:
        logger.error("Diagnostics Redis/RQ falhou: %s", exc)
        payload["redis"] = "unavailable"
        payload["queue"] = "unavailable"
    except Exception as exc:
        logger.error("Diagnostics RQ falhou: %s", exc)
        payload["queue"] = "unavailable"

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
                payload["database"] = "ok"

                cur.execute(
                    """
                    SELECT id, school_id, external_id, camera_id, nome, created_at
                    FROM presencas
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                )
                payload["last_presence"] = _row_to_dict(
                    cur.fetchone(),
                    ["id", "school_id", "external_id", "camera_id", "nome", "created_at"],
                )

                cur.execute(
                    """
                    SELECT id, status, school_id, external_id, camera_id, webhook_sent, created_at
                    FROM recognition_events
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                )
                payload["last_recognition_event"] = _row_to_dict(
                    cur.fetchone(),
                    ["id", "status", "school_id", "external_id", "camera_id", "webhook_sent", "created_at"],
                )

                cur.execute(
                    """
                    SELECT id, status, school_id, external_id, camera_id, webhook_error, created_at
                    FROM recognition_events
                    WHERE webhook_error IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                )
                payload["last_webhook_error"] = _row_to_dict(
                    cur.fetchone(),
                    ["id", "status", "school_id", "external_id", "camera_id", "webhook_error", "created_at"],
                )
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Diagnostics database falhou: %s", exc)
        payload["database"] = "unavailable"

    return payload


@router.get("/diagnostics")
async def diagnostics() -> dict[str, Any]:
    return build_diagnostics_payload()
