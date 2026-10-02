import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.models import AuditLog

logger = logging.getLogger(__name__)


def registrar_auditoria(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    trace_id: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        audit_metadata=metadata or {},
        ip_address=ip_address,
        trace_id=trace_id,
    )
    db.add(entry)
    return entry
