import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from app.core.config import (
    CAMERA_ID,
    SAAS_PRESENCE_WEBHOOK_URL,
    SAAS_WEBHOOK_SECRET,
    SAAS_WEBHOOK_TIMEOUT_SECONDS,
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

    payload_bytes = _json_bytes(payload)
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": event_id,
    }

    signature = _signature(payload_bytes)
    if signature:
        headers["X-Recognition-Signature"] = signature
    if trace_id:
        headers["X-Trace-Id"] = trace_id

    try:
        response = requests.post(
            SAAS_PRESENCE_WEBHOOK_URL,
            data=payload_bytes,
            headers=headers,
            timeout=SAAS_WEBHOOK_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        status_code = getattr(response, "status_code", None)
        logger.info(
            "Evento de presenca enviado ao SaaS event_id=%s http_status=%s",
            event_id,
            status_code,
        )
        return WebhookResult(sent=True, event_id=event_id, http_status=status_code)
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        error_summary = exc.__class__.__name__
        if status_code is not None:
            error_summary = f"{error_summary}: HTTP {status_code}"
        logger.error(
            "Falha ao enviar evento de presenca ao SaaS event_id=%s http_status=%s error=%s",
            event_id,
            status_code,
            error_summary,
            exc_info=True,
        )
        return WebhookResult(
            sent=False,
            event_id=event_id,
            http_status=status_code,
            error=error_summary,
        )
