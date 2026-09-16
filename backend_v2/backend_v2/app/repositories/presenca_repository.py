from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import Aluno, FaceEmbedding, Presenca, Responsavel


class PresencaRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, presenca: Presenca) -> Presenca:
        self.db.add(presenca)
        return presenca

    def get_by_recognition_event_id(self, event_id: str) -> Presenca | None:
        return (
            self.db.query(Presenca)
            .filter(Presenca.recognition_event_id == event_id)
            .first()
        )

    def get_equivalente_no_dia(
        self,
        *,
        aluno_id: int,
        empresa_id: int,
        tipo_evento: str,
        turno: str | None,
        detected_at,
    ) -> Presenca | None:
        dia = detected_at.date()
        query = (
            self.db.query(Presenca)
            .filter(
                Presenca.aluno_id == aluno_id,
                Presenca.empresa_id == empresa_id,
                Presenca.tipo_evento == tipo_evento,
                func.date(Presenca.timestamp) == dia,
            )
        )
        if turno:
            query = query.filter(Presenca.turno == turno)
        else:
            query = query.filter(Presenca.turno.is_(None))
        return query.order_by(Presenca.timestamp.asc()).first()

    def list_by_aluno(self, aluno_id: int, empresa_id: int) -> list[Presenca]:
        return (
            self.db.query(Presenca)
            .filter(Presenca.aluno_id == aluno_id, Presenca.empresa_id == empresa_id)
            .order_by(Presenca.timestamp.desc())
            .all()
        )

    def list_for_report(
        self,
        *,
        empresa_id: int | None = None,
        aluno_id: int | None = None,
        turma: str | None = None,
        camera_id: str | None = None,
        inicio=None,
        fim=None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Presenca], int]:
        query = self.db.query(Presenca).join(Presenca.aluno)
        if empresa_id is not None:
            query = query.filter(Presenca.empresa_id == empresa_id)
        if aluno_id is not None:
            query = query.filter(Presenca.aluno_id == aluno_id)
        if turma:
            query = query.filter(Aluno.turma == turma)
        if camera_id:
            query = query.filter(Presenca.camera_id == camera_id)
        if inicio:
            query = query.filter(Presenca.timestamp >= inicio)
        if fim:
            query = query.filter(Presenca.timestamp <= fim)
        total = query.count()
        return (
            query.order_by(Presenca.timestamp.desc())
            .offset(skip)
            .limit(limit)
            .all(),
            total,
        )


class ResponsavelRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, responsavel: Responsavel) -> Responsavel:
        self.db.add(responsavel)
        return responsavel


class FaceEmbeddingRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, face_embedding: FaceEmbedding) -> FaceEmbedding:
        self.db.add(face_embedding)
        return face_embedding

    def list_by_aluno(self, aluno_id: int) -> list[FaceEmbedding]:
        return self.db.query(FaceEmbedding).filter(FaceEmbedding.aluno_id == aluno_id).all()
