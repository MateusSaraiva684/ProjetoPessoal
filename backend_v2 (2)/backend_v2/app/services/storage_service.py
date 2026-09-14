from dataclasses import dataclass

from fastapi import UploadFile

from app.services.media import deletar_foto_cloudinary, salvar_foto


@dataclass(frozen=True)
class StoredPhoto:
    url: str
    content: bytes
    filename: str
    content_type: str


class StorageService:
    def save_student_photo(self, foto: UploadFile | None) -> StoredPhoto | None:
        url = salvar_foto(foto)
        if not url or foto is None:
            return None

        content = foto.file.read()
        foto.file.seek(0)

        return StoredPhoto(
            url=url,
            content=content,
            filename=foto.filename or "foto.jpg",
            content_type=foto.content_type or "application/octet-stream",
        )

    def delete_photo(self, url: str | None) -> None:
        deletar_foto_cloudinary(url)
