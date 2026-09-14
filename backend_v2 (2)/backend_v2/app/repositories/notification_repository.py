from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.models import NotificationOutbox


class NotificationOutboxRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, notification: NotificationOutbox) -> NotificationOutbox:
        self.db.add(notification)
        return notification

    def get(self, notification_id: int) -> NotificationOutbox | None:
        return (
            self.db.query(NotificationOutbox)
            .filter(NotificationOutbox.id == notification_id)
            .first()
        )

    def get_by_delivery_key(
        self,
        tipo: str,
        presenca_id: int,
        responsavel_id: int,
        canal: str,
    ) -> NotificationOutbox | None:
        return (
            self.db.query(NotificationOutbox)
            .filter(
                NotificationOutbox.tipo == tipo,
                NotificationOutbox.presenca_id == presenca_id,
                NotificationOutbox.responsavel_id == responsavel_id,
                NotificationOutbox.canal == canal,
            )
            .first()
        )

    def list_due_pending(
        self,
        now: datetime,
        limit: int = 50,
    ) -> list[NotificationOutbox]:
        return (
            self.db.query(NotificationOutbox)
            .filter(
                NotificationOutbox.status == "pending",
                or_(
                    NotificationOutbox.next_attempt_at.is_(None),
                    NotificationOutbox.next_attempt_at <= now,
                ),
            )
            .order_by(NotificationOutbox.created_at.asc(), NotificationOutbox.id.asc())
            .limit(limit)
            .all()
        )

    def list(
        self,
        *,
        empresa_id: int | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[NotificationOutbox]:
        query = self.db.query(NotificationOutbox)
        if empresa_id is not None:
            query = query.filter(NotificationOutbox.empresa_id == empresa_id)
        if status:
            query = query.filter(NotificationOutbox.status == status)
        return (
            query.order_by(NotificationOutbox.created_at.desc(), NotificationOutbox.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_status(self, status: str, empresa_id: int | None = None) -> int:
        query = self.db.query(NotificationOutbox).filter(NotificationOutbox.status == status)
        if empresa_id is not None:
            query = query.filter(NotificationOutbox.empresa_id == empresa_id)
        return query.count()
