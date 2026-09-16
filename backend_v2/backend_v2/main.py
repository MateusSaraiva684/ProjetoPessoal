import os
import logging
try:
    import sentry_sdk
except ImportError:  # Sentry é opcional em ambientes locais.
    sentry_sdk = None
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging_config import configurar_logging
from app.middleware.logging import request_logging_middleware
from app.middleware.rate_limit import rate_limit_middleware
from app.routes import admin, alunos, auth, notificacoes, presencas, reconhecimento
from app.database.session import SessionLocal
from app.tasks.celery_app import celery_app

configurar_logging()
logger = logging.getLogger(__name__)

if settings.SENTRY_DSN and sentry_sdk:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
    )


@asynccontextmanager
async def lifespan(application: FastAPI):
    startup()
    yield


app = FastAPI(
    title="Sistema Escolar API",
    version=settings.APP_VERSION,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

origins = [settings.FRONTEND_URL] if settings.FRONTEND_URL else []
if not settings.is_production:
    origins.extend(["http://localhost:5173", "http://localhost:3000"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(request_logging_middleware)
app.middleware("http")(rate_limit_middleware)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(alunos.router, prefix="/api/alunos", tags=["Alunos"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(presencas.router, prefix="/api/presencas", tags=["Presencas"])
app.include_router(notificacoes.router, prefix="/api/notificacoes", tags=["Notificacoes"])
app.include_router(presencas.recognition_router, prefix="/api/recognition", tags=["Recognition"])
app.include_router(reconhecimento.router, prefix="/api/reconhecimento", tags=["Reconhecimento"])

os.makedirs("uploads/alunos", exist_ok=True)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"erro": exc.detail})


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"erro": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    erros = [f"{' -> '.join(str(l) for l in e['loc'])}: {e['msg']}" for e in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"erro": "Dados invalidos", "detalhe": erros},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    if sentry_sdk:
        sentry_sdk.capture_exception(exc)
    logger.exception("Erro inesperado em %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"erro": "Erro interno do servidor"})


def startup():
    """Inicializa a aplicacao e sincroniza o admin automaticamente."""
    logger.info("Aplicacao iniciada - ambiente: %s", settings.ENVIRONMENT)
    
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        raise RuntimeError("ADMIN_EMAIL e ADMIN_PASSWORD sao obrigatorios para iniciar o backend.")

    from sqlalchemy.orm import Session as DBSession
    from app.database.session import SessionLocal
    from app.models.models import Usuario as UsuarioModel
    from app.core.security import hash_senha, verificar_senha

    db: DBSession = SessionLocal()
    try:
        admin_user = db.query(UsuarioModel).filter(
            UsuarioModel.email == settings.ADMIN_EMAIL
        ).first()

        if not admin_user:
            logger.info("Criando novo usuario admin: %s", settings.ADMIN_EMAIL)
            admin_user = UsuarioModel(
                nome="Administrador",
                email=settings.ADMIN_EMAIL,
                senha=hash_senha(settings.ADMIN_PASSWORD),
                is_superuser=True,
                role="superadmin",
                ativo=True,
            )
            db.add(admin_user)
            db.flush()
            db.commit()
            logger.info("Admin criado com sucesso: %s", settings.ADMIN_EMAIL)

        else:
            logger.info("Sincronizando admin existente: %s", settings.ADMIN_EMAIL)
            
            mudou = False
            
            if not admin_user.is_superuser:
                logger.debug("Elevando permissoes para superuser")
                admin_user.is_superuser = True
                mudou = True
            if admin_user.role != "superadmin":
                admin_user.role = "superadmin"
                mudou = True

            if not admin_user.ativo:
                logger.debug("Reativando administrador configurado")
                admin_user.ativo = True
                mudou = True
            
            senha_sincronizada = verificar_senha(settings.ADMIN_PASSWORD, admin_user.senha)
            if not senha_sincronizada:
                if settings.sync_admin_password_on_startup:
                    logger.debug("Sincronizando senha com .env")
                    admin_user.senha = hash_senha(settings.ADMIN_PASSWORD)
                    mudou = True
                else:
                    logger.warning(
                        "Senha do admin difere de ADMIN_PASSWORD; sincronizacao automatica desabilitada"
                    )
            
            if mudou:
                db.flush()
                db.commit()
                logger.info("Admin sincronizado: %s", settings.ADMIN_EMAIL)
            else:
                logger.debug("Admin ja estava sincronizado")

    except Exception as exc:
        logger.error("Erro ao sincronizar admin: %s", str(exc), exc_info=True)
        raise
    finally:
        db.close()


@app.get("/api/health")
def health():
    checks = {"database": "ok", "redis": "ok", "worker": "ok"}
    http_status = status.HTTP_200_OK
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Healthcheck do banco falhou")
        checks["database"] = "error"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    finally:
        db.close()

    if not settings.REDIS_URL:
        checks["redis"] = "not_configured"
        if settings.is_production:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        redis = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        try:
            redis.ping()
        except RedisError:
            logger.exception("Healthcheck do Redis falhou")
            checks["redis"] = "error"
            if settings.is_production:
                http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        finally:
            redis.close()

    if celery_app is None:
        checks["worker"] = "not_configured"
        if settings.is_production:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        try:
            workers = celery_app.control.inspect(timeout=1).ping() or {}
            if not workers:
                checks["worker"] = "unavailable"
                if settings.is_production:
                    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        except Exception:
            logger.exception("Healthcheck do worker falhou")
            checks["worker"] = "error"
            if settings.is_production:
                http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ok" if http_status == status.HTTP_200_OK else "error",
            "version": settings.APP_VERSION,
            "commit": settings.GIT_COMMIT,
            **checks,
        },
    )


def _frontend_url_for_request(path: str, query: str = "") -> str | None:
    if not settings.FRONTEND_URL:
        return None

    frontend_url = settings.FRONTEND_URL.rstrip("/")
    parts = urlsplit(frontend_url)
    frontend_path = "/" + path.lstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, frontend_path, query, ""))


@app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def frontend_route_fallback(full_path: str, request: Request):
    if full_path == "api" or full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"erro": "Not Found"})

    redirect_url = _frontend_url_for_request(full_path, request.url.query)
    if redirect_url:
        return RedirectResponse(redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    return JSONResponse(status_code=404, content={"erro": "Not Found"})
