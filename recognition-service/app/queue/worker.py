import logging
from datetime import datetime, timezone
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import (
    CAMERA_ID,
    MATCH_AMBIGUITY_MARGIN,
    PRESENCE_DEDUP_WINDOW_SECONDS,
    REDIS_URL,
    SCHOOL_ID,
    SIMILARITY_THRESHOLD,
    USE_GPU,
)
from app.core.database import get_connection
from app.services.audit import record_recognition_event
from app.services.face_service import get_embedding
from app.services.saas_webhook import send_presence_event

logger = logging.getLogger(__name__)

# MVP: o reconhecimento em tempo real filtra pelo SCHOOL_ID da instancia/camera.
# Em SaaS multi-escola real, o school_id deve vir da camera ou da requisicao de
# reconhecimento para evitar misturar escolas dentro da mesma instancia.

def _match_candidate(row) -> dict[str, Any]:
    aluno_id, school_id, external_id, nome, face_sample_id, distance = row
    return {
        "aluno_id": aluno_id,
        "school_id": school_id,
        "student_id": external_id,
        "nome": nome,
        "face_sample_id": face_sample_id,
        "distance": float(distance),
    }


def _find_ambiguous_candidate(best_match, candidates):
    best_distance = float(best_match[5])
    best_identity = (best_match[1], best_match[2])

    for candidate in candidates[1:]:
        candidate_identity = (candidate[1], candidate[2])
        if candidate_identity == best_identity:
            continue

        candidate_distance = float(candidate[5])
        if candidate_distance <= best_distance + MATCH_AMBIGUITY_MARGIN:
            return candidate

    return None


def _dedup_key(*, school_id: str, camera_id: str, external_id: str) -> str:
    return f"presence:dedup:{school_id}:{camera_id}:{external_id}"


def _claim_presence_dedup(*, school_id: str, camera_id: str, external_id: str) -> bool:
    if PRESENCE_DEDUP_WINDOW_SECONDS <= 0:
        return True

    redis_conn = Redis.from_url(REDIS_URL, socket_connect_timeout=3, socket_timeout=3)
    key = _dedup_key(school_id=school_id, camera_id=camera_id, external_id=external_id)

    try:
        claimed = redis_conn.set(
            key,
            datetime.now(timezone.utc).isoformat(),
            nx=True,
            ex=PRESENCE_DEDUP_WINDOW_SECONDS,
        )
        return bool(claimed)
    except RedisError:
        logger.error("Falha ao aplicar deduplicacao de presenca no Redis", exc_info=True)
        raise


