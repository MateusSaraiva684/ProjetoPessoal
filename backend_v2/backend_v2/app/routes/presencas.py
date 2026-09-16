import hashlib
import hmac
import json
import secrets
from typing import List

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequestError, ServiceUnavailableError, UnauthorizedError
from app.database.session import get_db
from app.models.models import Presenca, Usuario
from app.routes.auth import require_operator
from app.schemas.schemas import (
    PresencaCreate,
    PresencaManualCreate,
    PresencaReconhecimentoCreate,
    PresencaResponse,
    RecognitionPresenceWebhookCreate,
)
from app.services.presenca_service import PresencaService

router = APIRouter()
recognition_router = APIRouter()


def get_presenca_service(db: Session = Depends(get_db)) -> PresencaService:
    return PresencaService(db)


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _valid_hmac_signature(raw_body: bytes, provided_signature: str | None, secret: str) -> bool:
    if not provided_signature:
        return False

    algorithm, separator, digest = provided_signature.strip().partition("=")
    if algorithm.lower() != "sha256" or separator != "=" or not digest:
        return False

    expected_digest = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest.lower(), expected_digest)


async def require_recognition_webhook_secret(
    request: Request,
    authorization: str | None = Header(default=None),
    x_recognition_token: str | None = Header(default=None, alias="X-Recognition-Token"),
    x_recognition_signature: str | None = Header(default=None, alias="X-Recognition-Signature"),
) -> bytes:
    raw_body = await request.body()
    expected = settings.RECOGNITION_WEBHOOK_SECRET.strip()
    if not expected:
        if settings.is_production:
            raise ServiceUnavailableError("Webhook de reconhecimento nao configurado")
        return raw_body

    provided = _bearer_token(authorization) or (x_recognition_token or "").strip()
    if provided and secrets.compare_digest(provided, expected):
        return raw_body

    if _valid_hmac_signature(raw_body, x_recognition_signature, expected):
        return raw_body

    raise UnauthorizedError("Credenciais invalidas")


def _parse_reconhecimento_payload(
    raw_body: bytes,
) -> PresencaReconhecimentoCreate | RecognitionPresenceWebhookCreate:
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise BadRequestError("JSON invalido") from exc

    try:
        if isinstance(payload, dict) and (
            payload.get("event") == "presence_detected" or "event_id" in payload
        ):
            return RecognitionPresenceWebhookCreate.model_validate(payload)
        return PresencaReconhecimentoCreate.model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


def _registrar_reconhecimento_webhook(
    raw_body: bytes,
    idempotency_key: str | None,
    service: PresencaService,
) -> Presenca:
    body = _parse_reconhecimento_payload(raw_body)
    if isinstance(body, RecognitionPresenceWebhookCreate):
        if not idempotency_key or idempotency_key.strip() != body.event_id:
            raise BadRequestError("Idempotency-Key deve ser igual ao event_id")
        return service.registrar_evento_reconhecimento(body)

    return service.registrar_reconhecimento_recebido(body)


@router.post("", response_model=PresencaResponse, status_code=201)
async def registrar_reconhecimento(
    raw_body: bytes = Depends(require_recognition_webhook_secret),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    service: PresencaService = Depends(get_presenca_service),
):
    return _registrar_reconhecimento_webhook(raw_body, idempotency_key, service)


@recognition_router.post("/presences", response_model=PresencaResponse, status_code=201)
async def registrar_presence_recognition(
    raw_body: bytes = Depends(require_recognition_webhook_secret),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    service: PresencaService = Depends(get_presenca_service),
):
    return _registrar_reconhecimento_webhook(raw_body, idempotency_key, service)


@router.post("/manual", response_model=PresencaResponse, status_code=201)
def registrar_manual(
    body: PresencaManualCreate,
    user: Usuario = Depends(require_operator),
    service: PresencaService = Depends(get_presenca_service),
):
    return service.registrar_manual(body, user)


@router.post("/entrada", response_model=PresencaResponse, status_code=201)
def registrar_entrada(
    body: PresencaCreate,
    user: Usuario = Depends(require_operator),
    service: PresencaService = Depends(get_presenca_service),
):
    return service.registrar_entrada_saida(body, user, "entrada")


@router.post("/saida", response_model=PresencaResponse, status_code=201)
def registrar_saida(
    body: PresencaCreate,
    user: Usuario = Depends(require_operator),
    service: PresencaService = Depends(get_presenca_service),
):
    return service.registrar_entrada_saida(body, user, "saida")


@router.get("/aluno/{aluno_id}", response_model=List[PresencaResponse])
def listar_por_aluno(
    aluno_id: int,
    user: Usuario = Depends(require_operator),
    service: PresencaService = Depends(get_presenca_service),
):
    return service.listar_por_aluno(aluno_id, user)


def _report_filters(
    aluno_id: int | None = Query(None, gt=0),
    turma: str | None = Query(None, max_length=100),
    camera_id: str | None = Query(None, max_length=100),
    inicio: datetime | None = Query(None),
    fim: datetime | None = Query(None),
):
    if inicio and fim and inicio > fim:
        raise BadRequestError("inicio deve ser anterior ou igual a fim")
    return {
        "aluno_id": aluno_id,
        "turma": turma,
        "camera_id": camera_id,
        "inicio": inicio,
        "fim": fim,
    }


@router.get("", response_model=List[PresencaResponse])
def listar_relatorio(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    filtros: dict = Depends(_report_filters),
    user: Usuario = Depends(require_operator),
    service: PresencaService = Depends(get_presenca_service),
):
    registros, _ = service.listar_relatorio(user, skip=(page - 1) * limit, limit=limit, **filtros)
    return registros


@router.get("/export.csv")
def exportar_relatorio_csv(
    filtros: dict = Depends(_report_filters),
    user: Usuario = Depends(require_operator),
    service: PresencaService = Depends(get_presenca_service),
):
    registros, _ = service.listar_relatorio(user, skip=0, limit=10000, **filtros)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "aluno_id", "timestamp", "tipo_evento", "origem", "turno", "camera_id", "confianca", "status"])
    for item in registros:
        writer.writerow([
            item.id, item.aluno_id, item.timestamp.isoformat(), item.tipo_evento,
            item.origem, item.turno or "", item.camera_id or "",
            item.confianca if item.confianca is not None else "", item.status,
        ])
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=presencas.csv"},
    )
