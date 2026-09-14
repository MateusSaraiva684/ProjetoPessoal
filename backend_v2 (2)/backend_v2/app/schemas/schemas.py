from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Mensagem(BaseModel):
    mensagem: str


class ErroResponse(BaseModel):
    erro: str
    detalhe: Optional[str | List[str]] = None


class RegistrarRequest(BaseModel):
    nome: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    senha: str = Field(..., min_length=6, max_length=255)
    
    @field_validator("nome", "senha")
    @classmethod
    def nao_vazio_ou_apenas_espacos(cls, v):
        if not v.strip():
            raise ValueError("Campo não pode conter apenas espaços em branco")
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str
    mfa_code: Optional[str] = Field(None, min_length=6, max_length=8)


class RefreshRequest(BaseModel):
    refresh_token: str


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    is_superuser: bool
    role: str
    criado_em: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario: UsuarioResponse


class ResponsavelCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=255)
    telefone: str = Field(..., min_length=1, max_length=20)
    email: Optional[EmailStr] = None
    parentesco: Optional[str] = Field(None, max_length=50)
    
    @field_validator("nome", "telefone", "parentesco")
    @classmethod
    def nao_vazio_ou_apenas_espacos(cls, v):
        if v and not v.strip():
            raise ValueError("Campo não pode conter apenas espaços em branco")
        return v.strip() if v else v


class ResponsavelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    telefone: str
    email: Optional[str] = None


class AlunoCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=255)
    numero_inscricao: str = Field(..., min_length=1, max_length=50)
    telefone: str = Field(..., min_length=1, max_length=20)
    turma: Optional[str] = Field(None, max_length=100)
    
    @field_validator("nome", "numero_inscricao", "telefone", "turma")
    @classmethod
    def nao_vazio_ou_apenas_espacos(cls, v):
        if v and not v.strip():
            raise ValueError("Campo não pode conter apenas espaços em branco")
        return v.strip() if v else v


class AlunoUpdate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=255)
    numero_inscricao: str = Field(..., min_length=1, max_length=50)
    telefone: str = Field(..., min_length=1, max_length=20)
    turma: Optional[str] = Field(None, max_length=100)
    
    @field_validator("nome", "numero_inscricao", "telefone", "turma")
    @classmethod
    def nao_vazio_ou_apenas_espacos(cls, v):
        if v and not v.strip():
            raise ValueError("Campo não pode conter apenas espaços em branco")
        return v.strip() if v else v


class AlunoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    numero_inscricao: str
    telefone: str
    turma: Optional[str] = None
    foto: Optional[str] = None
    external_id: str
    empresa_id: int
    biometria_status: str
    biometria_error: Optional[str] = None
    biometria_atualizada_em: Optional[datetime] = None
    face_samples_count: int
    criado_em: datetime
    user_id: int
    responsaveis: List[ResponsavelResponse] = Field(default_factory=list)


OrigemPresenca = Literal["manual", "facial", "webhook", "sistema"]
StatusPresenca = Literal["confirmado", "pendente", "erro"]
TipoEventoPresenca = Literal["entrada", "saida", "manual", "ajuste_admin"]
TurnoPresenca = Literal["manha", "tarde", "noite", "integral"]


class PresencaManualCreate(BaseModel):
    aluno_id: int
    timestamp: Optional[datetime] = None
    status: StatusPresenca = "confirmado"
    tipo_evento: TipoEventoPresenca = "manual"
    turno: Optional[TurnoPresenca] = None
    observacao: Optional[str] = Field(None, max_length=500)

    @field_validator("timestamp")
    @classmethod
    def timestamp_deve_ter_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp deve incluir timezone")
        return value


class PresencaReconhecimentoCreate(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=100)
    empresa_id: int = Field(..., gt=0)
    timestamp: Optional[datetime] = None
    confianca: Optional[float] = Field(None, ge=0, le=1)
    status: StatusPresenca = "confirmado"
    tipo_evento: Literal["entrada", "saida"] = "entrada"
    turno: Optional[TurnoPresenca] = None
    camera_id: Optional[str] = Field(None, max_length=100)

    @field_validator("external_id", mode="before")
    @classmethod
    def normalizar_external_id(cls, value):
        if value is None:
            return value
        value = str(value).strip()
        if not value:
            raise ValueError("external_id nao pode ser vazio")
        return value

    @field_validator("timestamp")
    @classmethod
    def timestamp_deve_ter_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp deve incluir timezone")
        return value


