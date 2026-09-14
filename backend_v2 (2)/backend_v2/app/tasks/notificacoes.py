import logging

from app.database.session import SessionLocal
from app.services.notification_service import NotificationService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _processar_notificacoes_pendentes_impl(limit: int = 50) -> dict[str, int]:
    db = SessionLocal()
    try:
        resultado = NotificationService(db).processar_pendentes(limit=limit)
        logger.info("Notification outbox processada: %s", resultado)
        return resultado
    finally:
        db.close()


if celery_app:
    processar_notificacoes_pendentes = celery_app.task(
        name="processar_notificacoes_pendentes"
    )(_processar_notificacoes_pendentes_impl)
else:
    processar_notificacoes_pendentes = _processar_notificacoes_pendentes_impl
