import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import CAMERA_ID, CORS_ORIGINS, REDIS_URL, SAAS_PRESENCE_WEBHOOK_URL, SCHOOL_ID
from app.core.database import check_database_connection
from app.routes import diagnostics, operations, recognize, register
from app.services.face_service import is_model_loaded

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Recognition Service",
    description="Servico interno de reconhecimento facial com API REST",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Trace-Id"],
)


@app.middleware("http")
async def error_handler_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.error("Erro nao tratado: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Erro interno do servidor"},
        )


def _check_redis_connection() -> None:
    redis_conn = Redis.from_url(REDIS_URL, socket_connect_timeout=3, socket_timeout=3)
    redis_conn.ping()


def _build_health_response():
    database_status = "online"
    redis_status = "online"
    queue_status = "unknown"
    http_status = status.HTTP_200_OK

    try:
        _check_redis_connection()
        queue_status = "online"
    except RedisError as exc:
        logger.error("Healthcheck Redis falhou: %s", exc)
        redis_status = "error"
        queue_status = "error"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    try:
        check_database_connection()
    except Exception as exc:
        logger.error("Healthcheck database falhou: %s", exc)
        database_status = "error"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=http_status,
        content={
            "status": "online" if http_status == status.HTTP_200_OK else "error",
            "database": database_status,
            "redis": redis_status,
            "model_loaded": is_model_loaded(),
            "worker_required": True,
            "queue": queue_status,
            "school_id": SCHOOL_ID,
            "camera_id": CAMERA_ID,
            "webhook_configured": bool(SAAS_PRESENCE_WEBHOOK_URL),
        },
    )


@app.get("/health", tags=["health"])
async def health_check():
    return _build_health_response()


@app.get("/api/health", tags=["health"])
async def api_health_check():
    return _build_health_response()


app.include_router(register.router, prefix="/api")
app.include_router(register.legacy_router)
app.include_router(recognize.router, prefix="/api")
app.include_router(recognize.legacy_router)
app.include_router(operations.router, prefix="/api")
app.include_router(diagnostics.router, prefix="/api")

logger.info("Recognition Service iniciado")
