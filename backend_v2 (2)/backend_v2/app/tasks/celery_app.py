from app.core.config import settings

try:
    from celery import Celery
except ImportError:
    if settings.is_production:
        raise RuntimeError("Celery e obrigatorio em production.") from None
    celery_app = None
else:
    broker_url = settings.CELERY_BROKER_URL or settings.REDIS_URL
    result_backend = settings.CELERY_RESULT_BACKEND or settings.REDIS_URL
    if settings.is_production and not broker_url:
        raise RuntimeError("CELERY_BROKER_URL ou REDIS_URL e obrigatorio em production.")
    celery_app = Celery(
        "sistema_escolar",
        broker=broker_url or "memory://",
        backend=result_backend or broker_url or "cache+memory://",
        include=["app.tasks.notificacoes", "app.tasks.reconhecimento"],
    )
    celery_app.conf.update(
        task_default_queue="default",
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        broker_connection_retry_on_startup=True,
    )
