import logging

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import AppError, BadRequestError, ServiceUnavailableError

logger = logging.getLogger(__name__)

EXTENSOES_PERMITIDAS = {"image/jpeg", "image/png", "image/webp"}
TAMANHO_MAXIMO = 5 * 1024 * 1024  # 5MB
_cloudinary_configured = False


def _get_cloudinary_uploader(raise_on_missing: bool = True):
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError as exc:
        logger.error("Cloudinary nao esta disponivel no ambiente atual")
        if raise_on_missing:
            raise ServiceUnavailableError(
                "Servico de imagens indisponivel. Tente novamente mais tarde."
            ) from exc
        return None

    global _cloudinary_configured
    if not _cloudinary_configured:
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )
        _cloudinary_configured = True

    return cloudinary.uploader


def salvar_foto(foto: UploadFile | None) -> str | None:
    """Faz upload da foto para o Cloudinary e retorna a URL segura."""
    if not foto or not foto.filename:
        return None
    if foto.content_type not in EXTENSOES_PERMITIDAS:
        raise BadRequestError("Tipo de arquivo nao permitido. Use JPEG, PNG ou WEBP.")

    conteudo = foto.file.read()
    if len(conteudo) > TAMANHO_MAXIMO:
        raise BadRequestError("Foto muito grande. Maximo 5MB.")
    
    # Reset file pointer para possível re-leitura
    foto.file.seek(0)

    uploader = _get_cloudinary_uploader()
    try:
        resultado = uploader.upload(
            conteudo,
            folder="sistema_escolar/alunos",
            resource_type="image",
            transformation=[{"width": 400, "height": 400, "crop": "fill", "gravity": "face"}],
        )
        return resultado["secure_url"]
    except Exception as exc:
        logger.error("Erro ao fazer upload para Cloudinary: %s", exc)
        raise AppError(500, "Erro ao salvar a foto. Tente novamente.") from exc


def deletar_foto_cloudinary(url: str | None):
    """Remove uma foto do Cloudinary quando o registro correspondente deixa de existir."""
    if not url or "cloudinary.com" not in url:
        return

    uploader = _get_cloudinary_uploader(raise_on_missing=False)
    if uploader is None:
        return

    try:
        partes = url.split("/upload/")
        if len(partes) == 2:
            public_id_com_ext = partes[1]
            if public_id_com_ext.startswith("v") and "/" in public_id_com_ext:
                public_id_com_ext = public_id_com_ext.split("/", 1)[1]
            public_id = public_id_com_ext.rsplit(".", 1)[0]
            uploader.destroy(public_id)
    except Exception as exc:
        logger.warning("Nao foi possivel deletar foto do Cloudinary: %s", exc)
