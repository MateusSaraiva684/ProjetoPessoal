from app.core.config import settings

try:
    from celery import Celery
except ImportError:
    celery_app = None
else:
    broker_url = settings.CELERY_BROKER_URL or settings.REDIS_URL
    result_backend = settings.CELERY_RESULT_BACKEND or settings.REDIS_URL
    celery_app = Celery(
        "sistema_escolar",
        broker=broker_url or "memory://",
        backend=result_backend or "cache+memory://",
    )
