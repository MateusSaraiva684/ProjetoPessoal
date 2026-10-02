import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Aluno, NotificationOutbox, Presenca, Responsavel
from app.repositories.notification_repository import NotificationOutboxRepository

logger = logging.getLogger(__name__)

PRESENCE_ARRIVAL_TYPE = "presence_arrival"
VALID_CHANNELS = {"whatsapp", "sms", "email", "log"}


@dataclass(frozen=True)
class NotificationSendResult:
    provider_message_id: str | None = None


class NotificationProviderError(Exception):
    def __init__(self, detail: str, retryable: bool = True):
        self.detail = detail
        self.retryable = retryable
        super().__init__(detail)


class NotificationProvider(Protocol):
    channel: str

    def send(self, notification: NotificationOutbox) -> NotificationSendResult:
        ...


class LogNotificationProvider:
    channel = "log"

    def send(self, notification: NotificationOutbox) -> NotificationSendResult:
        logger.info(
            "Notification outbox delivered by log provider: id=%d tipo=%s responsavel_id=%d",
            notification.id,
            notification.tipo,
            notification.responsavel_id,
        )
        return NotificationSendResult(provider_message_id=f"log-{notification.id}")


class WhatsAppCloudProvider:
    channel = "whatsapp"

    def __init__(
        self,
        api_url: str | None = None,
        api_token: str | None = None,
        from_phone_id: str | None = None,
    ):
        self.api_url = self._normalize_api_url(
            api_url if api_url is not None else settings.WHATSAPP_API_URL
        )
        self.api_token = (
            api_token if api_token is not None else settings.WHATSAPP_API_TOKEN
        ).strip()
        self.from_phone_id = (
            from_phone_id
            if from_phone_id is not None
            else settings.WHATSAPP_FROM_PHONE_ID
        ).strip()

        if not self.api_url or not self.api_token or not self.from_phone_id:
            raise ValueError("WhatsApp provider nao configurado")

    def send(self, notification: NotificationOutbox) -> NotificationSendResult:
        payload = {
            "messaging_product": "whatsapp",
            "to": notification.telefone_destino,
            "type": "text",
            "text": {"body": notification.mensagem},
        }
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{self.api_url}/{self.from_phone_id}/messages"
        try:
            with httpx.Client(timeout=10, trust_env=False) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise NotificationProviderError("whatsapp_timeout", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            retryable = status_code == 429 or status_code >= 500
            raise NotificationProviderError(
                f"whatsapp_http_status_{status_code}",
                retryable=retryable,
            ) from exc
        except httpx.HTTPError as exc:
            raise NotificationProviderError("whatsapp_http_error", retryable=True) from exc

        provider_message_id = self._extract_provider_message_id(response)
        return NotificationSendResult(provider_message_id=provider_message_id)

    @staticmethod
    def _extract_provider_message_id(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None

        messages = payload.get("messages")
        if isinstance(messages, list) and messages:
            message_id = messages[0].get("id")
            return str(message_id) if message_id else None
        return None

    @staticmethod
    def _normalize_api_url(api_url: str) -> str:
        api_url = (api_url or "").strip().rstrip("/")
        if not api_url:
            return ""

        parsed = urlsplit(api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("WHATSAPP_API_URL deve ser uma URL HTTP(S) valida")
        if parsed.username or parsed.password:
            raise ValueError("WHATSAPP_API_URL nao deve conter credenciais")
        if settings.is_production and parsed.scheme != "https":
            raise ValueError("WHATSAPP_API_URL deve usar HTTPS em production")
        return api_url


class NotificationService:
    def __init__(
        self,
        db: Session | None = None,
        provider: NotificationProvider | None = None,
    ):
        self.db = db
        self.notifications = NotificationOutboxRepository(db) if db else None
        self.provider = provider

    def criar_notificacoes_presenca(
        self,
        presenca: Presenca,
        aluno: Aluno,
        mensagem: str,
        canal: str | None = None,
    ) -> list[NotificationOutbox]:
        self._require_db()
        canal = self._resolve_channel(canal)
        responsaveis = list(aluno.responsaveis)
        if not responsaveis:
            logger.info(
                "Aluno sem responsaveis cadastrados para notification outbox: aluno_id=%d presenca_id=%d",
                aluno.id,
                presenca.id,
            )
            return []

        criadas: list[NotificationOutbox] = []
        tipo = "presence_departure" if presenca.tipo_evento == "saida" else PRESENCE_ARRIVAL_TYPE
        for responsavel in responsaveis:
            existente = self.notifications.get_by_delivery_key(
                tipo,
                presenca.id,
                responsavel.id,
                canal,
            )
            if existente:
                criadas.append(existente)
                continue

            telefone = self.normalizar_telefone(responsavel.telefone)
            status = "pending" if telefone else "failed"
            notification = NotificationOutbox(
                empresa_id=aluno.empresa_id,
                tipo=tipo,
                status=status,
                canal=canal,
                presenca_id=presenca.id,
                aluno_id=aluno.id,
                responsavel_id=responsavel.id,
                telefone_destino=telefone or "",
                mensagem=mensagem,
                attempts=0,
                last_error=None if telefone else "telefone_destino invalido",
            )
            self.notifications.add(notification)
            criadas.append(notification)

        return criadas

    def processar_pendentes(
        self,
        limit: int = 50,
        now: datetime | None = None,
    ) -> dict[str, int]:
        self._require_db()
        now = now or datetime.now(timezone.utc)
        resultado = {"processed": 0, "sent": 0, "failed": 0, "retried": 0}
        notificacoes = self.notifications.list_due_pending(now=now, limit=limit)

        for notification in notificacoes:
            resultado["processed"] += 1
            self._marcar_processing(notification)
            try:
                self.enviar_notificacao_pendente(notification, now=now)
            except Exception:
                logger.exception(
                    "Erro inesperado ao processar notification outbox id=%d",
                    notification.id,
                )
                self._marcar_falha(
                    notification,
                    "unexpected_error",
                    retryable=True,
                    now=now,
                )

            if notification.status == "sent":
                resultado["sent"] += 1
            elif notification.status == "failed":
                resultado["failed"] += 1
            elif notification.status == "pending":
                resultado["retried"] += 1

        return resultado

    def enviar_notificacao_pendente(
        self,
        notification: NotificationOutbox,
        now: datetime | None = None,
    ) -> NotificationOutbox:
        self._require_db()
        now = now or datetime.now(timezone.utc)

        if notification.status != "processing":
            self._marcar_processing(notification)

        if not self.normalizar_telefone(notification.telefone_destino):
            self._marcar_falha(
                notification,
                "telefone_destino invalido",
                retryable=False,
                now=now,
            )
            return notification

        try:
            provider = self._get_provider(notification.canal)
            result = provider.send(notification)
        except NotificationProviderError as exc:
            self._marcar_falha(
                notification,
                exc.detail,
                retryable=exc.retryable,
                now=now,
            )
            return notification
        except Exception:
            logger.exception(
                "Erro inesperado no provider de notificacao: notification_id=%d canal=%s",
                notification.id,
                notification.canal,
            )
            self._marcar_falha(
                notification,
                "provider_unexpected_error",
                retryable=True,
                now=now,
            )
            return notification

        notification.status = "sent"
        notification.sent_at = now
        notification.provider_message_id = result.provider_message_id
        notification.last_error = None
        notification.next_attempt_at = None
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def enviar_presenca(self, responsavel: Responsavel, mensagem: str) -> None:
        logger.info(
            "Legacy notification log: responsavel_id=%d telefone=%s",
            responsavel.id,
            self._mask_phone(responsavel.telefone),
        )

    def _marcar_processing(self, notification: NotificationOutbox) -> None:
        notification.status = "processing"
        self.db.commit()
        self.db.refresh(notification)

    def _marcar_falha(
        self,
        notification: NotificationOutbox,
        detail: str,
        retryable: bool,
        now: datetime,
    ) -> None:
        notification.attempts += 1
        notification.last_error = self._safe_error(detail)

        max_attempts = settings.NOTIFICATION_MAX_ATTEMPTS
        if not retryable or notification.attempts >= max_attempts:
            notification.status = "failed"
            notification.next_attempt_at = None
        else:
            notification.status = "pending"
            notification.next_attempt_at = now + timedelta(
                seconds=settings.NOTIFICATION_RETRY_SECONDS
            )

        self.db.commit()
        self.db.refresh(notification)

    def _get_provider(self, canal: str) -> NotificationProvider:
        if self.provider:
            return self.provider

        if canal == "log":
            return LogNotificationProvider()
        if canal == "whatsapp":
            return WhatsAppCloudProvider()

        raise NotificationProviderError(f"canal_nao_suportado_{canal}", retryable=False)

    def _resolve_channel(self, canal: str | None = None) -> str:
        canal = (canal or settings.NOTIFICATION_PROVIDER or "log").strip().lower()
        if canal not in VALID_CHANNELS:
            logger.warning("Canal de notificacao invalido; usando log: canal=%s", canal)
            return "log"
        return canal

    def _require_db(self) -> None:
        if self.db is None or self.notifications is None:
            raise RuntimeError("NotificationService requer uma sessao de banco")

    @staticmethod
    def normalizar_telefone(telefone: str | None) -> str | None:
        digits = re.sub(r"\D", "", telefone or "")
        if len(digits) < 10 or len(digits) > 15:
            return None
        if len(digits) in (10, 11):
            digits = f"55{digits}"
        return digits

    @staticmethod
    def _safe_error(detail: str) -> str:
        detail = str(detail or "provider_error").strip()
        detail = re.sub(r"[\r\n\t]+", " ", detail)
        return detail[:255]

    @staticmethod
    def _mask_phone(telefone: str | None) -> str:
        digits = re.sub(r"\D", "", telefone or "")
        if len(digits) <= 4:
            return "****"
        return f"***{digits[-4:]}"
