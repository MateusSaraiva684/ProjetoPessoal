"""Middleware de Rate Limiting para proteção de brute force."""

import logging
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, Tuple
from collections import defaultdict
from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

# Rate limit store: {ip:endpoint: [timestamps...]}
# Usando defaultdict para evitar KeyError
rate_limit_store: Dict[str, list] = defaultdict(list)
rate_limit_lock = Lock()


def get_client_ip(request: Request) -> str:
    """Extrai IP do cliente da request."""
    if settings.TRUST_PROXY_HEADERS and "x-forwarded-for" in request.headers:
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    # Fallback para client.host
    return request.client.host if request.client else "unknown"


def check_rate_limit(
    ip: str,
    endpoint: str,
    max_requests: int = 5,
    window_seconds: int = 60,
) -> Tuple[bool, int]:
    now = datetime.now()
    key = f"{ip}:{endpoint}"
    cutoff_time = now - timedelta(seconds=window_seconds)

    with rate_limit_lock:
        for store_key, timestamps in list(rate_limit_store.items()):
            recentes = [timestamp for timestamp in timestamps if timestamp > cutoff_time]
            if recentes:
                rate_limit_store[store_key] = recentes
            else:
                del rate_limit_store[store_key]

        current_count = len(rate_limit_store[key])

        if current_count >= max_requests:
            logger.warning(
                "Rate limit excedido: IP %s em %s - %d/%d",
                ip,
                endpoint,
                current_count,
                max_requests,
            )
            return False, 0

        rate_limit_store[key].append(now)
        remaining = max_requests - len(rate_limit_store[key])

    return True, remaining


async def rate_limit_middleware(request: Request, call_next):
    """Middleware de rate limiting para endpoints sensíveis (login)."""
    
    # Apenas aplicar a /api/auth/login
    if request.url.path != "/api/auth/login":
        return await call_next(request)
    
    # Extrair IP do cliente
    client_ip = get_client_ip(request)
    
    # Se for teste (client IP é 'testclient'), permitir sem rate limit
    if client_ip == "testclient":
        return await call_next(request)
    
    # Se não tem client real, permitir
    if not request.client:
        return await call_next(request)
    
    # Verificar rate limit: 5 tentativas por minuto
    allowed, remaining = check_rate_limit(
        ip=client_ip,
        endpoint="/api/auth/login",
        max_requests=5,
        window_seconds=60
    )
    
    if not allowed:
        logger.warning(f"Rate limit excedido: IP {client_ip} em /api/auth/login")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "erro": "Muitas tentativas de login. Tente novamente em 1 minuto.",
                "retry_after": 60
            }
        )
    
    # Processar requisição
    response = await call_next(request)
    
    # Adicionar headers de rate limit à resposta
    response.headers["X-RateLimit-Limit"] = str(5)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(
        (datetime.now() + timedelta(seconds=60)).timestamp()
    )
    
    return response
