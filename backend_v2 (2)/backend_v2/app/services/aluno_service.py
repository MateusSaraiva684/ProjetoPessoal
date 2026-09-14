import logging
import inspect
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.trace import gerar_trace_id
from app.models.models import Aluno, AlunoFoto, Responsavel, Usuario
from app.repositories.aluno_repository import AlunoRepository
from app.schemas.schemas import ResponsavelCreate
from app.services.integration_service import IntegrationService
from app.services.storage_service import StorageService, StoredPhoto

logger = logging.getLogger(__name__)


class AlunoService:
    def __init__(
        self,
        db: Session,
        integration_service: IntegrationService | None = None,
        storage_service: StorageService | None = None,
    ):
        self.db = db
        self.alunos = AlunoRepository(db)
        self.integration_service = integration_service or IntegrationService()
        self.storage_service = storage_service or StorageService()

    def listar_turmas(self, user: Usuario) -> list[str]:
        return self.alunos.list_turmas_by_user(user.id)

    def listar(
        self,
        user: Usuario,
        turma: str | None = None,
        busca: str | None = None,
        biometria_status: str | None = None,
        sem_foto: bool | None = None,
        com_erro_biometria: bool | None = None,
        criado_de: date | None = None,
        criado_ate: date | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> dict:
        """Lista alunos com paginação.
        
        Args:
            user: Usuário autenticado
            turma: Filtrar por turma (opcional)
            busca: Buscar por nome ou número (opcional)
            page: Número da página (começa em 1)
            limit: Itens por página
            
        Returns:
            Dict com dados paginados
        """
        # Validar page e limit
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 50
            
        skip = (page - 1) * limit
        alunos, total = self.alunos.list_by_user(
            user.id, 
            turma=turma, 
            busca=busca, 
            biometria_status=biometria_status,
            sem_foto=sem_foto,
            com_erro_biometria=com_erro_biometria,
            criado_de=criado_de,
            criado_ate=criado_ate,
            skip=skip, 
            limit=limit
        )
        
        total_pages = (total + limit - 1) // limit  # Ceiling division
        
        # Converter objetos Aluno para dicionários serializáveis
        dados_alunos = []
        for aluno in alunos:
            dados_alunos.append({
                "id": aluno.id,
                "nome": aluno.nome,
                "numero_inscricao": aluno.numero_inscricao,
                "telefone": aluno.telefone,
                "turma": aluno.turma,
                "foto": aluno.foto,
                "external_id": aluno.external_id,
                "empresa_id": aluno.empresa_id,
                "biometria_status": aluno.biometria_status,
                "biometria_error": aluno.biometria_error,
                "biometria_atualizada_em": aluno.biometria_atualizada_em,
                "face_samples_count": aluno.face_samples_count,
                "criado_em": aluno.criado_em,
                "user_id": aluno.user_id,
                "responsaveis": [
                    {"id": r.id, "nome": r.nome, "telefone": r.telefone}
                    for r in aluno.responsaveis
                ] if hasattr(aluno, 'responsaveis') else []
            })
        
        return {
            "data": dados_alunos,
            "paginacao": {
                "total": total,
                "pagina": page,
                "limite": limit,
                "paginas_totais": total_pages,
                "proxima_pagina": page + 1 if skip + limit < total else None,
            }
        }

    def criar(
        self,
        user: Usuario,
        nome: str,
        numero_inscricao: str,
        telefone: str,
        turma: str = "",
        foto: UploadFile | None = None,
    ) -> Aluno:
        numero_inscricao = self._normalizar_numero_inscricao(numero_inscricao)
        stored_photo = None
        
        try:
            stored_photo = self.storage_service.save_student_photo(foto) if foto else None
        except Exception as e:
            logger.error("Erro ao fazer upload de foto: %s", str(e))
            raise
        
        aluno = Aluno(
            nome=nome,
            numero_inscricao=numero_inscricao,
            telefone=telefone,
            turma=turma.strip() or None,
            foto=stored_photo.url if stored_photo else None,
            empresa_id=user.id,
            external_id=f"pending-{uuid4()}",
            biometria_status="pending" if stored_photo else "no_photo",
            user_id=user.id,
        )
        try:
            self.alunos.add(aluno)
            self.db.flush()  # Força constraint check do UNIQUE
            aluno.external_id = str(aluno.id)
            self.db.flush()
            self.db.commit()
            self.db.refresh(aluno)
            if stored_photo:
                self._registrar_foto_principal(aluno, stored_photo)
            trace_id = gerar_trace_id("cadastro-aluno", aluno.id)
            logger.info("Aluno criado: id=%d por usuario id=%d trace_id=%s", aluno.id, user.id, trace_id)
            self._sync_aluno_safely(aluno, action="criacao", photo_file=stored_photo, trace_id=trace_id)
            return aluno
        except IntegrityError as e:
            self.db.rollback()
            self.storage_service.delete_photo(stored_photo.url if stored_photo else None)
            # Detecta violação de constraint UNIQUE (SQLite, PostgreSQL)
            if "alunos.user_id, alunos.numero_inscricao" in str(e) or "uq_alunos_user_numero_inscricao" in str(e):
                logger.warning("Numero inscricao duplicado para usuario id=%d: %s", user.id, numero_inscricao)
                raise BadRequestError("Numero de inscricao ja cadastrado para esta escola")
            if "uq_alunos_empresa_external_id" in str(e):
                logger.warning("External ID duplicado para empresa id=%d", user.id)
                raise BadRequestError("External ID ja cadastrado para esta escola")
            logger.error("Erro ao criar aluno (integridade): %s", str(e))
            raise BadRequestError("Erro ao criar aluno: dados inválidos")
        except Exception as e:
            self.db.rollback()
            self.storage_service.delete_photo(stored_photo.url if stored_photo else None)
            logger.error("Erro ao criar aluno: %s", str(e))
            raise

    def buscar(self, user: Usuario, aluno_id: int) -> Aluno:
        aluno = self.alunos.get_by_user(aluno_id, user.id)
        if not aluno:
            raise NotFoundError("Aluno nao encontrado")
        return aluno

    def buscar_para_usuario_ou_admin(self, user: Usuario, aluno_id: int) -> Aluno:
        aluno = self.alunos.get(aluno_id) if user.is_superuser else self.alunos.get_by_user(aluno_id, user.id)
        if not aluno:
            raise NotFoundError("Aluno nao encontrado")
        return aluno

    def buscar_por_external_id(self, external_id: str, empresa_id: int) -> Aluno:
        aluno = self.alunos.get_by_external_id(str(external_id), empresa_id)
        if not aluno:
            raise BadRequestError("external_id invalido para empresa_id informado")
        return aluno

    def vincular_responsavel(
        self,
        user: Usuario,
        aluno_id: int,
        payload: ResponsavelCreate,
    ) -> Responsavel:
        aluno = self.buscar_para_usuario_ou_admin(user, aluno_id)
        telefone = payload.telefone.strip()
        email = str(payload.email).strip().lower() if payload.email else None

        for responsavel in aluno.responsaveis:
            mesmo_telefone = responsavel.telefone.strip() == telefone
            mesmo_email = bool(email and responsavel.email and responsavel.email.strip().lower() == email)
            if mesmo_telefone or mesmo_email:
                return responsavel

        responsavel = (
            self.db.query(Responsavel)
            .filter(or_(Responsavel.telefone == telefone, Responsavel.email == email) if email else Responsavel.telefone == telefone)
            .order_by(Responsavel.id.asc())
            .first()
        )
        if not responsavel:
            responsavel = Responsavel(
                nome=payload.nome.strip(),
                telefone=telefone,
                email=email,
            )
            self.db.add(responsavel)
            self.db.flush()

        if responsavel not in aluno.responsaveis:
            aluno.responsaveis.append(responsavel)
        self.db.commit()
        self.db.refresh(responsavel)
        return responsavel

    def atualizar(
        self,
        user: Usuario,
        aluno_id: int,
        nome: str,
        numero_inscricao: str,
        telefone: str,
        turma: str = "",
        foto: UploadFile | None = None,
    ) -> Aluno:
        aluno = self.buscar(user, aluno_id)
        numero_inscricao = self._normalizar_numero_inscricao(numero_inscricao)
        foto_antiga = aluno.foto
        nome_antigo = aluno.nome
        nome_normalizado = nome.strip()
        nome_mudou = nome_normalizado != nome_antigo
        stored_photo = self.storage_service.save_student_photo(foto) if foto else None

        aluno.nome = nome_normalizado
        aluno.numero_inscricao = numero_inscricao
        aluno.telefone = telefone
        aluno.turma = turma.strip() or None

        if stored_photo:
            aluno.foto = stored_photo.url
            aluno.biometria_status = "pending"
            aluno.biometria_error = None

        try:
            self.db.flush()  # Força constraint check do UNIQUE
            self.db.commit()
            self.db.refresh(aluno)
            if stored_photo:
                self.storage_service.delete_photo(foto_antiga)
                self._registrar_foto_principal(aluno, stored_photo)
            trace_id = gerar_trace_id("cadastro-aluno", aluno.id)
            logger.info("Aluno atualizado: id=%d trace_id=%s", aluno_id, trace_id)
            if stored_photo or nome_mudou:
                self._sync_aluno_safely(
                    aluno,
                    action="atualizacao",
                    photo_file=stored_photo,
                    trace_id=trace_id,
                )
            return aluno
        except IntegrityError as e:
            self.db.rollback()
            self.storage_service.delete_photo(stored_photo.url if stored_photo else None)
            # Detecta violação de constraint UNIQUE (SQLite, PostgreSQL)
            if "alunos.user_id, alunos.numero_inscricao" in str(e) or "uq_alunos_user_numero_inscricao" in str(e):
                logger.warning("Numero inscricao duplicado na atualização: %s", numero_inscricao)
                raise BadRequestError("Numero de inscricao ja cadastrado para esta escola")
            logger.error("Erro ao atualizar aluno (integridade): %s", str(e))
            raise BadRequestError("Erro ao atualizar aluno: dados inválidos")
        except Exception as e:
            self.db.rollback()
            self.storage_service.delete_photo(stored_photo.url if stored_photo else None)
            logger.error("Erro ao atualizar aluno: %s", str(e))
            raise

    def deletar(self, user: Usuario, aluno_id: int) -> None:
        aluno = self.buscar(user, aluno_id)
        aluno_snapshot = self._snapshot_aluno(aluno)
        foto_url = aluno.foto
        self.alunos.delete(aluno)
        self.db.commit()
        self.storage_service.delete_photo(foto_url)
        self._delete_biometria_safely(aluno_snapshot)
        logger.info("Aluno deletado: id=%d por usuario id=%d", aluno_id, user.id)

    def deletar_admin(self, admin: Usuario, aluno_id: int) -> None:
        aluno = self.alunos.get(aluno_id)
        if not aluno:
            raise NotFoundError("Aluno nao encontrado")
        aluno_snapshot = self._snapshot_aluno(aluno)
        foto_url = aluno.foto
        self.alunos.delete(aluno)
        self.db.commit()
        self.storage_service.delete_photo(foto_url)
        self._delete_biometria_safely(aluno_snapshot)
        logger.info("Aluno id=%d deletado pelo admin id=%d", aluno_id, admin.id)

    def _normalizar_numero_inscricao(self, numero_inscricao: str) -> str:
        numero_inscricao = numero_inscricao.strip()
        if not numero_inscricao:
            raise BadRequestError("Numero de inscricao e obrigatorio")
        return numero_inscricao

    def retry_biometria(self, user: Usuario, aluno_id: int) -> Aluno:
        aluno = self.buscar_para_usuario_ou_admin(user, aluno_id)
        if not aluno.foto:
            self._set_biometria_status(aluno, "no_photo", error="Aluno sem foto cadastrada")
            raise BadRequestError("Aluno sem foto cadastrada")

        trace_id = gerar_trace_id("biometria", aluno.id)
        logger.info("Retentativa de biometria iniciada aluno_id=%d trace_id=%s", aluno.id, trace_id)
        self._sync_aluno_safely(aluno, action="retentativa", trace_id=trace_id)
        return aluno

    def listar_fotos(self, user: Usuario, aluno_id: int) -> list[AlunoFoto]:
        aluno = self.buscar_para_usuario_ou_admin(user, aluno_id)
        return (
            self.db.query(AlunoFoto)
            .filter(AlunoFoto.aluno_id == aluno.id, AlunoFoto.empresa_id == aluno.empresa_id)
            .order_by(AlunoFoto.principal.desc(), AlunoFoto.criada_em.desc(), AlunoFoto.id.desc())
            .all()
        )

    def adicionar_foto(self, user: Usuario, aluno_id: int, foto: UploadFile) -> AlunoFoto:
        aluno = self.buscar_para_usuario_ou_admin(user, aluno_id)
        stored_photo = self.storage_service.save_student_photo(foto)
        if not stored_photo:
            raise BadRequestError("Foto invalida")

        aluno_foto = AlunoFoto(
            aluno_id=aluno.id,
            empresa_id=aluno.empresa_id,
            url=stored_photo.url,
            tipo="biometrica",
            principal=False,
            biometria_status="syncing",
        )
        self.db.add(aluno_foto)
        self.db.flush()

        trace_id = gerar_trace_id("biometria", aluno.id)
        logger.info(
            "Foto biometrica adicionada aluno_id=%d foto_id=%d trace_id=%s",
            aluno.id,
            aluno_foto.id,
            trace_id,
        )
        result = self.integration_service.add_aluno_face_sample(
            aluno,
            photo_file=stored_photo,
            trace_id=trace_id,
        )
        if result is not None and not getattr(result, "success", True):
            aluno_foto.biometria_status = self._status_from_sync_error(result)
            aluno_foto.biometria_error = getattr(result, "message", None) or getattr(result, "error", None)
        else:
            data = getattr(result, "data", None) or {}
            aluno_foto.biometria_status = self._status_from_sync_result(data)
            aluno_foto.biometria_error = self._error_from_sync_result(data)
            aluno_foto.face_sample_id = self._extract_face_sample_id(data)
            aluno.face_samples_count = self._extract_face_samples_count(data, aluno)
            aluno.biometria_status = aluno_foto.biometria_status
            aluno.biometria_error = aluno_foto.biometria_error
            aluno.biometria_atualizada_em = datetime.now(timezone.utc)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            self._compensar_foto_biometrica(aluno, aluno_foto, trace_id)
            self.storage_service.delete_photo(stored_photo.url)
            raise BadRequestError("Nao foi possivel salvar a foto biometrica") from exc
        except SQLAlchemyError:
            self.db.rollback()
            self._compensar_foto_biometrica(aluno, aluno_foto, trace_id)
            self.storage_service.delete_photo(stored_photo.url)
            raise

        self.db.refresh(aluno_foto)
        return aluno_foto

    def _compensar_foto_biometrica(
        self,
        aluno: Aluno,
        aluno_foto: AlunoFoto,
        trace_id: str,
    ) -> None:
        if not aluno_foto.face_sample_id:
            return

        result = self.integration_service.delete_aluno_face_sample(
            aluno,
            aluno_foto.face_sample_id,
            trace_id=trace_id,
        )
        if result.success:
            return

        logger.error(
            "Falha ao compensar amostra biometrica remota: aluno_id=%d foto_id=%d "
            "sample_id=%d error=%s",
            aluno.id,
            aluno_foto.id,
            aluno_foto.face_sample_id,
            result.error or result.message or "unknown_error",
            extra={"trace_id": trace_id},
        )

    def deletar_foto(self, user: Usuario, aluno_id: int, foto_id: int) -> None:
        aluno = self.buscar_para_usuario_ou_admin(user, aluno_id)
        aluno_foto = (
            self.db.query(AlunoFoto)
            .filter(
                AlunoFoto.id == foto_id,
                AlunoFoto.aluno_id == aluno.id,
                AlunoFoto.empresa_id == aluno.empresa_id,
            )
            .first()
        )
        if not aluno_foto:
            raise NotFoundError("Foto nao encontrada")
        if aluno_foto.principal:
            raise BadRequestError("A foto principal deve ser alterada pela edicao do aluno")

        trace_id = gerar_trace_id("biometria", aluno.id)
        delete_result = None
        if aluno_foto.face_sample_id:
            delete_result = self.integration_service.delete_aluno_face_sample(
                aluno,
                aluno_foto.face_sample_id,
                trace_id=trace_id,
            )
        foto_url = aluno_foto.url
        deleted_status = aluno_foto.biometria_status
        deleted_error = aluno_foto.biometria_error
        self.db.delete(aluno_foto)
        result_data = getattr(delete_result, "data", None) or {}
        remaining = result_data.get("remaining_face_samples")
        try:
            aluno.face_samples_count = max(int(remaining), 0)
        except (TypeError, ValueError):
            aluno.face_samples_count = max((aluno.face_samples_count or 1) - 1, 0)
        self._recalcular_status_biometria(aluno, deleted_status=deleted_status, deleted_error=deleted_error)
        self.db.commit()
        self.storage_service.delete_photo(foto_url)

    @staticmethod
    def _snapshot_aluno(aluno: Aluno) -> SimpleNamespace:
        return SimpleNamespace(
            id=aluno.id,
            external_id=aluno.external_id,
            nome=aluno.nome,
            empresa_id=aluno.empresa_id,
            foto=aluno.foto,
        )

    def _registrar_foto_principal(self, aluno: Aluno, stored_photo: StoredPhoto) -> None:
        self.db.query(AlunoFoto).filter(
            AlunoFoto.aluno_id == aluno.id,
            AlunoFoto.principal.is_(True),
        ).delete(synchronize_session=False)
        self.db.add(
            AlunoFoto(
                aluno_id=aluno.id,
                empresa_id=aluno.empresa_id,
                url=stored_photo.url,
                tipo="principal",
                principal=True,
                biometria_status=aluno.biometria_status,
                biometria_error=aluno.biometria_error,
            )
        )
        self.db.commit()
        self.db.refresh(aluno)

    def _sync_aluno_safely(
        self,
        aluno: Aluno,
        *,
        action: str,
        photo_file: StoredPhoto | None = None,
        trace_id: str | None = None,
    ) -> None:
        if not aluno.foto and photo_file is None:
            self._set_biometria_status(aluno, "no_photo")
            return

        self._set_biometria_status(aluno, "syncing")
        try:
            result = self._call_sync_aluno(aluno, photo_file=photo_file, trace_id=trace_id)
        except Exception as exc:
            self._set_biometria_status(aluno, "failed", error=exc.__class__.__name__)
            logger.error(
                "Falha inesperada no sync de %s do aluno id=%d: %s",
                action,
                aluno.id,
                exc.__class__.__name__,
                extra={"trace_id": trace_id},
            )
            return

        if result is not None and not getattr(result, "success", True):
            status = self._status_from_sync_error(result)
            self._set_biometria_status(
                aluno,
                status,
                error=getattr(result, "message", None) or getattr(result, "error", None),
            )
            logger.warning(
                "Sync de %s do aluno id=%d nao concluido: error=%s status=%s retryable=%s",
                action,
                aluno.id,
                getattr(result, "error", None),
                getattr(result, "status_code", None),
                getattr(result, "retryable", None),
            )
            return

        result_data = getattr(result, "data", None) or {}
        if not result_data:
            self._set_biometria_status(aluno, "failed", error="empty_response")
            logger.warning(
                "Sync de %s do aluno id=%d retornou HTTP sucesso sem corpo util",
                action,
                aluno.id,
            )
            return
        samples_count = self._extract_face_samples_count(result_data, aluno)
        self._set_biometria_status(
            aluno,
            self._status_from_sync_result(result_data),
            error=self._error_from_sync_result(result_data),
            face_samples_count=samples_count,
        )

    def _set_biometria_status(
        self,
        aluno: Aluno,
        status: str,
        *,
        error: str | None = None,
        face_samples_count: int | None = None,
    ) -> None:
        aluno.biometria_status = status
        aluno.biometria_error = error
        aluno.biometria_atualizada_em = datetime.now(timezone.utc)
        if face_samples_count is not None:
            aluno.face_samples_count = face_samples_count
        self.db.commit()
        self.db.refresh(aluno)

    @staticmethod
    def _extract_face_samples_count(data: dict, aluno: Aluno) -> int:
        value = data.get("face_samples_count")
        try:
            count = int(value)
        except (TypeError, ValueError):
            count = 0
        return count if count > 0 else max(aluno.face_samples_count or 0, 0)

    @staticmethod
    def _status_from_sync_result(data: dict) -> str:
        status = str(data.get("biometria_status") or data.get("status") or "").strip()
        if status in {"ready", "pending", "syncing", "failed", "no_photo", "needs_new_photo", "retrying"}:
            return status
        if status in {"ok", "success"}:
            samples = data.get("face_samples_count")
            try:
                return "ready" if int(samples) > 0 else "failed"
            except (TypeError, ValueError):
                return "failed"
        error = str(data.get("biometria_error") or data.get("error") or "").strip().upper()
        if error in {"NO_FACE_DETECTED", "MULTIPLE_FACES_DETECTED", "INVALID_IMAGE", "LOW_QUALITY_IMAGE"}:
            return "needs_new_photo"
        if error in {"MODEL_ERROR", "DATABASE_ERROR"}:
            return "retrying"
        return "failed"

    @staticmethod
    def _status_from_sync_error(result) -> str:
        data = getattr(result, "data", None) or {}
        detail = str(getattr(result, "message", None) or data.get("detail") or data.get("error") or "")
        normalized = detail.upper()
        if normalized in {"NO_FACE_DETECTED", "MULTIPLE_FACES_DETECTED", "INVALID_IMAGE", "LOW_QUALITY_IMAGE"}:
            return "needs_new_photo"
        if normalized in {"MODEL_ERROR", "DATABASE_ERROR"}:
            return "retrying"
        if any(token in detail.lower() for token in ("no_face", "face", "rosto", "imagem", "image")):
            return "needs_new_photo"
        return "retrying" if getattr(result, "retryable", False) else "failed"

    @staticmethod
    def _extract_face_sample_id(data: dict) -> int | None:
        value = data.get("face_sample_id")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _call_sync_aluno(
        self,
        aluno: Aluno,
        *,
        photo_file: StoredPhoto | None = None,
        trace_id: str | None = None,
    ):
        signature = inspect.signature(self.integration_service.sync_aluno)
        if "trace_id" in signature.parameters:
            return self.integration_service.sync_aluno(
                aluno,
                photo_file=photo_file,
                trace_id=trace_id,
            )
        return self.integration_service.sync_aluno(aluno, photo_file=photo_file)

    def _call_delete_biometria(self, aluno: SimpleNamespace, trace_id: str | None = None):
        signature = inspect.signature(self.integration_service.delete_aluno_biometria)
        if "trace_id" in signature.parameters:
            return self.integration_service.delete_aluno_biometria(aluno, trace_id=trace_id)
        return self.integration_service.delete_aluno_biometria(aluno)

    @staticmethod
    def _error_from_sync_result(data: dict) -> str | None:
        value = data.get("biometria_error") or data.get("error")
        return str(value) if value else None

    def _recalcular_status_biometria(
        self,
        aluno: Aluno,
        *,
        deleted_status: str | None = None,
        deleted_error: str | None = None,
    ) -> None:
        valid_samples = (
            self.db.query(AlunoFoto)
            .filter(
                AlunoFoto.aluno_id == aluno.id,
                AlunoFoto.empresa_id == aluno.empresa_id,
                AlunoFoto.biometria_status == "ready",
            )
            .count()
        )
        if aluno.face_samples_count > 0 or valid_samples > 0:
            aluno.biometria_status = "ready"
            aluno.biometria_error = None
        elif not aluno.foto:
            aluno.biometria_status = "no_photo"
            aluno.biometria_error = None
        elif deleted_status in {"failed", "needs_new_photo"}:
            aluno.biometria_status = deleted_status
            aluno.biometria_error = deleted_error
        else:
            aluno.biometria_status = "failed"
            aluno.biometria_error = deleted_error or "no_valid_face_samples"
        aluno.biometria_atualizada_em = datetime.now(timezone.utc)

    def _delete_biometria_safely(self, aluno: SimpleNamespace) -> None:
        try:
            result = self._call_delete_biometria(
                aluno,
                trace_id=gerar_trace_id("biometria", getattr(aluno, "id", None)),
            )
        except Exception as exc:
            logger.error(
                "Falha inesperada na exclusao biometrica do aluno id=%s: %s",
                aluno.id,
                exc.__class__.__name__,
            )
            return

        if result is not None and not getattr(result, "success", True):
            logger.warning(
                "Exclusao biometrica do aluno id=%s nao concluida: error=%s status=%s retryable=%s",
                aluno.id,
                getattr(result, "error", None),
                getattr(result, "status_code", None),
                getattr(result, "retryable", None),
            )
