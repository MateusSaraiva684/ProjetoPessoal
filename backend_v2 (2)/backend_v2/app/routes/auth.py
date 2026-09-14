from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.database.session import get_db
from app.models.models import Usuario
from app.schemas.schemas import (
    LoginRequest,
    Mensagem,
    RefreshRequest,
    RegistrarRequest,
    TokenResponse,
    UsuarioResponse,
)
from app.services.auth_service import AuthService, TokenBundle
from app.services.audit_service import registrar_auditoria

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    auth_service: AuthService = Depends(get_auth_service),
) -> Usuario:
    if not credentials:
        raise UnauthorizedError("Token nao fornecido")
    return auth_service.get_current_user_from_token(credentials.credentials)


def require_roles(*roles: str):
    def dependency(user: Usuario = Depends(get_current_user)) -> Usuario:
        if user.role not in roles and not (user.is_superuser and "superadmin" in roles):
            raise UnauthorizedError("Permissao insuficiente")
        return user

    return dependency


require_admin = require_roles("superadmin", "gestor")
require_operator = require_roles("superadmin", "gestor", "operator")


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="none" if settings.is_production else "lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth",
    )


def _delete_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth",
        samesite="none" if settings.is_production else "lax",
        secure=settings.is_production,
    )


def _token_response(bundle: TokenBundle, response: Response) -> dict:
    _set_refresh_cookie(response, bundle.refresh_token)
    return {
        "access_token": bundle.access_token,
        "expires_in": bundle.expires_in,
        "usuario": bundle.usuario,
    }


@router.post("/registrar", response_model=Mensagem, status_code=201)
def registrar(
    body: RegistrarRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.registrar(body)
    return {"mensagem": "Conta criada com sucesso"}


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Autentica um usuário e retorna tokens de acesso e refresh.
    
    Rate limit: 5 tentativas por minuto por IP (implementado em middleware)
    """
    user = auth_service.autenticar(body)
    return _token_response(auth_service.emitir_tokens(user), response)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    cookie_token: Optional[str] = Cookie(default=None, alias="refresh_token"),
    body: Optional[RefreshRequest] = None,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Renova o access token usando refresh token.
    
    Aceita refresh token via:
    - Cookie: refresh_token
    - Body JSON: {"refresh_token": "..."}
    """
    token = cookie_token or (body.refresh_token if body else None)
    
    if not token:
        raise UnauthorizedError("Refresh token nao fornecido (cookie ou body)")
    
    return _token_response(auth_service.renovar(token), response)


@router.post("/logout", response_model=Mensagem)
def logout(
    response: Response,
    user: Usuario = Depends(get_current_user),
    cookie_token: Optional[str] = Cookie(default=None, alias="refresh_token"),
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.revogar_refresh_token(cookie_token)
    _delete_refresh_cookie(response)
    return {"mensagem": "Logout realizado com sucesso"}


@router.get("/me", response_model=UsuarioResponse)
def me(user: Usuario = Depends(get_current_user)):
    return user


@router.post("/mfa/setup")
def mfa_setup(
    user: Usuario = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    url = auth_service.iniciar_mfa(user)
    registrar_auditoria(
        auth_service.db,
        actor_user_id=user.id,
        action="mfa_setup",
        resource_type="usuario",
        resource_id=user.id,
        metadata={"result": "pending_confirmation"},
    )
    auth_service.db.commit()
    return {"otpauth_url": url}


@router.post("/mfa/confirm")
def mfa_confirm(
    body: dict,
    user: Usuario = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    auth_service.confirmar_mfa(user, str(body.get("code", "")))
    registrar_auditoria(
        auth_service.db,
        actor_user_id=user.id,
        action="mfa_enabled",
        resource_type="usuario",
        resource_id=user.id,
        metadata={"result": "success"},
    )
    auth_service.db.commit()
    return {"mensagem": "MFA ativado com sucesso"}
