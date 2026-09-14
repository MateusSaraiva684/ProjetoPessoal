import logging
import base64
import hashlib
import hmac
import secrets
import struct
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jose import JWTError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequestError, UnauthorizedError
from app.core.security import (
    criar_access_token,
    criar_refresh_token,
    decodificar_access_token,
    hash_senha,
    verificar_senha,
)
from app.models.models import RefreshToken, Usuario
from app.repositories.usuario_repository import RefreshTokenRepository, UsuarioRepository
from app.schemas.schemas import LoginRequest, RegistrarRequest

logger = logging.getLogger(__name__)


def _totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _totp_valid(secret: str, code: str) -> bool:
    if not code.isdigit() or len(code) != 6:
        return False
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    counter = int(time.time()) // 30
    for offset in (-1, 0, 1):
        digest = hmac.new(key, struct.pack(">Q", counter + offset), hashlib.sha1).digest()
        index = digest[-1] & 0x0F
        value = (struct.unpack(">I", digest[index:index + 4])[0] & 0x7FFFFFFF) % 1000000
        if hmac.compare_digest(f"{value:06d}", code):
            return True
    return False


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str
    expires_in: int
    usuario: Usuario


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.usuarios = UsuarioRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)

    def registrar(self, body: RegistrarRequest) -> None:
        if self.usuarios.get_by_email(body.email):
            raise BadRequestError("E-mail já cadastrado")
        if len(body.senha) < 6:
            raise BadRequestError("Senha deve ter no minimo 6 caracteres")

        usuario = Usuario(nome=body.nome, email=body.email, senha=hash_senha(body.senha))
        try:
            self.usuarios.add(usuario)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise BadRequestError("E-mail já cadastrado") from exc
        logger.info("Novo usuario registrado: %s", body.email)

    def autenticar(self, body: LoginRequest) -> Usuario:
        user = self.usuarios.get_by_email(body.email, ativo=True)

        if user and user.locked_until:
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > datetime.now(timezone.utc):
                raise UnauthorizedError("Conta temporariamente bloqueada")
            user.locked_until = None
            user.failed_login_attempts = 0
            self.db.commit()

        if user:
            if not verificar_senha(body.senha, user.senha):
                self._register_failed_login(user)
                raise UnauthorizedError("E-mail ou senha incorretos")
            if user.mfa_enabled:
                if not body.mfa_code or not user.mfa_secret or not _totp_valid(user.mfa_secret, body.mfa_code):
                    raise UnauthorizedError("Código MFA inválido ou ausente")
            user.failed_login_attempts = 0
            user.locked_until = None
            self.db.commit()
            logger.info("Login realizado: %s", body.email)
            return user

        # Usuário não existe - permitir fallback apenas para admin
        if body.email == settings.ADMIN_EMAIL and body.senha == settings.ADMIN_PASSWORD:
            user = Usuario(
                nome="Administrador",
                email=settings.ADMIN_EMAIL,
                senha=hash_senha(settings.ADMIN_PASSWORD),
                is_superuser=True,
                ativo=True,
            )
            try:
                self.usuarios.add(user)
                self.db.commit()
                self.db.refresh(user)
                logger.info("Admin criado automaticamente: %s", body.email)
                return user
            except Exception as e:
                self.db.rollback()
                logger.error("Erro ao criar admin: %s", str(e))
                raise UnauthorizedError("Erro ao processar login") from e

        raise UnauthorizedError("E-mail ou senha incorretos")

    def iniciar_mfa(self, user: Usuario) -> str:
        secret = _totp_secret()
        user.mfa_secret = secret
        user.mfa_enabled = False
        self.db.commit()
        return f"otpauth://totp/SaaS%20Escolar:{user.email}?secret={secret}&issuer=SaaS%20Escolar"

    def confirmar_mfa(self, user: Usuario, code: str) -> None:
        if not user.mfa_secret or not _totp_valid(user.mfa_secret, code):
            raise BadRequestError("Código MFA inválido")
        user.mfa_enabled = True
        self.db.commit()

    def _register_failed_login(self, user: Usuario) -> None:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.LOGIN_MAX_FAILURES:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
            logger.warning("Conta bloqueada após falhas de login: user_id=%d", user.id)
        self.db.commit()

    def emitir_tokens(self, user: Usuario) -> TokenBundle:
        access_token = criar_access_token(user.id)
        refresh_token = criar_refresh_token()
        self.refresh_tokens.add(self._novo_refresh_token(refresh_token, user.id))
        self.db.commit()
        return TokenBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            usuario=user,
        )

    def renovar(self, token: str | None) -> TokenBundle:
        if not token:
            raise UnauthorizedError("Refresh token nao fornecido")

        rt = self.refresh_tokens.get_by_token(token)
        if not rt or not rt.valido:
            raise UnauthorizedError("Refresh token invalido ou expirado")

        user = rt.usuario
        if not user.ativo:
            raise UnauthorizedError("Usuario inativo")

        access_token = criar_access_token(user.id)
        refresh_token = criar_refresh_token()
        rt.revogado = True
        self.refresh_tokens.add(self._novo_refresh_token(refresh_token, user.id))
        self.db.commit()

        logger.info("Token renovado para usuario id=%d", user.id)
        return TokenBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            usuario=user,
        )

    def revogar_refresh_token(self, token: str | None) -> None:
        if not token:
            return
        rt = self.refresh_tokens.get_by_token(token)
        if rt:
            rt.revogado = True
            self.db.commit()

    def get_current_user_from_token(self, token: str) -> Usuario:
        try:
            payload = decodificar_access_token(token)
            user_id = int(payload["sub"])
        except (JWTError, KeyError, ValueError) as exc:
            raise UnauthorizedError("Token invalido ou expirado") from exc

        user = self.usuarios.get_by_id(user_id, ativo=True)
        if not user:
            raise UnauthorizedError("Usuario nao encontrado")
        return user

    def _novo_refresh_token(self, token: str, user_id: int) -> RefreshToken:
        return RefreshToken(
            token=token,
            user_id=user_id,
            expira_em=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
