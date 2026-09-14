import os
from urllib.parse import urlsplit, urlunsplit
from dotenv import load_dotenv

load_dotenv()


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "sim", "on")


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} deve ser um numero valido.") from exc
    if parsed <= 0:
        raise RuntimeError(f"{name} deve ser maior que zero.")
    return parsed


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} deve ser um numero inteiro valido.") from exc
    if parsed <= 0:
        raise RuntimeError(f"{name} deve ser maior que zero.")
    return parsed


def _derive_recognition_api_base_url(
    explicit_base_url: str | None = None,
    legacy_base_url: str | None = None,
    service_url: str | None = None,
) -> str:
    explicit_base_url = (
        explicit_base_url
        if explicit_base_url is not None
        else os.getenv("RECOGNITION_API_BASE_URL")
    )
    if explicit_base_url is not None:
        return explicit_base_url.rstrip("/")

    legacy_base_url = (
        legacy_base_url
        if legacy_base_url is not None
        else os.getenv("FACE_RECOGNITION_API_BASE_URL")
    )
    if legacy_base_url is not None:
        return legacy_base_url.rstrip("/")

    service_url = (
        service_url
        if service_url is not None
        else os.getenv("RECOGNITION_SERVICE_URL") or os.getenv("FACE_RECOGNITION_SERVICE_URL", "")
    ).rstrip("/")
    if not service_url:
        return ""

    parts = urlsplit(service_url)
    path_parts = [segment for segment in parts.path.split("/") if segment]
    if len(path_parts) <= 1:
        base_path = ""
    else:
        base_path = "/" + "/".join(path_parts[:-1])

    return urlunsplit((parts.scheme, parts.netloc, base_path, "", ""))


def _derive_face_recognition_service_url(
    explicit_url: str | None = None,
    service_base_url: str | None = None,
) -> str:
    explicit_url = (
        explicit_url
        if explicit_url is not None
        else os.getenv("FACE_RECOGNITION_SERVICE_URL")
    )
    if explicit_url:
        return explicit_url.rstrip("/")

    service_base_url = (
        service_base_url
        if service_base_url is not None
        else os.getenv("RECOGNITION_SERVICE_URL", "")
    ).rstrip("/")
    if not service_base_url:
        return ""

    if service_base_url.endswith("/api/recognize"):
        return f"{service_base_url}/sync"
    return f"{service_base_url}/api/recognize/sync"


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Credenciais do painel admin (definidas nas variáveis de ambiente)
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    ADMIN_SECRET_KEY: str = os.getenv("ADMIN_SECRET_KEY", "")  # mantida por compatibilidade

    # Cloudinary — armazenamento de fotos
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")

    RECOGNITION_SERVICE_URL: str = os.getenv("RECOGNITION_SERVICE_URL", "")
    FACE_RECOGNITION_SERVICE_URL: str = _derive_face_recognition_service_url()
    FACE_RECOGNITION_TIMEOUT_SECONDS: float = _env_float(
        "FACE_RECOGNITION_TIMEOUT_SECONDS", 10
    )
    RECOGNITION_API_BASE_URL: str = _derive_recognition_api_base_url()
    RECOGNITION_API_TIMEOUT_SECONDS: float = _env_float(
        "RECOGNITION_API_TIMEOUT_SECONDS",
        FACE_RECOGNITION_TIMEOUT_SECONDS,
    )
    RECOGNITION_API_TOKEN: str = os.getenv("RECOGNITION_API_TOKEN", "")
    RECOGNITION_WEBHOOK_SECRET: str = os.getenv("RECOGNITION_WEBHOOK_SECRET", "")
    MAX_IMAGE_UPLOAD_BYTES: int = _env_int("MAX_IMAGE_UPLOAD_BYTES", 5 * 1024 * 1024)
    NOTIFICATION_PROVIDER: str = os.getenv("NOTIFICATION_PROVIDER", "log").strip().lower()
    WHATSAPP_API_URL: str = os.getenv("WHATSAPP_API_URL", "")
    WHATSAPP_API_TOKEN: str = os.getenv("WHATSAPP_API_TOKEN", "")
    WHATSAPP_FROM_PHONE_ID: str = os.getenv("WHATSAPP_FROM_PHONE_ID", "")
    NOTIFICATION_MAX_ATTEMPTS: int = _env_int("NOTIFICATION_MAX_ATTEMPTS", 3)
    NOTIFICATION_RETRY_SECONDS: int = _env_int("NOTIFICATION_RETRY_SECONDS", 60)

    REDIS_URL: str = os.getenv("REDIS_URL", "")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "")
    TRUST_PROXY_HEADERS: bool = _env_flag("TRUST_PROXY_HEADERS", False)
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "").strip()
    SENTRY_TRACES_SAMPLE_RATE: float = _env_float("SENTRY_TRACES_SAMPLE_RATE", 0.0)
    LOGIN_MAX_FAILURES: int = _env_int("LOGIN_MAX_FAILURES", 5)
    LOGIN_LOCKOUT_MINUTES: int = _env_int("LOGIN_LOCKOUT_MINUTES", 15)
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", "./backups")
    BACKUP_RETENTION_DAYS: int = _env_int("BACKUP_RETENTION_DAYS", 30)
    BIOMETRIC_RETENTION_DAYS: int = _env_int("BIOMETRIC_RETENTION_DAYS", 365)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def sync_admin_password_on_startup(self) -> bool:
        return _env_flag("SYNC_ADMIN_PASSWORD_ON_STARTUP", not self.is_production)


settings = Settings()

if settings.ENVIRONMENT not in ("testing",):
    if not settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY não definida nas variáveis de ambiente.")
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL não definida nas variáveis de ambiente.")
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        raise RuntimeError("ADMIN_EMAIL e ADMIN_PASSWORD não definidos nas variáveis de ambiente.")
    if settings.is_production and len(settings.SECRET_KEY) < 32:
        raise RuntimeError("SECRET_KEY deve ter pelo menos 32 caracteres em production.")
    if settings.is_production and settings.RECOGNITION_WEBHOOK_SECRET and len(settings.RECOGNITION_WEBHOOK_SECRET) < 32:
        raise RuntimeError("RECOGNITION_WEBHOOK_SECRET deve ter pelo menos 32 caracteres em production.")
