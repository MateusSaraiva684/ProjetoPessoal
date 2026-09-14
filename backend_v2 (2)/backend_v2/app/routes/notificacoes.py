from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.database.session import get_db
from app.models.models import Usuario
from app.repositories.notification_repository import NotificationOutboxRepository
from app.routes.auth import get_current_user
from app.schemas.schemas import NotificationOutboxResponse
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("", response_model=list[NotificationOutboxResponse])
def listar_notificacoes(
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    page: int = Query(1, ge=1),
    user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = NotificationOutboxRepository(db)
    empresa_id = None if user.is_superuser else user.id
    return repo.list(
        empresa_id=empresa_id,
        status=status,
        skip=(page - 1) * limit,
        limit=limit,
    )


@router.post("/{notification_id}/retry", response_model=NotificationOutboxResponse)
def reenviar_notificacao(
    notification_id: int,
    user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = NotificationOutboxRepository(db)
    notification = repo.get(notification_id)
    if not notification:
        raise NotFoundError("Notificacao nao encontrada")
    if not user.is_superuser and notification.empresa_id != user.id:
        raise NotFoundError("Notificacao nao encontrada")
    if notification.status not in {"failed", "pending"}:
        raise BadRequestError("Apenas notificacoes pendentes ou com falha podem ser reenviadas")

    notification.status = "pending"
    notification.next_attempt_at = None
    notification.last_error = None
    db.commit()
    db.refresh(notification)
    return NotificationService(db).enviar_notificacao_pendente(notification)
