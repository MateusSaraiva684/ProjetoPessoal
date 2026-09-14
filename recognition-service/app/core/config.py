import logging
import os

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _get_csv(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _get_int(name: str, default: str) -> int:
    raw_value = os.getenv(name, default).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} deve ser um inteiro valido") from exc

    if value < 0:
        raise ValueError(f"{name} nao pode ser negativo")

    return value


# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# App Settings
APP_ENV = os.getenv("APP_ENV", "development").lower()
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
GIT_COMMIT = os.getenv("GIT_COMMIT", "unknown")

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://recognition-redis:6379")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL nao configurada. Configure a variavel de ambiente.")

DB_CONNECT_TIMEOUT_SECONDS = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5"))

# Recognition Settings
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))
MATCH_AMBIGUITY_MARGIN = float(os.getenv("MATCH_AMBIGUITY_MARGIN", "0.02"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
PHOTO_URL_TIMEOUT_SECONDS = float(os.getenv("PHOTO_URL_TIMEOUT_SECONDS", "8"))
PHOTO_URL_ALLOWED_HOSTS = _get_csv("PHOTO_URL_ALLOWED_HOSTS", "res.cloudinary.com")
JOB_TIMEOUT_SECONDS = int(os.getenv("JOB_TIMEOUT_SECONDS", "60"))
JOB_RESULT_TTL_SECONDS = int(os.getenv("JOB_RESULT_TTL_SECONDS", "3600"))
JOB_FAILURE_TTL_SECONDS = int(os.getenv("JOB_FAILURE_TTL_SECONDS", "86400"))
WEBHOOK_MAX_ATTEMPTS = _get_int("WEBHOOK_MAX_ATTEMPTS", "5")
WEBHOOK_RETRY_SECONDS = _get_int("WEBHOOK_RETRY_SECONDS", "60")
BIOMETRIC_RETENTION_DAYS = _get_int("BIOMETRIC_RETENTION_DAYS", "365")

# Face Recognition Settings
USE_GPU = _get_bool("USE_GPU", "false")

# Security Settings
API_KEYS = _get_csv("RECOGNITION_API_KEYS")
CORS_ORIGINS = _get_csv(
    "CORS_ORIGINS",
    "" if APP_ENV == "production" else "http://localhost:3000,http://localhost:5173",
)

# SaaS Webhook Settings
SAAS_PRESENCE_WEBHOOK_URL = (
    os.getenv("SAAS_PRESENCE_WEBHOOK_URL") or os.getenv("SAAS_WEBHOOK_URL", "")
).strip()
SAAS_WEBHOOK_SECRET = (
    os.getenv("SAAS_WEBHOOK_SECRET") or os.getenv("RECOGNITION_WEBHOOK_SECRET", "")
).strip()
SAAS_WEBHOOK_TIMEOUT_SECONDS = float(os.getenv("SAAS_WEBHOOK_TIMEOUT_SECONDS", "5"))
SCHOOL_ID = os.getenv("SCHOOL_ID", "escola_1").strip() or "escola_1"
CAMERA_ID = os.getenv("CAMERA_ID", "entrada_principal").strip() or "entrada_principal"
PRESENCE_DEDUP_WINDOW_SECONDS = _get_int("PRESENCE_DEDUP_WINDOW_SECONDS", "300")
