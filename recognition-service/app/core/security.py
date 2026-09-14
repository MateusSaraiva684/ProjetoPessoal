import hmac
import logging
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import API_KEYS

logger = logging.getLogger(__name__)


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    return token.strip()


async def require_api_key(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """
    Protects internal SaaS endpoints.

    Accepts Authorization: Bearer <key> or X-API-Key: <key>.
    """
    if not API_KEYS:
        logger.error("RECOGNITION_API_KEYS nao configurada; recusando endpoint protegido")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servico de reconhecimento sem credenciais configuradas",
        )

    provided_key = x_api_key or _extract_bearer_token(authorization)
    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial ausente",
        )

    for valid_key in API_KEYS:
        if hmac.compare_digest(provided_key, valid_key):
            return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credencial invalida",
    )
