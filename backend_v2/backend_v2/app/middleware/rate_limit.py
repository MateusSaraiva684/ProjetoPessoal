"""Middleware de Rate Limiting para proteção de brute force."""

import hashlib
import logging
from datetime import datetime, timedelta, timezone

from fastapi import Request, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

def get_client_ip(request: Request) -> str:
    """Extrai IP do cliente da request."""
    if settings.TRUST_PROXY_HEADERS and "x-forwarded-for" in request.headers:
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    # Fallback para client.host
    return request.client.host if request.client else "unknown"


async def check_rate_limit(
    ip: str,
    endpoint: str,
    max_requests: int = 5,
    window_seconds: int = 60,
) -> tuple[bool, int, int]:
    if not settings.REDIS_URL:
        raise RedisError("REDIS_URL nao configurada")

    digest = hashlib.sha256(f"{ip}:{endpoint}".encode("utf-8")).hexdigest()
    key = f"rate-limit:{digest}"
    redis = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        ttl = await redis.ttl(key)
        return count <= max_requests, max(0, max_requests - count), max(ttl, 1)
    finally:
        await redis.aclose()


async def rate_limit_middleware(request: Request, call_next):
    """Middleware de rate limiting para endpoints sensíveis (login)."""
    
    # Apenas aplicar a /api/auth/login
    if request.url.path != "/api/auth/login":
        return await call_next(request)
    
    # Extrair IP do cliente
    client_ip = get_client_ip(request)
    
    if not request.client:
        return await call_next(request)

    try:
        allowed, remaining, retry_after = await check_rate_limit(
            ip=client_ip,
            endpoint="/api/auth/login",
            max_requests=settings.LOGIN_MAX_FAILURES,
            window_seconds=settings.LOGIN_LOCKOUT_MINUTES * 60,
        )
    except RedisError:
        logger.exception("Rate limit indisponivel; Redis e obrigatorio para login distribuido")
        if settings.is_production:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"erro": "Servico de autenticacao temporariamente indisponivel."},
            )
        return await call_next(request)
    
    if not allowed:
        logger.warning("Rate limit excedido: IP %s em /api/auth/login", client_ip)
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "erro": "Muitas tentativas de login. Tente novamente mais tarde.",
                "retry_after": retry_after,
            }
        )
    
    # Processar requisição
    response = await call_next(request)
    
    # Adicionar headers de rate limit à resposta
    response.headers["X-RateLimit-Limit"] = str(settings.LOGIN_MAX_FAILURES)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(
        int((datetime.now(timezone.utc) + timedelta(seconds=retry_after)).timestamp())
    )
    
    return response
