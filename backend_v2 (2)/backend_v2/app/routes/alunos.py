from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.models import Usuario
from app.routes.auth import get_current_user
from app.schemas.schemas import (
    AlunoCreate,
    AlunoFotoResponse,
    AlunoResponse,
    AlunoUpdate,
    PaginadoResponse,
    ResponsavelCreate,
    ResponsavelResponse,
)
from app.services.aluno_service import AlunoService

router = APIRouter()


def get_aluno_service(db: Session = Depends(get_db)) -> AlunoService:
    return AlunoService(db)


def _validar_aluno_form(schema_cls, **dados):
    try:
        return schema_cls(**dados)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.get("/turmas", response_model=List[str])
def listar_turmas(
    user: Usuario = Depends(get_current_user),
    service: AlunoService = Depends(get_aluno_service),
):
    return service.listar_turmas(user)


@router.get("/", response_model=PaginadoResponse)
def listar(
    turma: Optional[str] = None,
    busca: Optional[str] = None,
    search: Optional[str] = None,
    biometria_status: Optional[str] = None,
    sem_foto: Optional[bool] = None,
    com_erro_biometria: Optional[bool] = None,
    criado_de: Optional[date] = None,
    criado_ate: Optional[date] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user: Usuario = Depends(get_current_user),
    service: AlunoService = Depends(get_aluno_service),
):
    """Lista alunos com paginação.
    
    Parâmetros:
    - page: Número da página (padrão: 1)
    - limit: Itens por página (padrão: 50, máximo: 100)
    - turma: Filtrar por turma (opcional)
    - busca: Buscar por nome ou número de inscrição (opcional)
    """
    return service.listar(
        user,
        turma=turma,
        busca=search or busca,
        biometria_status=biometria_status,
        sem_foto=sem_foto,
        com_erro_biometria=com_erro_biometria,
        criado_de=criado_de,
        criado_ate=criado_ate,
        page=page,
        limit=limit,
    )


@router.post("/", response_model=AlunoResponse, status_code=201)
def criar(
    nome: str = Form(...),
    numero_inscricao: str = Form(...),
    telefone: str = Form(...),
    turma: str = Form(""),
    foto: UploadFile = File(None),
    user: Usuario = Depends(get_current_user),
    service: AlunoService = Depends(get_aluno_service),
):
    payload = _validar_aluno_form(
        AlunoCreate,
        nome=nome,
        numero_inscricao=numero_inscricao,
        telefone=telefone,
        turma=turma,
    )
    return service.criar(
        user=user,
        nome=payload.nome,
        numero_inscricao=payload.numero_inscricao,
        telefone=payload.telefone,
        turma=payload.turma or "",
        foto=foto,
    )


@router.get("/{aluno_id}", response_model=AlunoResponse)
def buscar(
    aluno_id: int,
    user: Usuario = Depends(get_current_user),
    service: AlunoService = Depends(get_aluno_service),
):
    return service.buscar(user, aluno_id)


@router.post("/{aluno_id}/retry-biometria", response_model=AlunoResponse)
def retry_biometria(
    aluno_id: int,
    user: Usuario = Depends(get_current_user),
    service: AlunoService = Depends(get_aluno_service),
):
    return service.retry_biometria(user, aluno_id)


@router.post("/{aluno_id}/responsaveis", response_model=ResponsavelResponse, status_code=201)
def vincular_responsavel(
    aluno_id: int,
    payload: ResponsavelCreate,
    user: Usuario = Depends(get_current_user),
    service: AlunoService = Depends(get_aluno_service),
):
    return service.vincular_responsavel(user, aluno_id, payload)


@router.get("/{aluno_id}/fotos", response_model=List[AlunoFotoResponse])
def listar_fotos(
    aluno_id: int,
    user: Usuario = Depends(get_current_user),
    service: AlunoService = Depends(get_aluno_service),
):
    return service.listar_fotos(user, aluno_id)


@router.post("/{aluno_id}/fotos", response_model=AlunoFotoResponse, status_code=201)
def adicionar_foto(
    aluno_id: int,
    foto: UploadFile = File(...),
    user: Usuario = Depends(get_current_user),
    service: AlunoService = Depends(get_aluno_service),
):
    return service.adicionar_foto(user, aluno_id, foto)


@router.delete("/{aluno_id}/fotos/{foto_id}", status_code=204)
def deletar_foto(
    aluno_id: int,
    foto_id: int,
    user: Usuario = Depends(get_current_user),
    service: AlunoService = Depends(get_aluno_service),
):
    service.deletar_foto(user, aluno_id, foto_id)


@router.put("/{aluno_id}", response_model=AlunoResponse)
def atualizar(
    aluno_id: int,
    nome: str = Form(...),
    numero_inscricao: str = Form(...),
    telefone: str = Form(...),
    turma: str = Form(""),
    foto: UploadFile = File(None),
    user: Usuario = Depends(get_current_user),
    service: AlunoService = Depends(get_aluno_service),
):
    payload = _validar_aluno_form(
        AlunoUpdate,
        nome=nome,
        numero_inscricao=numero_inscricao,
        telefone=telefone,
        turma=turma,
    )
    return service.atualizar(
        user=user,
        aluno_id=aluno_id,
        nome=payload.nome,
        numero_inscricao=payload.numero_inscricao,
        telefone=payload.telefone,
        turma=payload.turma or "",
        foto=foto,
    )


@router.delete("/{aluno_id}", status_code=204)
def deletar(
    aluno_id: int,
    user: Usuario = Depends(get_current_user),
    service: AlunoService = Depends(get_aluno_service),
):
    service.deletar(user, aluno_id)
