import logging
from datetime import date

from sqlalchemy import desc, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.trace import gerar_trace_id
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.security import hash_senha
from app.models.models import AuditLog, Usuario
from app.repositories.aluno_repository import AlunoRepository
from app.repositories.notification_repository import NotificationOutboxRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.schemas import AtualizarUsuarioRequest, RedefinirSenhaRequest
from app.services.aluno_service import AlunoService
from app.services.integration_service import IntegrationService
from app.services.storage_service import StorageService
from app.services.audit_service import registrar_auditoria

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self.usuarios = UsuarioRepository(db)
        self.alunos = AlunoRepository(db)
        self.notifications = NotificationOutboxRepository(db)
        self.aluno_service = AlunoService(db)
        self.storage_service = StorageService()

    def estatisticas(self) -> dict:
        total_usuarios = self.usuarios.count_all()
        usuarios_ativos = self.usuarios.count_active()
        return {
            "total_usuarios": total_usuarios,
            "usuarios_ativos": usuarios_ativos,
            "usuarios_inativos": total_usuarios - usuarios_ativos,
            "total_alunos": self.alunos.count_all(),
        }

    def listar_auditoria(self, limit: int = 100) -> list[dict]:
        registros = (
            self.db.query(AuditLog, Usuario.email)
            .outerjoin(Usuario, AuditLog.actor_user_id == Usuario.id)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": registro.id,
                "actor_user_id": registro.actor_user_id,
                "actor_email": email,
                "action": registro.action,
                "resource_type": registro.resource_type,
                "resource_id": registro.resource_id,
                "metadata": registro.audit_metadata or {},
                "ip_address": registro.ip_address,
                "trace_id": registro.trace_id,
                "created_at": registro.created_at,
            }
            for registro, email in registros
        ]

    def listar_usuarios(self) -> list[dict]:
        totais_alunos = self.alunos.count_by_user_map()
        return [
            {
                "id": u.id,
                "nome": u.nome,
                "email": u.email,
                "ativo": u.ativo,
                "is_superuser": u.is_superuser,
                "role": u.role,
                "criado_em": u.criado_em,
                "total_alunos": totais_alunos.get(u.id, 0),
            }
            for u in self.usuarios.list_all()
        ]

    def listar_escolas(self) -> list[dict]:
        totais_alunos = self.alunos.count_by_user_map()
        return [
            {
                "id": escola.id,
                "nome": escola.nome,
                "email": escola.email,
                "ativo": escola.ativo,
                "criado_em": escola.criado_em,
                "total_alunos": totais_alunos.get(escola.id, 0),
            }
            for escola in self.usuarios.list_escolas()
        ]

    def atualizar_usuario(
        self,
        usuario_id: int,
        body: AtualizarUsuarioRequest,
        admin: Usuario,
    ) -> dict:
        usuario = self._buscar_usuario(usuario_id)
        if usuario.is_superuser and usuario.id != admin.id:
            raise ForbiddenError("Nao e possivel editar outro superusuario")
        if body.role is not None and admin.role != "superadmin":
            raise ForbiddenError("Somente superadmin pode alterar papeis")
        if body.role == "superadmin" and not usuario.is_superuser:
            raise ForbiddenError("O papel superadmin exige is_superuser")
        if usuario.is_superuser and body.email is not None and body.email != usuario.email:
            raise ForbiddenError(
                "Altere o e-mail do administrador pela configuracao ADMIN_EMAIL"
            )
        if usuario.is_superuser and body.ativo is False:
            raise ForbiddenError("Nao e possivel desativar um superusuario")
        if body.nome is not None:
            usuario.nome = body.nome
        if body.email is not None:
            if self.usuarios.email_exists_for_other_user(body.email, usuario_id):
                raise BadRequestError("E-mail ja esta em uso")
            usuario.email = body.email
        if body.ativo is not None:
            usuario.ativo = body.ativo
        if body.role is not None:
            usuario.role = body.role
        self.db.commit()
        registrar_auditoria(
            self.db,
            actor_user_id=admin.id,
            action="admin.user.updated",
            resource_type="usuario",
            resource_id=usuario.id,
            metadata={"fields": [field for field, value in {"nome": body.nome, "ativo": body.ativo, "role": body.role}.items() if value is not None]},
        )
        self.db.commit()
        logger.info("Usuario id=%d atualizado pelo admin id=%d", usuario_id, admin.id)
        return {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "ativo": usuario.ativo,
            "role": usuario.role,
        }

    def redefinir_senha(
        self,
        usuario_id: int,
        body: RedefinirSenhaRequest,
        admin: Usuario,
    ) -> dict:
        if len(body.nova_senha) < 6:
            raise BadRequestError("Senha deve ter no minimo 6 caracteres")
        usuario = self._buscar_usuario(usuario_id)
        if usuario.is_superuser and usuario.id != admin.id:
            raise ForbiddenError("Nao e possivel redefinir senha de outro superusuario")
        usuario.senha = hash_senha(body.nova_senha)
        self.db.commit()
        registrar_auditoria(
            self.db,
            actor_user_id=admin.id,
            action="admin.user.password_reset",
            resource_type="usuario",
            resource_id=usuario.id,
        )
        self.db.commit()
        logger.info("Senha do usuario id=%d redefinida pelo admin id=%d", usuario_id, admin.id)
        return {"mensagem": "Senha redefinida com sucesso"}

    def toggle_usuario_ativo(self, usuario_id: int, admin: Usuario) -> dict:
        usuario = self._buscar_usuario(usuario_id)
        if usuario.is_superuser:
            raise ForbiddenError("Nao e possivel desativar um superusuario")
        usuario.ativo = not usuario.ativo
        self.db.commit()
        registrar_auditoria(
            self.db,
            actor_user_id=admin.id,
            action="admin.user.status_changed",
            resource_type="usuario",
            resource_id=usuario.id,
            metadata={"ativo": usuario.ativo},
        )
        self.db.commit()
        status_str = "ativado" if usuario.ativo else "desativado"
        logger.info("Usuario id=%d %s pelo admin id=%d", usuario_id, status_str, admin.id)
        return {"id": usuario.id, "ativo": usuario.ativo, "mensagem": f"Usuario {status_str}"}

    def deletar_usuario(self, usuario_id: int, admin: Usuario) -> dict:
        usuario = self._buscar_usuario(usuario_id)
        if usuario.is_superuser:
            raise ForbiddenError("Nao e possivel remover um superusuario")

        fotos_para_deletar = [
            aluno.foto for aluno in self.alunos.list_all_by_user(usuario_id) if aluno.foto
        ]

        self.usuarios.delete(usuario)
        self.db.commit()
        registrar_auditoria(
            self.db,
            actor_user_id=admin.id,
            action="admin.user.deleted",
            resource_type="usuario",
            resource_id=usuario_id,
        )
        self.db.commit()
        for foto in fotos_para_deletar:
            self.storage_service.delete_photo(foto)
        logger.info("Usuario id=%d deletado pelo admin id=%d", usuario_id, admin.id)
        return {"mensagem": "Usuario removido com sucesso"}

    def listar_todos_alunos(
        self,
        page: int = 1,
        limit: int = 50,
        empresa_id: int | None = None,
        turma: str | None = None,
        busca: str | None = None,
        biometria_status: str | None = None,
        sem_foto: bool | None = None,
        com_erro_biometria: bool | None = None,
        criado_de: date | None = None,
        criado_ate: date | None = None,
    ) -> dict:
        """Lista todos os alunos com paginação.
        
        Args:
            page: Número da página (começa em 1)
            limit: Número de registros por página
            
        Returns:
            Dicionário com dados paginados e metadados
        """
        if empresa_id is not None:
            escola = self._buscar_usuario(empresa_id)
            if escola.is_superuser:
                raise BadRequestError("Escola invalida")

        skip = (page - 1) * limit
        alunos, total = self.alunos.list_all_with_usuario(
            skip=skip,
            limit=limit,
            empresa_id=empresa_id,
            turma=turma,
            busca=busca,
            biometria_status=biometria_status,
            sem_foto=sem_foto,
            com_erro_biometria=com_erro_biometria,
            criado_de=criado_de,
            criado_ate=criado_ate,
        )
        
        return {
            "data": [
                {
                    "id": a[0].id,
                    "nome": a[0].nome,
                    "numero_inscricao": a[0].numero_inscricao,
                    "telefone": a[0].telefone,
                    "foto": a[0].foto,
                    "external_id": a[0].external_id,
                    "biometria_status": a[0].biometria_status,
                    "biometria_error": a[0].biometria_error,
                    "biometria_atualizada_em": a[0].biometria_atualizada_em,
                    "face_samples_count": a[0].face_samples_count,
                    "criado_em": a[0].criado_em,
                    "user_id": a[0].user_id,
                    "empresa_id": a[0].empresa_id,
                    "usuario_nome": a[1],
                    "usuario_email": a[2],
                }
                for a in alunos
            ],
            "paginacao": {
                "total": total,
                "pagina": page,
                "limite": limit,
                "paginas_totais": (total + limit - 1) // limit,
                "proxima_pagina": page + 1 if page * limit < total else None,
            },
        }

    def deletar_aluno(self, aluno_id: int, admin: Usuario) -> dict:
        self.aluno_service.deletar_admin(admin, aluno_id)
        registrar_auditoria(
            self.db,
            actor_user_id=admin.id,
            action="admin.student.deleted",
            resource_type="aluno",
            resource_id=aluno_id,
        )
        self.db.commit()
        return {"mensagem": "Aluno removido com sucesso"}

    def system_health(self) -> dict:
        trace_id = gerar_trace_id("system-health")
        database = {"status": "online", "message": "ok"}
        try:
            self.db.execute(text("SELECT 1"))
        except Exception as exc:
            logger.error("System health database error trace_id=%s error=%s", trace_id, exc.__class__.__name__)
            database = {"status": "error", "message": exc.__class__.__name__}

        try:
            integration_service = IntegrationService()
        except Exception as exc:
            integration_service = None
            logger.error("Recognition health config error trace_id=%s error=%s", trace_id, exc.__class__.__name__)

        recognition = {
            "status": "offline",
            "url": getattr(integration_service, "base_url", ""),
            "message": "Recognition API nao configurada",
        }
        if integration_service and integration_service.base_url:
            result = integration_service.health(trace_id=trace_id)
            if result.success:
                recognition = {
                    "status": "online",
                    "url": integration_service.base_url,
                    "message": "ok",
                    "data": result.data,
                }
            else:
                recognition = {
                    "status": "error" if result.status_code else "offline",
                    "url": integration_service.base_url,
                    "message": result.message or result.error or "unavailable",
                }

        return {
            "backend": {"status": "online"},
            "database": database,
            "recognition_service": recognition,
            "cloudinary": {
                "configured": bool(
                    settings.CLOUDINARY_CLOUD_NAME
                    and settings.CLOUDINARY_API_KEY
                    and settings.CLOUDINARY_API_SECRET
                )
            },
            "webhook": {"configured": bool(settings.RECOGNITION_WEBHOOK_SECRET)},
            "notifications": {
                "pending": self.notifications.count_by_status("pending"),
                "failed": self.notifications.count_by_status("failed"),
            },
            "trace_id": trace_id,
        }

    def _buscar_usuario(self, usuario_id: int) -> Usuario:
        usuario = self.usuarios.get_by_id(usuario_id)
        if not usuario:
            raise NotFoundError("Usuario nao encontrado")
        return usuario
