from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Boolean,
    UniqueConstraint,
    Index,
    Float,
    JSON,
    Table,
    Text,
)
from sqlalchemy.orm import relationship
from app.database.session import Base


aluno_responsaveis = Table(
    "aluno_responsaveis",
    Base.metadata,
    Column("aluno_id", ForeignKey("alunos.id", ondelete="CASCADE"), primary_key=True),
    Column("responsavel_id", ForeignKey("responsaveis.id", ondelete="CASCADE"), primary_key=True),
)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    senha = Column(String, nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    role = Column(String(30), default="operator", nullable=False, index=True)
    mfa_secret = Column(String(64), nullable=True)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    alunos = relationship(
        "Aluno",
        back_populates="usuario",
        cascade="all, delete-orphan",
        foreign_keys="Aluno.user_id",
    )
    refresh_tokens = relationship("RefreshToken", back_populates="usuario", cascade="all, delete-orphan")


class Aluno(Base):
    __tablename__ = "alunos"
    __table_args__ = (
        UniqueConstraint("user_id", "numero_inscricao", name="uq_alunos_user_numero_inscricao"),
        UniqueConstraint("empresa_id", "external_id", name="uq_alunos_empresa_external_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    numero_inscricao = Column(String, nullable=False)
    telefone = Column(String, nullable=False)
    turma = Column(String, nullable=True)
    foto = Column(String, nullable=True)
    empresa_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    external_id = Column(String, nullable=False)
    biometria_status = Column(String, nullable=False, default="pending")
    biometria_error = Column(String, nullable=True)
    biometria_atualizada_em = Column(DateTime(timezone=True), nullable=True)
    face_samples_count = Column(Integer, nullable=False, default=0)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    usuario = relationship("Usuario", back_populates="alunos", foreign_keys=[user_id])
    responsaveis = relationship(
        "Responsavel",
        secondary=aluno_responsaveis,
        back_populates="alunos",
    )
    presencas = relationship("Presenca", back_populates="aluno", cascade="all, delete-orphan")
    fotos = relationship("AlunoFoto", back_populates="aluno", cascade="all, delete-orphan")
    face_embeddings = relationship("FaceEmbedding", back_populates="aluno", cascade="all, delete-orphan")


class Responsavel(Base):
    __tablename__ = "responsaveis"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    telefone = Column(String, nullable=False)
    email = Column(String, nullable=True)

    alunos = relationship(
        "Aluno",
        secondary=aluno_responsaveis,
        back_populates="responsaveis",
    )


class Presenca(Base):
    __tablename__ = "presencas"
    __table_args__ = (
        UniqueConstraint("recognition_event_id", name="uq_presencas_recognition_event_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    aluno_id = Column(Integer, ForeignKey("alunos.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    tipo_evento = Column(String, nullable=False, default="entrada")
    origem = Column(String, nullable=False)
    turno = Column(String, nullable=True)
    camera_id = Column(String, nullable=True)
    confianca = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="confirmado")
    recognition_event_id = Column(String, nullable=True)
    observacao = Column(Text, nullable=True)
    criado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    aluno = relationship("Aluno", back_populates="presencas")
    notificacoes = relationship(
        "NotificationOutbox",
        back_populates="presenca",
        cascade="all, delete-orphan",
    )


class AlunoFoto(Base):
    __tablename__ = "aluno_fotos"

    id = Column(Integer, primary_key=True, index=True)
    aluno_id = Column(Integer, ForeignKey("alunos.id", ondelete="CASCADE"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    url = Column(String, nullable=False)
    storage_public_id = Column(String, nullable=True)
    tipo = Column(String, nullable=False, default="biometrica")
    principal = Column(Boolean, nullable=False, default=False)
    criada_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    biometria_status = Column(String, nullable=False, default="pending")
    biometria_error = Column(String, nullable=True)
    face_sample_id = Column(Integer, nullable=True)

    aluno = relationship("Aluno", back_populates="fotos")


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        UniqueConstraint(
            "tipo",
            "presenca_id",
            "responsavel_id",
            "canal",
            name="uq_notification_outbox_presence_recipient_channel",
        ),
        Index(
            "ix_notification_outbox_status_next_attempt_at",
            "status",
            "next_attempt_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    tipo = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending", index=True)
    canal = Column(String, nullable=False)
    presenca_id = Column(Integer, ForeignKey("presencas.id", ondelete="CASCADE"), nullable=False, index=True)
    aluno_id = Column(Integer, ForeignKey("alunos.id", ondelete="CASCADE"), nullable=False, index=True)
    responsavel_id = Column(Integer, ForeignKey("responsaveis.id", ondelete="CASCADE"), nullable=False, index=True)
    telefone_destino = Column(String, nullable=False)
    mensagem = Column(Text, nullable=False)
    provider_message_id = Column(String, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    presenca = relationship("Presenca", back_populates="notificacoes")
    aluno = relationship("Aluno")
    responsavel = relationship("Responsavel")


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    aluno_id = Column(Integer, ForeignKey("alunos.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding = Column(JSON, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    aluno = relationship("Aluno", back_populates="face_embeddings")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    expira_em = Column(DateTime(timezone=True), nullable=False)
    revogado = Column(Boolean, default=False, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    usuario = relationship("Usuario", back_populates="refresh_tokens")

    @property
    def expirado(self) -> bool:
        expira_em = self.expira_em
        if expira_em.tzinfo is None:
            expira_em = expira_em.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expira_em

    @property
    def valido(self) -> bool:
        return not self.revogado and not self.expirado


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=True)
    audit_metadata = Column("metadata", JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    trace_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    actor = relationship("Usuario", foreign_keys=[actor_user_id])
