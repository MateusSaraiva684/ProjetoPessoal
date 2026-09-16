import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _processar_reconhecimento_impl(imagem: str) -> dict:
    logger.info("Tarefa de reconhecimento recebida para processamento futuro")
    return {"status": "pendente", "detalhe": "Worker de reconhecimento ainda nao conectado"}


if celery_app:
    processar_reconhecimento = celery_app.task(name="processar_reconhecimento")(
        _processar_reconhecimento_impl
    )
else:
    processar_reconhecimento = _processar_reconhecimento_impl