def _trace_metadata(trace_id: str | None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    data = dict(metadata or {})
    if trace_id:
        data["trace_id"] = trace_id
    return data


def process_identification(image_bytes: bytes, trace_id: str | None = None) -> dict[str, Any]:
    """
    Identifica a face de forma sincrona sem criar presenca e sem enviar webhook.
    Usado pelo SaaS quando ele proprio vai decidir o que fazer com o match.
    """
    embedding = get_embedding(image_bytes, use_gpu=USE_GPU)
    if embedding is None:
        record_recognition_event(
            status="error",
            school_id=SCHOOL_ID,
            camera_id=CAMERA_ID,
            metadata=_trace_metadata(trace_id, {"error": "no_face_detected", "mode": "identify_only"}),
        )
        return {"status": "error", "error": "no_face_detected"}

    vector_str = "[" + ",".join(map(str, embedding.tolist())) + "]"
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        a.id,
                        a.school_id,
                        a.external_id,
                        a.nome,
                        e.id AS face_sample_id,
                        e.embedding <-> %s::vector AS distance
                    FROM embeddings e
                    JOIN alunos a ON a.id = e.aluno_id
                    WHERE a.school_id = %s
                      AND a.archived_at IS NULL
                    ORDER BY distance
                    LIMIT 5;
                    """,
                    (vector_str, SCHOOL_ID),
                )
                candidates = cur.fetchall()

                if not candidates:
                    record_recognition_event(
                        status="no_match",
                        school_id=SCHOOL_ID,
                        camera_id=CAMERA_ID,
                        metadata=_trace_metadata(trace_id, {"mode": "identify_only"}),
                        cur=cur,
                    )
                    return {"status": "no_match"}

                result = candidates[0]
                aluno_id, school_id, external_id, nome, face_sample_id, distance = result
                if distance >= SIMILARITY_THRESHOLD:
                    record_recognition_event(
                        status="no_match",
                        school_id=school_id,
                        camera_id=CAMERA_ID,
                        aluno_id=aluno_id,
                        external_id=external_id,
                        face_sample_id=face_sample_id,
                        distance=float(distance),
                        candidates=[_match_candidate(candidate) for candidate in candidates],
                        metadata=_trace_metadata(trace_id, {"threshold": SIMILARITY_THRESHOLD, "mode": "identify_only"}),
                        cur=cur,
                    )
                    return {
                        "status": "no_match",
                        "best_distance": float(distance),
                        "threshold": SIMILARITY_THRESHOLD,
                    }

                ambiguous_candidate = _find_ambiguous_candidate(result, candidates)
                if ambiguous_candidate is not None:
                    ambiguous_candidates = [
                        _match_candidate(candidate)
                        for candidate in candidates
                        if float(candidate[5]) <= float(distance) + MATCH_AMBIGUITY_MARGIN
                    ]
                    record_recognition_event(
                        status="ambiguous_match",
                        school_id=school_id,
                        camera_id=CAMERA_ID,
                        aluno_id=aluno_id,
                        external_id=external_id,
                        face_sample_id=face_sample_id,
                        distance=float(distance),
                        candidates=ambiguous_candidates,
                        metadata=_trace_metadata(trace_id, {"ambiguity_margin": MATCH_AMBIGUITY_MARGIN, "mode": "identify_only"}),
                        cur=cur,
                    )
                    return {
                        "status": "ambiguous_match",
                        "student_id": external_id,
                        "school_id": school_id,
                        "camera_id": CAMERA_ID,
                        "message": "Reconhecimento ambiguo; revise cadastros duplicados",
                        "candidates": ambiguous_candidates,
                    }

                confidence = float(max(0, 1 - distance))
                record_recognition_event(
                    status="success",
                    school_id=school_id,
                    camera_id=CAMERA_ID,
                    aluno_id=aluno_id,
                    external_id=external_id,
                    face_sample_id=face_sample_id,
                    confidence=confidence,
                    distance=float(distance),
                    metadata=_trace_metadata(trace_id, {"mode": "identify_only"}),
                    cur=cur,
                )
                response: dict[str, Any] = {
                    "status": "success",
                    "aluno_id": aluno_id,
                    "school_id": school_id,
                    "student_id": external_id,
                    "external_id": external_id,
                    "face_sample_id": face_sample_id,
                    "nome": nome,
                    "confidence": confidence,
                    "confianca": confidence,
                    "distance": float(distance),
                }
                if external_id.isdigit():
                    response["saas_aluno_id"] = int(external_id)
                return response
    finally:
        conn.close()


def process_recognition(image_bytes: bytes, trace_id: str | None = None) -> dict[str, Any]:
    """
    Processa reconhecimento facial usando pgvector.

    Erros inesperados sao levantados para o RQ marcar o job como failed.
    """
    logger.info("Iniciando reconhecimento facial trace_id=%s", trace_id)

    embedding = get_embedding(image_bytes, use_gpu=USE_GPU)
    if embedding is None:
        logger.warning("Nenhum rosto detectado")
        record_recognition_event(
            status="error",
            school_id=SCHOOL_ID,
            camera_id=CAMERA_ID,
            metadata=_trace_metadata(trace_id, {"error": "no_face_detected"}),
        )
        return {
            "status": "error",
            "error": "no_face_detected",
        }

    logger.info("Embedding gerado, consultando banco")

    vector_str = "[" + ",".join(map(str, embedding.tolist())) + "]"
    conn = get_connection()

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        a.id,
                        a.school_id,
                        a.external_id,
                        a.nome,
                        e.id AS face_sample_id,
                        e.embedding <-> %s::vector AS distance
                    FROM embeddings e
                    JOIN alunos a ON a.id = e.aluno_id
                    WHERE a.school_id = %s
                      AND a.archived_at IS NULL
                    ORDER BY distance
                    LIMIT 5;
                    """,
                    (vector_str, SCHOOL_ID),
                )
                candidates = cur.fetchall()

                if not candidates:
                    record_recognition_event(
                        status="no_match",
                        school_id=SCHOOL_ID,
                        camera_id=CAMERA_ID,
                        cur=cur,
                    )
                    return {"status": "no_match"}

                result = candidates[0]
                aluno_id, school_id, external_id, nome, face_sample_id, distance = result
                logger.info("Melhor match: %s (distancia: %s)", nome, distance)

                if distance >= SIMILARITY_THRESHOLD:
                    record_recognition_event(
                        status="no_match",
                        school_id=school_id,
                        camera_id=CAMERA_ID,
                        aluno_id=aluno_id,
                        external_id=external_id,
                        face_sample_id=face_sample_id,
                        distance=float(distance),
                        candidates=[_match_candidate(candidate) for candidate in candidates],
                        metadata=_trace_metadata(trace_id, {"threshold": SIMILARITY_THRESHOLD}),
                        cur=cur,
                    )
                    return {
                        "status": "no_match",
                        "best_distance": float(distance),
                        "threshold": SIMILARITY_THRESHOLD,
                    }

                ambiguous_candidate = _find_ambiguous_candidate(result, candidates)
                if ambiguous_candidate is not None:
                    ambiguous_candidates = [
                        _match_candidate(candidate)
                        for candidate in candidates
                        if float(candidate[5]) <= float(distance) + MATCH_AMBIGUITY_MARGIN
                    ]
                    logger.warning(
                        "Reconhecimento ambiguo: best=%s candidate=%s margin=%s",
                        _match_candidate(result),
                        _match_candidate(ambiguous_candidate),
                        MATCH_AMBIGUITY_MARGIN,
                    )
                    record_recognition_event(
                        status="ambiguous_match",
                        school_id=school_id,
                        camera_id=CAMERA_ID,
                        aluno_id=aluno_id,
                        external_id=external_id,
                        face_sample_id=face_sample_id,
                        distance=float(distance),
                        candidates=ambiguous_candidates,
                        metadata=_trace_metadata(trace_id, {"ambiguity_margin": MATCH_AMBIGUITY_MARGIN}),
                        cur=cur,
                    )
                    return {
                        "status": "ambiguous_match",
                        "student_id": external_id,
                        "school_id": school_id,
                        "camera_id": CAMERA_ID,
                        "message": "Reconhecimento ambiguo; revise cadastros duplicados",
                        "candidates": ambiguous_candidates,
                    }

                if not _claim_presence_dedup(
                    school_id=school_id,
                    camera_id=CAMERA_ID,
                    external_id=external_id,
                ):
                    logger.info(
                        "Presenca duplicada ignorada: school_id=%s camera_id=%s external_id=%s",
                        school_id,
                        CAMERA_ID,
                        external_id,
                    )
                    record_recognition_event(
                        status="duplicate",
                        school_id=school_id,
                        camera_id=CAMERA_ID,
                        aluno_id=aluno_id,
                        external_id=external_id,
                        face_sample_id=face_sample_id,
                        distance=float(distance),
                        cur=cur,
                    )
                    return {
                        "status": "duplicate",
                        "student_id": external_id,
                        "school_id": school_id,
                        "camera_id": CAMERA_ID,
                        "message": "Presenca ja registrada recentemente",
                    }

                cur.execute(
                    """
                    INSERT INTO presencas (aluno_id, school_id, external_id, camera_id, nome)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, created_at
                    """,
                    (aluno_id, school_id, external_id, CAMERA_ID, nome),
                )
                presenca_id, detected_at = cur.fetchone()

        logger.info("Presenca registrada: %s (%s)", nome, presenca_id)
        confidence = float(max(0, 1 - distance))
        webhook_result = send_presence_event(
            presence_id=presenca_id,
            school_id=school_id,
            student_id=external_id,
            student_name=nome,
            confidence=confidence,
            detected_at=detected_at,
            tipo_evento="entrada",
            trace_id=trace_id,
        )
        webhook_sent = bool(webhook_result)
        webhook_error = getattr(webhook_result, "error", None)
        webhook_event_id = getattr(webhook_result, "event_id", None)
        record_recognition_event(
            status="success",
            school_id=school_id,
            camera_id=CAMERA_ID,
            aluno_id=aluno_id,
            external_id=external_id,
            face_sample_id=face_sample_id,
            confidence=confidence,
            distance=float(distance),
            presence_id=presenca_id,
            webhook_sent=webhook_sent,
            webhook_error=webhook_error,
            metadata=_trace_metadata(trace_id, {"webhook_event_id": webhook_event_id}),
        )

        return {
            "status": "success",
            "aluno_id": aluno_id,
            "school_id": school_id,
            "student_id": external_id,
            "face_sample_id": face_sample_id,
            "nome": nome,
            "confidence": confidence,
            "presenca_id": presenca_id,
            "saas_webhook_sent": webhook_sent,
            "message": f"{nome} entrou na escola",
        }

    except Exception as exc:
        record_recognition_event(
            status="error",
            school_id=SCHOOL_ID,
            camera_id=CAMERA_ID,
            metadata=_trace_metadata(trace_id, {"error": exc.__class__.__name__}),
        )
        logger.error("Erro no reconhecimento", exc_info=True)
        raise
    finally:
        conn.close()