class RecognitionPresenceWebhookCreate(BaseModel):
    event: Literal["presence_detected"]
    event_id: str = Field(..., min_length=1, max_length=255)
    school_id: str = Field(..., min_length=1, max_length=100)
    camera_id: Optional[str] = Field(None, max_length=100)
    presence_id: Optional[int] = None
    student_id: str = Field(..., min_length=1, max_length=100)
    student_name: Optional[str] = Field(None, max_length=255)
    confidence: float = Field(..., ge=0, le=1)
    detected_at: datetime
    tipo_evento: Literal["entrada", "saida"] = "entrada"
    turno: Optional[TurnoPresenca] = None
    message_template: Optional[str] = Field(None, max_length=500)
    trace_id: Optional[str] = Field(None, max_length=255)

    @field_validator("event_id", "school_id", "student_id", "student_name", "camera_id", mode="before")
    @classmethod
    def normalizar_texto(cls, value):
        if value is None:
            return value
        value = str(value).strip()
        if not value:
            raise ValueError("campo nao pode ser vazio")
        return value

    @field_validator("detected_at")
    @classmethod
    def detected_at_deve_ter_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("detected_at deve incluir timezone")
        return value


class PresencaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    aluno_id: int
    timestamp: datetime
    tipo_evento: str = "entrada"
    origem: OrigemPresenca
    turno: Optional[str] = None
    camera_id: Optional[str] = None
    confianca: Optional[float] = None
    status: StatusPresenca
    recognition_event_id: Optional[str] = None
    observacao: Optional[str] = None


class PresencaCreate(BaseModel):
    aluno_id: int
    timestamp: Optional[datetime] = None
    turno: Optional[TurnoPresenca] = None
    observacao: Optional[str] = Field(None, max_length=500)

    @field_validator("timestamp")
    @classmethod
    def timestamp_deve_ter_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp deve incluir timezone")
        return value


class AlunoFotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    aluno_id: int
    empresa_id: int
    url: str
    storage_public_id: Optional[str] = None
    tipo: str
    principal: bool
    criada_em: datetime
    biometria_status: str
    biometria_error: Optional[str] = None
    face_sample_id: Optional[int] = None


class NotificationOutboxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    empresa_id: Optional[int] = None
    tipo: str
    status: str
    canal: str
    presenca_id: int
    aluno_id: int
    responsavel_id: int
    telefone_destino: str
    mensagem: str
    attempts: int
    last_error: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None


class ReconhecimentoFacialResponse(BaseModel):
    aluno_id: int
    confianca: float
    presenca: PresencaResponse
    mensagem: str


class ReconhecimentoIdentificacaoResponse(BaseModel):
    status: str = "success"
    aluno_id: int
    external_id: str
    school_id: Optional[str] = None
    confianca: float
    candidatos: List[dict] = Field(default_factory=list)
    trace_id: Optional[str] = None
    aluno: AlunoResponse
    mensagem: str


class FaceEmbeddingCreate(BaseModel):
    aluno_id: int
    embedding: List[float]


class FaceEmbeddingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    aluno_id: int
    embedding: List[float]
    criado_em: datetime


class AtualizarUsuarioRequest(BaseModel):
    nome: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    ativo: Optional[bool] = None
    role: Optional[Literal["superadmin", "gestor", "operator"]] = None
    
    @field_validator("nome")
    @classmethod
    def nome_nao_vazio(cls, v):
        if v and not v.strip():
            raise ValueError("Nome não pode conter apenas espaços em branco")
        return v.strip() if v else None


class RedefinirSenhaRequest(BaseModel):
    nova_senha: str = Field(..., min_length=6, max_length=255)
    
    @field_validator("nova_senha")
    @classmethod
    def senha_valida(cls, v):
        if not v.strip():
            raise ValueError("Senha não pode conter apenas espaços em branco")
        return v


class PaginacaoMetadata(BaseModel):
    """Metadata de paginação."""
    total: int
    pagina: int
    limite: int
    paginas_totais: int
    proxima_pagina: Optional[int] = None


class PaginadoResponse(BaseModel):
    """Resposta paginada genérica."""
    data: List[AlunoResponse]
    paginacao: PaginacaoMetadata
