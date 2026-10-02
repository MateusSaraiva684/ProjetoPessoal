from sqlalchemy.orm import Session

from app.models.models import Aluno, Presenca, Usuario
from app.services.face_recognition_service import FaceImagePayload, FaceRecognitionResult, FaceRecognitionService
from app.services.presenca_service import PresencaService


class ReconhecimentoFacialWorkflow:
    def __init__(
        self,
        db: Session,
        face_service: FaceRecognitionService | None = None,
        presenca_service: PresencaService | None = None,
    ):
        self.face_service = face_service or FaceRecognitionService()
        self.presenca_service = presenca_service or PresencaService(db)

    async def processar(
        self,
        payload: FaceImagePayload,
        user: Usuario,
    ) -> tuple[FaceRecognitionResult, Presenca]:
        resultado = await self.face_service.reconhecer(payload)
        presenca = self.presenca_service.registrar_por_reconhecimento(resultado, user)
        return resultado, presenca

    async def identificar(
        self,
        payload: FaceImagePayload,
        user: Usuario,
    ) -> tuple[FaceRecognitionResult, Aluno]:
        resultado = await self.face_service.reconhecer(payload)
        aluno = self.presenca_service.identificar_aluno_por_reconhecimento(resultado, user)
        return resultado, aluno
