import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.models.models import Presenca, Usuario
from app.repositories.presenca_repository import PresencaRepository
from app.schemas.schemas import (
    PresencaCreate,
    PresencaManualCreate,
    PresencaReconhecimentoCreate,
    RecognitionPresenceWebhookCreate,
)
from app.services.aluno_service import AlunoService
from app.services.face_recognition_service import FaceRecognitionResult
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
FORTALEZA_TZ = ZoneInfo("America/Fortaleza")


class PresencaService:
    def __init__(
        self,
        db: Session,
        notification_service: NotificationService | None = None,
    ):
        self.db = db
        self.presencas = PresencaRepository(db)
        self.alunos = AlunoService(db)
        self.notification_service = notification_service or NotificationService(db)

    def registrar_manual(self, body: PresencaManualCreate, user: Usuario) -> Presenca:
        aluno = self.alunos.buscar_para_usuario_ou_admin(user, body.aluno_id)
        return self.registrar_presenca(
            aluno_id=aluno.id,
            empresa_id=aluno.empresa_id,
            tipo_evento=body.tipo_evento,
            origem="manual",
            detected_at=body.timestamp or datetime.now(timezone.utc),
            turno=body.turno,
            observacao=body.observacao,
            criado_por_id=user.id,
            status=body.status,
        )

    def registrar_entrada_saida(self, body: PresencaCreate, user: Usuario, tipo_evento: str) -> Presenca:
        aluno = self.alunos.buscar_para_usuario_ou_admin(user, body.aluno_id)
        return self.registrar_presenca(
            aluno_id=aluno.id,
            empresa_id=aluno.empresa_id,
            tipo_evento=tipo_evento,
            origem="manual",
            detected_at=body.timestamp or datetime.now(timezone.utc),
            turno=body.turno,
            observacao=body.observacao,
            criado_por_id=user.id,
        )

    def registrar_presenca(
        self,
        *,
        aluno_id: int,
        empresa_id: int,
        tipo_evento: str,
        origem: str,
        detected_at: datetime,
        camera_id: str | None = None,
        confidence: float | None = None,
        recognition_event_id: str | None = None,
        turno: str | None = None,
        observacao: str | None = None,
        criado_por_id: int | None = None,
        status: str = "confirmado",
    ) -> Presenca:
        tipo_evento = tipo_evento or "entrada"
        if tipo_evento not in {"entrada", "saida", "manual", "ajuste_admin"}:
            raise BadRequestError("tipo_evento invalido")
        aluno = self.alunos.alunos.get(aluno_id)
        if not aluno or aluno.empresa_id != empresa_id:
            raise BadRequestError("aluno_id invalido para empresa_id informado")
        if tipo_evento in {"entrada", "saida"}:
            existente = self.presencas.get_equivalente_no_dia(
                aluno_id=aluno_id,
                empresa_id=empresa_id,
                tipo_evento=tipo_evento,
                turno=turno,
                detected_at=detected_at,
            )
            if existente:
                logger.info(
                    "Presenca duplicada evitada: aluno_id=%d tipo_evento=%s turno=%s presenca_id=%d",
                    aluno_id,
                    tipo_evento,
                    turno,
                    existente.id,
                )
                existente.status = "confirmado"
                return existente

        presenca = Presenca(
            aluno_id=aluno_id,
            empresa_id=empresa_id,
            timestamp=detected_at,
            tipo_evento=tipo_evento,
            origem=origem,
            turno=turno,
            camera_id=camera_id,
            confianca=confidence,
            status=status,
            recognition_event_id=recognition_event_id,
            observacao=observacao,
            criado_por_id=criado_por_id,
        )
        self.presencas.add(presenca)
        self.db.flush()
        if status == "confirmado":
            self._criar_notificacoes_responsaveis(presenca, aluno, detected_at)
        self.db.commit()
        self.db.refresh(presenca)
        logger.info(
            "Presenca registrada: id=%d aluno_id=%d tipo_evento=%s origem=%s",
            presenca.id,
            aluno_id,
            tipo_evento,
            origem,
        )
        return presenca

    def listar_por_aluno(self, aluno_id: int, user: Usuario) -> list[Presenca]:
        aluno = self.alunos.buscar_para_usuario_ou_admin(user, aluno_id)
        return self.presencas.list_by_aluno(aluno_id, aluno.empresa_id)

    def listar_relatorio(self, user: Usuario, **filtros):
        empresa_id = None if user.is_superuser else user.id
        return self.presencas.list_for_report(empresa_id=empresa_id, **filtros)

    def registrar_reconhecimento_recebido(
        self,
        body: PresencaReconhecimentoCreate,
    ) -> Presenca:
        aluno = self.alunos.buscar_por_external_id(body.external_id, body.empresa_id)
        return self.registrar_presenca(
            aluno_id=aluno.id,
            empresa_id=aluno.empresa_id,
            detected_at=body.timestamp or datetime.now(timezone.utc),
            tipo_evento=body.tipo_evento,
            origem="facial",
            confidence=body.confianca,
            status=body.status,
            turno=body.turno,
            camera_id=body.camera_id,
        )

    def registrar_evento_reconhecimento(
        self,
        body: RecognitionPresenceWebhookCreate,
    ) -> Presenca:
        presenca_existente = self.presencas.get_by_recognition_event_id(body.event_id)
        if presenca_existente:
            logger.info(
                "Evento de reconhecimento ja processado: event_id=%s presenca_id=%d",
                body.event_id,
                presenca_existente.id,
            )
            return presenca_existente

        empresa_id = self._resolver_empresa_id(body.school_id)
        aluno = self.alunos.buscar_por_external_id(body.student_id, empresa_id)
        try:
            presenca = self.registrar_presenca(
                aluno_id=aluno.id,
                empresa_id=aluno.empresa_id,
                tipo_evento=body.tipo_evento,
                origem="facial",
                detected_at=body.detected_at,
                camera_id=body.camera_id,
                confidence=body.confidence,
                recognition_event_id=body.event_id,
                turno=body.turno,
            )
        except IntegrityError:
            self.db.rollback()
            presenca_existente = self.presencas.get_by_recognition_event_id(body.event_id)
            if presenca_existente:
                logger.info(
                    "Evento de reconhecimento ja processado por outra transacao: event_id=%s presenca_id=%d",
                    body.event_id,
                    presenca_existente.id,
                )
                return presenca_existente
            raise

        logger.info(
            "Presenca oficial criada por webhook de reconhecimento: id=%d aluno_id=%d empresa_id=%d event_id=%s",
            presenca.id,
            aluno.id,
            aluno.empresa_id,
            body.event_id,
        )
        return presenca

    def registrar_por_reconhecimento(
        self,
        resultado: FaceRecognitionResult,
        user: Usuario,
    ) -> Presenca:
        aluno = self.identificar_aluno_por_reconhecimento(resultado, user)
        presenca = self.registrar_presenca(
            aluno_id=aluno.id,
            empresa_id=aluno.empresa_id,
            tipo_evento="entrada",
            origem="facial",
            detected_at=datetime.now(timezone.utc),
            confidence=resultado.confianca,
        )

        logger.info(
            "Presenca facial registrada: id=%d aluno_id=%d confianca=%.4f",
            presenca.id,
            aluno.id,
            resultado.confianca,
        )
        return presenca

    def identificar_aluno_por_reconhecimento(
        self,
        resultado: FaceRecognitionResult,
        user: Usuario,
    ):
        if not resultado.external_id:
            raise BadRequestError("Resposta do reconhecimento sem identificador de aluno")

        empresa_id = user.id
        if resultado.school_id:
            empresa_id = self._resolver_empresa_id(resultado.school_id)
            if not user.is_superuser and empresa_id != user.id:
                raise BadRequestError(
                    "school_id do reconhecimento nao corresponde ao usuario autenticado"
                )

        return self.alunos.buscar_por_external_id(resultado.external_id, empresa_id)

    def _resolver_empresa_id(self, school_id: str) -> int:
        school_id = school_id.strip()
        if school_id.isdigit():
            return int(school_id)

        prefixo = "escola_"
        if school_id.lower().startswith(prefixo):
            candidato = school_id[len(prefixo):]
            if candidato.isdigit():
                return int(candidato)

        raise BadRequestError(
            "school_id invalido; use o empresa_id numerico ou escola_<empresa_id>"
        )

    def _criar_notificacoes_responsaveis(
        self,
        presenca: Presenca,
        aluno,
        detected_at: datetime,
    ) -> None:
        responsaveis = list(aluno.responsaveis)
        if not responsaveis:
            logger.info(
                "Aluno sem responsaveis cadastrados para notificacao de presenca: aluno_id=%d",
                aluno.id,
            )
            return

        local_time = detected_at.astimezone(FORTALEZA_TZ).strftime("%H:%M")
        if presenca.tipo_evento == "saida":
            mensagem = f"{aluno.nome} saiu da escola \u00e0s {local_time}."
        else:
            mensagem = f"{aluno.nome} chegou \u00e0 escola \u00e0s {local_time}."
        self.notification_service.criar_notificacoes_presenca(
            presenca=presenca,
            aluno=aluno,
            mensagem=mensagem,
        )
