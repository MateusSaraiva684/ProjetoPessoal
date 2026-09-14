import logging
import base64
import binascii
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, status
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.core.config import (
    JOB_FAILURE_TTL_SECONDS,
    JOB_RESULT_TTL_SECONDS,
    JOB_TIMEOUT_SECONDS,
    REDIS_URL,
)
from app.core.images import read_validated_image, validate_image_bytes
from app.core.security import require_api_key
from app.queue.worker import process_identification, process_recognition

logger = logging.getLogger(__name__)

router = APIRouter(tags=["recognition"], dependencies=[Depends(require_api_key)])
legacy_router = APIRouter(tags=["recognition"], dependencies=[Depends(require_api_key)])


def get_redis_connection() -> Redis:
    try:
        redis_conn = Redis.from_url(REDIS_URL, socket_connect_timeout=3, socket_timeout=3)
        redis_conn.ping()
        return redis_conn
    except RedisError as exc:
        logger.error("Erro ao conectar com Redis: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servico de fila indisponivel. Tente novamente.",
        ) from exc


def _decode_base64_image(value: str) -> bytes:
    if "," in value and value.lower().startswith("data:"):
        value = value.split(",", 1)[1]
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="base64_invalido") from exc


async def _read_image_from_request(
    request: Request,
    file: UploadFile | None = None,
    imagem: UploadFile | None = None,
) -> bytes:
    upload = file or imagem
    if upload is not None:
        return await read_validated_image(upload)

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON invalido") from exc
        image_base64 = body.get("imagem_base64") or body.get("base64") or body.get("image")
        if image_base64:
            return validate_image_bytes(_decode_base64_image(str(image_base64)))

    if content_type.startswith("image/"):
        return validate_image_bytes(await request.body(), content_type)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Imagem nao fornecida")


@router.post("/recognize")
async def recognize(
    file: UploadFile = File(...),
    trace_id: str | None = Header(None, alias="X-Trace-Id"),
) -> dict[str, Any]:
    try:
        image_bytes = await read_validated_image(file)
        logger.info("Arquivo recebido: %s (%s bytes) trace_id=%s", file.filename, len(image_bytes), trace_id)

        redis_conn = get_redis_connection()
        queue = Queue("recognition", connection=redis_conn)
        job = queue.enqueue(
            process_recognition,
            image_bytes,
            trace_id,
            job_timeout=JOB_TIMEOUT_SECONDS,
            result_ttl=JOB_RESULT_TTL_SECONDS,
            failure_ttl=JOB_FAILURE_TTL_SECONDS,
        )

        logger.info("Job enfileirado: %s", job.id)
        return {
            "status": "processing",
            "job_id": job.id,
            "message": "Reconhecimento facial em processamento",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Erro ao enfileirar reconhecimento: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar requisicao",
        ) from exc


@router.post("/recognize/sync")
async def recognize_sync(
    request: Request,
    file: UploadFile | None = File(None),
    imagem: UploadFile | None = File(None),
    trace_id: str | None = Header(None, alias="X-Trace-Id"),
) -> dict[str, Any]:
    image_bytes = await _read_image_from_request(request, file=file, imagem=imagem)
    logger.info("Reconhecimento sync recebido trace_id=%s", trace_id)
    return process_identification(image_bytes, trace_id=trace_id)


@legacy_router.post("/facial")
async def recognize_legacy_facial(
    request: Request,
    imagem: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
    trace_id: str | None = Header(None, alias="X-Trace-Id"),
) -> dict[str, Any]:
    image_bytes = await _read_image_from_request(request, file=file, imagem=imagem)
    return process_identification(image_bytes, trace_id=trace_id)


@router.get("/recognize/{job_id}")
async def get_recognition_status(job_id: str) -> dict[str, Any]:
    try:
        redis_conn = get_redis_connection()
        job = Job.fetch(job_id, connection=redis_conn)

        if job.is_finished:
            logger.info("Job finalizado: %s", job_id)
            return {
                "status": "completed",
                "job_id": job_id,
                "result": job.result,
            }

        if job.is_failed:
            logger.error("Job falhou: %s - %s", job_id, job.exc_info)
            return {
                "status": "failed",
                "job_id": job_id,
                "error": "Job falhou no processamento",
            }

        if job.is_started:
            return {
                "status": "processing",
                "job_id": job_id,
                "message": "Ainda processando...",
            }

        return {
            "status": "queued",
            "job_id": job_id,
            "message": "Aguardando processamento",
        }

    except NoSuchJobError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job nao encontrado",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Erro ao buscar status do job: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nao foi possivel consultar o job agora",
        ) from exc
