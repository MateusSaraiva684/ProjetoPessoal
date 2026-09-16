"""Remove dados biometricos expirados em execucao unica ou em loop."""

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.models import Aluno, AlunoFoto, FaceEmbedding
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


def purge_expired_biometrics() -> dict[str, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.BIOMETRIC_RETENTION_DAYS)
    db = SessionLocal()
    deleted_photos = 0
    deleted_embeddings = 0
    try:
        storage = StorageService()
        expired_photos = db.query(AlunoFoto).filter(AlunoFoto.criada_em < cutoff).all()
        for photo in expired_photos:
            storage.delete_photo(photo.url)
            if photo.aluno.foto == photo.url:
                photo.aluno.foto = None
                photo.aluno.biometria_status = "no_photo"
            db.delete(photo)
            deleted_photos += 1

        legacy_students = (
            db.query(Aluno)
            .filter(Aluno.foto.isnot(None), Aluno.criado_em < cutoff)
            .all()
        )
        for student in legacy_students:
            if not any(photo.url == student.foto for photo in student.fotos):
                storage.delete_photo(student.foto)
                student.foto = None
                student.biometria_status = "no_photo"
                deleted_photos += 1

        expired_embeddings = db.query(FaceEmbedding).filter(FaceEmbedding.criado_em < cutoff).all()
        for embedding in expired_embeddings:
            db.delete(embedding)
            deleted_embeddings += 1

        db.commit()
        logger.info(
            "Retencao biometrica concluida photos=%d embeddings=%d cutoff=%s",
            deleted_photos,
            deleted_embeddings,
            cutoff.isoformat(),
        )
        return {"photos": deleted_photos, "embeddings": deleted_embeddings}
    except Exception:
        db.rollback()
        logger.exception("Falha na retencao biometrica")
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=86400)
    args = parser.parse_args()
    while True:
        purge_expired_biometrics()
        if not args.loop:
            return
        time.sleep(max(args.interval_seconds, 60))


if __name__ == "__main__":
    main()
