import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from app.core.config import (
    CAMERA_ID,
    SAAS_PRESENCE_WEBHOOK_URL,
    SAAS_WEBHOOK_SECRET,
    SAAS_WEBHOOK_TIMEOUT_SECONDS,
    WEBHOOK_MAX_ATTEMPTS,
    WEBHOOK_RETRY_SECONDS,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebhookResult:
    sent: bool
    event_id: str | None = None
    http_status: int | None = None
    error: str | None = None

    def __bool__(self) -> bool:
        return self.sent


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _signature(payload_bytes: bytes) -> str:
    if not SAAS_WEBHOOK_SECRET:
        return ""

    digest = hmac.new(
        SAAS_WEBHOOK_SECRET.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def _send_payload(payload: dict[str, Any]) -> WebhookResult:
    event_id = str(payload["event_id"])
    payload_bytes = _json_bytes(payload)
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": event_id,
    }
    signature = _signature(payload_bytes)
    if signature:
        headers["X-Recognition-Signature"] = signature
    if payload.get("trace_id"):
        headers["X-Trace-Id"] = payload["trace_id"]

    try:
        response = requests.post(
            SAAS_PRESENCE_WEBHOOK_URL,
            data=payload_bytes,
            headers=headers,
            timeout=SAAS_WEBHOOK_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return WebhookResult(sent=True, event_id=event_id, http_status=response.status_code)
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        error_summary = exc.__class__.__name__
        if status_code is not None:
            error_summary = f"{error_summary}: HTTP {status_code}"
        return WebhookResult(
            sent=False,
            event_id=event_id,
            http_status=status_code,
            error=error_summary,
        )


def _schedule_retry(payload: dict[str, Any], attempt: int, error: str | None) -> None:
    from redis import Redis
    from rq import Queue
    from app.core.config import REDIS_URL
    from app.core.database import get_connection

    event_id = str(payload["event_id"])
    next_attempt = datetime.now(timezone.utc) + timedelta(
        seconds=WEBHOOK_RETRY_SECONDS * (2 ** max(attempt - 1, 0))
    )
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                """
                INSERT INTO webhook_deliveries
                    (event_id, presence_id, payload, attempts, status, next_attempt_at, last_error)
                VALUES (%s, %s, %s::jsonb, %s, 'pending', %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    attempts = EXCLUDED.attempts,
                    status = EXCLUDED.status,
                    next_attempt_at = EXCLUDED.next_attempt_at,
                    last_error = EXCLUDED.last_error,
                    updated_at = now()
                    """,
                    (event_id, payload["presence_id"], json.dumps(payload), attempt, next_attempt, error),
                )
    finally:
        conn.close()
    redis = Redis.from_url(REDIS_URL)
    try:
        Queue("webhook-retry", connection=redis).enqueue_in(
            timedelta(seconds=WEBHOOK_RETRY_SECONDS * (2 ** max(attempt - 1, 0))),
            deliver_presence_webhook,
            payload,
            attempt + 1,
            job_id=f"webhook:{event_id}:{attempt + 1}",
        )
    finally:
        redis.close()


def deliver_presence_webhook(payload: dict[str, Any], attempt: int = 1) -> None:
    from app.core.database import get_connection

    result = _send_payload(payload)
    event_id = str(payload["event_id"])
    if result.sent:
        conn = get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                    "UPDATE webhook_deliveries SET status='sent', updated_at=now() WHERE event_id=%s",
                        (event_id,),
                    )
                    cur.execute(
                    "UPDATE recognition_events SET webhook_sent=true, webhook_error=NULL WHERE presence_id=%s",
                        (payload["presence_id"],),
                    )
        finally:
            conn.close()
        return

    if attempt < WEBHOOK_MAX_ATTEMPTS:
        _schedule_retry(payload, attempt, result.error)
        return

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                """
                UPDATE webhook_deliveries
                SET status='dead_letter', dead_lettered_at=now(), last_error=%s, updated_at=now()
                WHERE event_id=%s
                """,
                    (result.error, event_id),
                )
    finally:
        conn.close()
    from redis import Redis
    from rq import Queue
    from app.core.config import REDIS_URL

    redis = Redis.from_url(REDIS_URL)
    try:
        Queue("webhook-dead-letter", connection=redis).enqueue(
            dead_letter_webhook,
            payload,
            result.error,
            job_id=f"webhook-dead-letter:{event_id}",
        )
    finally:
        redis.close()
    logger.error("Webhook enviado para dead-letter event_id=%s error=%s", event_id, result.error)


def dead_letter_webhook(payload: dict[str, Any], error: str | None = None) -> None:
    logger.error(
        "Webhook mantido na fila dead-letter event_id=%s error=%s",
        payload.get("event_id"),
        error,
    )


def send_presence_event(
    *,
    presence_id: int,
    school_id: str,
    student_id: str,
    student_name: str,
    confidence: float,
    detected_at: datetime,
    tipo_evento: str = "entrada",
    trace_id: str | None = None,
    _attempt: int = 1,
) -> WebhookResult:
    event_id = f"presence:{school_id}:{presence_id}"

    if not SAAS_PRESENCE_WEBHOOK_URL:
        logger.info("Webhook do SaaS nao configurado; evento de presenca nao enviado event_id=%s", event_id)
        return WebhookResult(sent=False, event_id=event_id, error="webhook_url_not_configured")

    if detected_at.tzinfo is None:
        detected_at = detected_at.replace(tzinfo=timezone.utc)

    payload = {
        "event": "presence_detected",
        "event_id": event_id,
        "school_id": school_id,
        "camera_id": CAMERA_ID,
        "presence_id": presence_id,
        "student_id": student_id,
        "student_name": student_name,
        "confidence": confidence,
        "detected_at": detected_at.astimezone(timezone.utc).isoformat(),
        "tipo_evento": tipo_evento,
        "message_template": "{student_name} chegou na escola as {local_time}",
    }
    if trace_id:
        payload["trace_id"] = trace_id

    result = _send_payload(payload)
    if result.sent:
        logger.info(
            "Evento de presenca enviado ao SaaS event_id=%s http_status=%s",
            event_id,
            result.http_status,
        )
        return result

    if _attempt < WEBHOOK_MAX_ATTEMPTS:
        try:
            _schedule_retry(payload, _attempt, result.error)
        except Exception:
            logger.exception("Falha ao agendar retry do webhook event_id=%s", event_id)
    else:
        from redis import Redis
        from rq import Queue
        from app.core.config import REDIS_URL

        redis = Redis.from_url(REDIS_URL)
        try:
            Queue("webhook-dead-letter", connection=redis).enqueue(
                dead_letter_webhook,
                payload,
                result.error,
                job_id=f"webhook-dead-letter:{event_id}",
            )
        finally:
            redis.close()
        logger.error(
            "Falha ao enviar evento de presenca ao SaaS event_id=%s http_status=%s error=%s",
            event_id,
            result.http_status,
            result.error,
        )
    return result
