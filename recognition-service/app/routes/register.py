import logging

from fastapi import APIRouter, Body, Depends, File, Form, Header, HTTPException, UploadFile, status

from app.core.config import SCHOOL_ID, USE_GPU
from app.core.database import get_connection
from app.core.images import download_validated_image, read_validated_image
from app.core.security import require_api_key
from app.services.face_service import get_embedding

logger = logging.getLogger(__name__)

router = APIRouter(tags=["registration"], dependencies=[Depends(require_api_key)])
legacy_router = APIRouter(tags=["registration"], dependencies=[Depends(require_api_key)])


def _normalize_required(value: str | None, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} obrigatorio",
        )
    return normalized


def _biometric_error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=code)


def _normalize_image_error(exc: HTTPException) -> HTTPException:
    detail = str(exc.detail or "").upper()
    if detail in {"NO_FACE_DETECTED", "MULTIPLE_FACES_DETECTED", "INVALID_IMAGE", "LOW_QUALITY_IMAGE"}:
        return exc
    if "GRANDE" in detail:
        return _biometric_error(exc.status_code, "INVALID_IMAGE")
    if "MIME" in detail or "ARQUIVO" in detail or "IMAGEM" in detail or "PHOTO_URL" in detail:
        return _biometric_error(exc.status_code, "INVALID_IMAGE")
    return _biometric_error(exc.status_code, "INVALID_IMAGE")


def _upsert_student(
    *,
    school_id: str,
    external_id: str | None,
    nome: str,
    vector_str: str | None,
) -> tuple[int, str, bool, int]:
    conn = get_connection()

    try:
        with conn:
            with conn.cursor() as cur:
                if external_id is None:
                    if vector_str is None:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="file_required",
                        )

                    cur.execute("SELECT nextval(pg_get_serial_sequence('alunos', 'id'))")
                    aluno_id = cur.fetchone()[0]
                    external_id = str(aluno_id)
                    cur.execute(
                        """
                        INSERT INTO alunos (id, school_id, external_id, nome, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (aluno_id, school_id, external_id, nome, vector_str),
                    )
                    aluno_id = cur.fetchone()[0]
                    _insert_face_sample(cur, aluno_id=aluno_id, vector_str=vector_str)
                    return aluno_id, external_id, True, _count_face_samples(cur, aluno_id)

                if vector_str is None:
                    cur.execute(
                        """
                        UPDATE alunos
                        SET nome = %s
                        WHERE school_id = %s AND external_id = %s
                        RETURNING id
                        """,
                        (nome, school_id, external_id),
                    )
                    result = cur.fetchone()
                    if not result:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="file_required",
                        )
                    aluno_id = result[0]
                    return aluno_id, external_id, False, _count_face_samples(cur, aluno_id)

                cur.execute(
                    """
                    INSERT INTO alunos (school_id, external_id, nome, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (school_id, external_id)
                    DO UPDATE SET
                        nome = EXCLUDED.nome,
                        embedding = EXCLUDED.embedding
                    RETURNING id, (xmax = 0) AS inserted
                    """,
                    (school_id, external_id, nome, vector_str),
                )
                aluno_id, inserted = cur.fetchone()
                _insert_face_sample(cur, aluno_id=aluno_id, vector_str=vector_str)
                return aluno_id, external_id, bool(inserted), _count_face_samples(cur, aluno_id)
    finally:
        conn.close()


def _insert_face_sample(cur, *, aluno_id: int, vector_str: str) -> int:
    cur.execute(
        """
        INSERT INTO embeddings (aluno_id, embedding)
        VALUES (%s, %s)
        RETURNING id
        """,
        (aluno_id, vector_str),
    )
    return cur.fetchone()[0]


def _count_face_samples(cur, aluno_id: int) -> int:
    cur.execute("SELECT COUNT(*) FROM embeddings WHERE aluno_id = %s", (aluno_id,))
    return cur.fetchone()[0]


def _add_face_sample(*, school_id: str, external_id: str, vector_str: str) -> tuple[int, int, int]:
    conn = get_connection()

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE alunos
                    SET embedding = %s
                    WHERE school_id = %s AND external_id = %s
                    RETURNING id
                    """,
                    (vector_str, school_id, external_id),
                )
                result = cur.fetchone()
                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="student_not_found",
                    )

                aluno_id = result[0]
                sample_id = _insert_face_sample(cur, aluno_id=aluno_id, vector_str=vector_str)
                return aluno_id, sample_id, _count_face_samples(cur, aluno_id)
    finally:
        conn.close()


def _build_embedding_from_bytes(image_bytes: bytes) -> str:
    try:
        embedding = get_embedding(image_bytes, use_gpu=USE_GPU)
    except ValueError as exc:
        detail = str(exc).upper()
        if "MULTIPLE" in detail:
            code = "MULTIPLE_FACES_DETECTED"
        elif "LOW_QUALITY" in detail or "BORR" in detail:
            code = "LOW_QUALITY_IMAGE"
        elif "NO_FACE" in detail or "ROSTO" in detail:
            code = "NO_FACE_DETECTED"
        else:
            code = "INVALID_IMAGE"
        raise _biometric_error(status.HTTP_400_BAD_REQUEST, code) from exc
    except RuntimeError as exc:
        raise _biometric_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "MODEL_ERROR") from exc

    if embedding is None:
        raise _biometric_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "NO_FACE_DETECTED")

    return "[" + ",".join(map(str, embedding.tolist())) + "]"


async def _build_embedding_from_upload(file: UploadFile) -> str:
    try:
        image_bytes = await read_validated_image(file)
    except HTTPException as exc:
        raise _normalize_image_error(exc) from exc
    return _build_embedding_from_bytes(image_bytes)


