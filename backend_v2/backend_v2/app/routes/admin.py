from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.database.session import get_db
from app.models.models import Usuario
from app.routes.auth import get_current_user
from app.schemas.schemas import AtualizarUsuarioRequest, RedefinirSenhaRequest
from app.services.admin_service import AdminService

router = APIRouter()


def get_superuser(user: Usuario = Depends(get_current_user)) -> Usuario:
    if user.role != "superadmin" or not user.is_superuser:
        raise ForbiddenError("Acesso restrito a administradores")
    return user


def get_admin_service(db: Session = Depends(get_db)) -> AdminService:
    return AdminService(db)


@router.get("/stats")
def estatisticas(
    _: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    return service.estatisticas()


@router.get("/system-health")
def system_health(
    _: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    return service.system_health()


@router.get("/audit-logs")
def listar_auditoria(
    limit: int = Query(100, ge=1, le=200),
    _: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    return service.listar_auditoria(limit=limit)


@router.get("/usuarios")
def listar_usuarios(
    _: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    return service.listar_usuarios()


@router.get("/escolas")
def listar_escolas(
    _: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    return service.listar_escolas()


@router.get("/escolas/{empresa_id}/alunos")
def listar_alunos_por_escola(
    empresa_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    return service.listar_todos_alunos(page=page, limit=limit, empresa_id=empresa_id)


@router.patch("/usuarios/{usuario_id}")
def atualizar_usuario(
    usuario_id: int,
    body: AtualizarUsuarioRequest,
    admin: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    return service.atualizar_usuario(usuario_id, body, admin)


@router.patch("/usuarios/{usuario_id}/senha")
def redefinir_senha(
    usuario_id: int,
    body: RedefinirSenhaRequest,
    admin: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    return service.redefinir_senha(usuario_id, body, admin)


@router.patch("/usuarios/{usuario_id}/ativo")
def toggle_usuario_ativo(
    usuario_id: int,
    admin: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    return service.toggle_usuario_ativo(usuario_id, admin)


@router.delete("/usuarios/{usuario_id}")
def deletar_usuario(
    usuario_id: int,
    admin: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    return service.deletar_usuario(usuario_id, admin)


@router.get("/alunos")
def listar_todos_alunos(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    empresa_id: int | None = Query(None, ge=1),
    turma: str | None = Query(None),
    busca: str | None = Query(None),
    search: str | None = Query(None),
    biometria_status: str | None = Query(None),
    sem_foto: bool | None = Query(None),
    com_erro_biometria: bool | None = Query(None),
    criado_de: date | None = Query(None),
    criado_ate: date | None = Query(None),
    _: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    """Lista todos os alunos com paginação.
    
    Args:
        page: Número da página (padrão: 1)
        limit: Registros por página (padrão: 50, máximo: 100)
    """
    return service.listar_todos_alunos(
        page=page,
        limit=limit,
        empresa_id=empresa_id,
        turma=turma,
        busca=search or busca,
        biometria_status=biometria_status,
        sem_foto=sem_foto,
        com_erro_biometria=com_erro_biometria,
        criado_de=criado_de,
        criado_ate=criado_ate,
    )


@router.delete("/alunos/{aluno_id}")
def deletar_aluno(
    aluno_id: int,
    admin: Usuario = Depends(get_superuser),
    service: AdminService = Depends(get_admin_service),
):
    return service.deletar_aluno(aluno_id, admin)
