from pathlib import PurePath
from urllib.parse import urlsplit

from fastapi import HTTPException, UploadFile, status
import requests

from app.core.config import APP_ENV, MAX_FILE_SIZE_BYTES, PHOTO_URL_ALLOWED_HOSTS, PHOTO_URL_TIMEOUT_SECONDS

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/jpg"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _has_valid_signature(image_bytes: bytes) -> bool:
    return (
        image_bytes.startswith(b"\xff\xd8\xff")
        or image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    )


def _is_allowed_photo_host(hostname: str | None) -> bool:
    if not hostname:
        return False

    normalized = hostname.lower().rstrip(".")
    for allowed_host in PHOTO_URL_ALLOWED_HOSTS:
        allowed = allowed_host.lower().rstrip(".")
        if normalized == allowed or normalized.endswith(f".{allowed}"):
            return True
    return False


def validate_image_bytes(image_bytes: bytes, content_type: str | None = None) -> bytes:
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio")

    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        max_size_mb = MAX_FILE_SIZE_BYTES / 1024 / 1024
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo muito grande (max: {max_size_mb:.0f}MB)",
        )

    if content_type:
        content_type = content_type.split(";")[0].strip().lower()
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo MIME invalido. Use: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
            )

    if not _has_valid_signature(image_bytes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo nao parece ser uma imagem JPEG/PNG valida",
        )

    return image_bytes


async def read_validated_image(file: UploadFile) -> bytes:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome do arquivo invalido")

    file_ext = PurePath(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo invalido. Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo MIME invalido. Use: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )

    return validate_image_bytes(await file.read(), file.content_type)


def download_validated_image(photo_url: str) -> bytes:
    parsed = urlsplit(photo_url.strip())
    allowed_scheme = parsed.scheme == "https" or (
        APP_ENV != "production"
        and parsed.scheme == "http"
        and _is_allowed_photo_host(parsed.hostname)
    )
    if not allowed_scheme or not _is_allowed_photo_host(parsed.hostname):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="photo_url nao permitido",
        )

    try:
        response = requests.get(
            photo_url,
            timeout=PHOTO_URL_TIMEOUT_SECONDS,
            allow_redirects=False,
            headers={"User-Agent": "recognition-service/1.0"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="photo_url_download_failed",
        ) from exc

    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_FILE_SIZE_BYTES:
        max_size_mb = MAX_FILE_SIZE_BYTES / 1024 / 1024
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo muito grande (max: {max_size_mb:.0f}MB)",
        )

    return validate_image_bytes(response.content, response.headers.get("Content-Type"))