def _build_embedding_from_photo_url(photo_url: str) -> str:
    try:
        image_bytes = download_validated_image(photo_url)
    except HTTPException as exc:
        raise _normalize_image_error(exc) from exc
    return _build_embedding_from_bytes(image_bytes)


def _database_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    logger.exception("Erro de banco no cadastro biometrico")
    return _biometric_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "DATABASE_ERROR")


def _school_id_from_legacy_payload(payload: dict) -> str:
    school_id = payload.get("school_id")
    if school_id:
        return _normalize_required(str(school_id), "school_id")

    empresa_id = payload.get("empresa_id")
    if isinstance(empresa_id, int) and empresa_id > 0:
        return f"escola_{empresa_id}"
    if isinstance(empresa_id, str) and empresa_id.strip().isdigit() and int(empresa_id) > 0:
        return f"escola_{int(empresa_id)}"

    return _normalize_required(SCHOOL_ID, "school_id")


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    nome: str = Form(...),
    file: UploadFile = File(...),
    school_id: str | None = Form(None),
    external_id: str | None = Form(None),
    trace_id: str | None = Header(None, alias="X-Trace-Id"),
):
    normalized_name = _normalize_required(nome, "Nome")
    normalized_school_id = _normalize_required(school_id or SCHOOL_ID, "school_id")
    normalized_external_id = external_id.strip() if external_id and external_id.strip() else None
    vector_str = await _build_embedding_from_upload(file)

    try:
        aluno_id, saved_external_id, inserted, face_samples_count = _upsert_student(
            school_id=normalized_school_id,
            external_id=normalized_external_id,
            nome=normalized_name,
            vector_str=vector_str,
        )
    except Exception as exc:
        raise _database_error(exc) from exc

    logger.info("Aluno registrado no recognition-service: %s trace_id=%s", aluno_id, trace_id)
    return {
        "status": "ready",
        "aluno_id": aluno_id,
        "school_id": normalized_school_id,
        "external_id": saved_external_id,
        "created": inserted,
        "face_samples_count": face_samples_count,
    }


@router.post("/students/sync", status_code=status.HTTP_200_OK)
async def sync_student(
    school_id: str = Form(...),
    external_id: str = Form(...),
    name: str = Form(...),
    file: UploadFile | None = File(None),
    photo_url: str | None = Form(None),
    trace_id: str | None = Header(None, alias="X-Trace-Id"),
):
    normalized_school_id = _normalize_required(school_id, "school_id")
    normalized_external_id = _normalize_required(external_id, "external_id")
    normalized_name = _normalize_required(name, "name")

    vector_str = None
    if file is not None:
        vector_str = await _build_embedding_from_upload(file)
    elif photo_url:
        vector_str = _build_embedding_from_photo_url(photo_url)

    try:
        aluno_id, saved_external_id, inserted, face_samples_count = _upsert_student(
            school_id=normalized_school_id,
            external_id=normalized_external_id,
            nome=normalized_name,
            vector_str=vector_str,
        )
    except Exception as exc:
        raise _database_error(exc) from exc
    logger.info(
        "Aluno sincronizado school_id=%s external_id=%s trace_id=%s",
        normalized_school_id,
        normalized_external_id,
        trace_id,
    )

    return {
        "status": "ready",
        "aluno_id": aluno_id,
        "school_id": normalized_school_id,
        "external_id": saved_external_id,
        "created": inserted,
        "face_samples_count": face_samples_count,
    }


@legacy_router.post("/sync/aluno", status_code=status.HTTP_200_OK)
async def sync_legacy_aluno(payload: dict = Body(...)):
    normalized_school_id = _school_id_from_legacy_payload(payload)
    normalized_external_id = _normalize_required(str(payload.get("external_id") or ""), "external_id")
    normalized_name = _normalize_required(str(payload.get("nome") or payload.get("name") or ""), "nome")
    photo_url = str(payload.get("photo_url") or payload.get("foto") or "").strip()

    vector_str = _build_embedding_from_photo_url(photo_url) if photo_url else None
    try:
        aluno_id, saved_external_id, inserted, face_samples_count = _upsert_student(
            school_id=normalized_school_id,
            external_id=normalized_external_id,
            nome=normalized_name,
            vector_str=vector_str,
        )
    except Exception as exc:
        raise _database_error(exc) from exc

    return {
        "status": "ready",
        "aluno_id": aluno_id,
        "school_id": normalized_school_id,
        "external_id": saved_external_id,
        "created": inserted,
        "face_samples_count": face_samples_count,
    }


@router.post("/students/faces", status_code=status.HTTP_201_CREATED)
async def add_student_face_sample(
    school_id: str = Form(...),
    external_id: str = Form(...),
    file: UploadFile = File(...),
    trace_id: str | None = Header(None, alias="X-Trace-Id"),
):
    normalized_school_id = _normalize_required(school_id, "school_id")
    normalized_external_id = _normalize_required(external_id, "external_id")
    vector_str = await _build_embedding_from_upload(file)

    try:
        aluno_id, sample_id, face_samples_count = _add_face_sample(
            school_id=normalized_school_id,
            external_id=normalized_external_id,
            vector_str=vector_str,
        )
    except Exception as exc:
        raise _database_error(exc) from exc

    logger.info(
        "Amostra facial adicionada: aluno_id=%s sample_id=%s total=%s trace_id=%s",
        aluno_id,
        sample_id,
        face_samples_count,
        trace_id,
    )

    return {
        "status": "ready",
        "aluno_id": aluno_id,
        "school_id": normalized_school_id,
        "external_id": normalized_external_id,
        "face_sample_id": sample_id,
        "face_samples_count": face_samples_count,
    }
