import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SYNC_ALUNO_ENDPOINT = "/api/students/sync"
ADD_STUDENT_FACE_ENDPOINT = "/api/students/faces"
DELETE_STUDENT_FACES_ENDPOINT = "/api/students/faces"
RETRYABLE_STATUS_CODES = {408, 425, 429}


@dataclass(frozen=True)
class IntegrationResult:
    success: bool
    retryable: bool = False
    status_code: int | None = None
    error: str | None = None
    message: str | None = None
    data: dict[str, Any] | None = None


class IntegrationService:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        api_token: str | None = None,
    ):
        configured_base_url = (
            base_url if base_url is not None else settings.RECOGNITION_API_BASE_URL
        )
        if settings.ENVIRONMENT == "testing" and base_url is None:
            configured_base_url = ""
        self.base_url = self._normalize_base_url(configured_base_url)
        self.timeout_seconds = self._normalize_timeout(timeout_seconds)
        self.api_token = (
            api_token
            if api_token is not None
            else settings.RECOGNITION_API_TOKEN
        ).strip()

    def sync_aluno(
        self,
        aluno: Any,
        photo_file: Any | None = None,
        trace_id: str | None = None,
    ) -> IntegrationResult:
        if not self.base_url:
            logger.debug("Sync de aluno ignorado: Recognition API nao configurada")
            return IntegrationResult(
                success=False,
                retryable=True,
                error="recognition_api_not_configured",
            )

        try:
            payload = self._build_aluno_form_data(aluno)
        except ValueError as exc:
            aluno_id = getattr(aluno, "id", "unknown")
            logger.error("Payload invalido para sync de aluno id=%s: %s", aluno_id, exc)
            return IntegrationResult(success=False, retryable=False, error="invalid_payload")

        try:
            with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
                response = client.post(
                    self._url(SYNC_ALUNO_ENDPOINT),
                    data=payload,
                    files=self._build_aluno_files(photo_file),
                    headers=self._headers(trace_id=trace_id),
                )
                response.raise_for_status()
                data = self._response_json(response)
        except httpx.TimeoutException:
            logger.warning(
                "Timeout ao sincronizar aluno id=%s com Recognition API",
                aluno.id,
            )
            return IntegrationResult(success=False, retryable=True, error="timeout")
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            retryable = self._is_retryable_status(status_code)
            log = logger.warning if retryable else logger.error
            log(
                "Falha ao sincronizar aluno id=%s com Recognition API: status=%s retryable=%s",
                aluno.id,
                status_code,
                retryable,
            )
            return IntegrationResult(
                success=False,
                retryable=retryable,
                status_code=status_code,
                error="http_status_error",
                message=self._response_message(exc.response),
                data=self._response_json(exc.response),
            )
        except httpx.HTTPError as exc:
            logger.error(
                "Erro HTTP ao sincronizar aluno id=%s com Recognition API: %s",
                aluno.id,
                exc.__class__.__name__,
            )
            return IntegrationResult(success=False, retryable=True, error="http_error")
        except Exception:
            logger.exception(
                "Erro inesperado ao sincronizar aluno id=%s com Recognition API",
                aluno.id,
            )
            return IntegrationResult(success=False, retryable=True, error="unexpected_error")

        logger.info("Aluno id=%s sincronizado com Recognition API trace_id=%s", aluno.id, trace_id)
        return IntegrationResult(
            success=True,
            status_code=getattr(response, "status_code", None),
            message=data.get("message") if data else None,
            data=data,
        )

    def add_aluno_face_sample(
        self,
        aluno: Any,
        photo_file: Any | None = None,
        trace_id: str | None = None,
    ) -> IntegrationResult:
        if not self.base_url:
            logger.debug("Adicao de amostra ignorada: Recognition API nao configurada")
            return IntegrationResult(
                success=False,
                retryable=True,
                error="recognition_api_not_configured",
            )

        try:
            payload = self._build_face_sample_form_data(aluno)
        except ValueError as exc:
            aluno_id = getattr(aluno, "id", "unknown")
            logger.error("Payload invalido para amostra do aluno id=%s: %s", aluno_id, exc)
            return IntegrationResult(success=False, retryable=False, error="invalid_payload")

        try:
            with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
                response = client.post(
                    self._url(ADD_STUDENT_FACE_ENDPOINT),
                    data=payload,
                    files=self._build_aluno_files(photo_file),
                    headers=self._headers(trace_id=trace_id),
                )
                response.raise_for_status()
                data = self._response_json(response)
        except httpx.TimeoutException:
            return IntegrationResult(success=False, retryable=True, error="timeout")
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            return IntegrationResult(
                success=False,
                retryable=self._is_retryable_status(status_code),
                status_code=status_code,
                error="http_status_error",
                message=self._response_message(exc.response),
                data=self._response_json(exc.response),
            )
        except httpx.HTTPError:
            return IntegrationResult(success=False, retryable=True, error="http_error")

        return IntegrationResult(
            success=True,
            status_code=getattr(response, "status_code", None),
            message=data.get("message") if data else None,
            data=data,
        )

    def delete_aluno_biometria(self, aluno: Any, trace_id: str | None = None) -> IntegrationResult:
        if not self.base_url:
            logger.debug("Exclusao biometrica ignorada: Recognition API nao configurada")
            return IntegrationResult(
                success=False,
                retryable=True,
                error="recognition_api_not_configured",
            )

        try:
            params = self._build_biometric_delete_params(aluno)
        except ValueError as exc:
            aluno_id = getattr(aluno, "id", "unknown")
            logger.error(
                "Parametros invalidos para exclusao biometrica do aluno id=%s: %s",
                aluno_id,
                exc,
            )
            return IntegrationResult(success=False, retryable=False, error="invalid_payload")

        try:
            with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
                response = client.delete(
                    self._url(DELETE_STUDENT_FACES_ENDPOINT),
                    params=params,
                    headers=self._headers(trace_id=trace_id),
                )
                response.raise_for_status()
                data = self._response_json(response)
        except httpx.TimeoutException:
            logger.warning(
                "Timeout ao excluir biometria do aluno id=%s na Recognition API",
                aluno.id,
            )
            return IntegrationResult(success=False, retryable=True, error="timeout")
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            retryable = self._is_retryable_status(status_code)
            log = logger.warning if retryable else logger.error
            log(
                "Falha ao excluir biometria do aluno id=%s na Recognition API: status=%s retryable=%s",
                aluno.id,
                status_code,
                retryable,
            )
            return IntegrationResult(
                success=False,
                retryable=retryable,
                status_code=status_code,
                error="http_status_error",
                message=self._response_message(exc.response),
                data=self._response_json(exc.response),
            )
        except httpx.HTTPError as exc:
            logger.error(
                "Erro HTTP ao excluir biometria do aluno id=%s na Recognition API: %s",
                aluno.id,
                exc.__class__.__name__,
            )
            return IntegrationResult(success=False, retryable=True, error="http_error")
        except Exception:
            logger.error(
                "Erro inesperado ao excluir biometria do aluno id=%s na Recognition API",
                aluno.id,
            )
            return IntegrationResult(success=False, retryable=True, error="unexpected_error")

        logger.info("Biometria do aluno id=%s excluida na Recognition API", aluno.id)
        return IntegrationResult(
            success=True,
            status_code=getattr(response, "status_code", None),
            message=data.get("message") if data else None,
            data=data,
        )

    def delete_aluno_face_sample(
        self,
        aluno: Any,
        face_sample_id: int,
        trace_id: str | None = None,
    ) -> IntegrationResult:
        if not self.base_url:
            return IntegrationResult(success=False, retryable=True, error="recognition_api_not_configured")

        try:
            params = self._build_biometric_delete_params(aluno)
        except ValueError:
            return IntegrationResult(success=False, retryable=False, error="invalid_payload")

        try:
            with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
                response = client.delete(
                    self._url(f"{DELETE_STUDENT_FACES_ENDPOINT}/{face_sample_id}"),
                    params=params,
                    headers=self._headers(trace_id=trace_id),
                )
                response.raise_for_status()
                data = self._response_json(response)
        except httpx.TimeoutException:
            return IntegrationResult(success=False, retryable=True, error="timeout")
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            return IntegrationResult(
                success=False,
                retryable=self._is_retryable_status(status_code),
                status_code=status_code,
                error="http_status_error",
                message=self._response_message(exc.response),
                data=self._response_json(exc.response),
            )
        except httpx.HTTPError:
            return IntegrationResult(success=False, retryable=True, error="http_error")

        return IntegrationResult(success=True, status_code=response.status_code, data=data)

    def health(self, trace_id: str | None = None) -> IntegrationResult:
        if not self.base_url:
            return IntegrationResult(success=False, retryable=True, error="recognition_api_not_configured")

        try:
            with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
                response = client.get(self._url("/api/health"), headers=self._headers(trace_id=trace_id))
                response.raise_for_status()
                data = self._response_json(response)
        except httpx.TimeoutException:
            return IntegrationResult(success=False, retryable=True, error="timeout")
        except httpx.HTTPStatusError as exc:
            return IntegrationResult(
                success=False,
                retryable=self._is_retryable_status(exc.response.status_code),
                status_code=exc.response.status_code,
                error="http_status_error",
                message=self._response_message(exc.response),
                data=self._response_json(exc.response),
            )
        except httpx.HTTPError:
            return IntegrationResult(success=False, retryable=True, error="http_error")

        return IntegrationResult(success=True, status_code=response.status_code, data=data)

    def _headers(self, trace_id: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "sistema-escolar-backend/2.0",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        if trace_id:
            headers["X-Trace-Id"] = trace_id
        return headers

    def _url(self, endpoint: str) -> str:
        if self.base_url.endswith("/api") and endpoint.startswith("/api/"):
            endpoint = endpoint[len("/api"):]
        return f"{self.base_url}{endpoint}"

    @staticmethod
    def _build_aluno_form_data(aluno: Any) -> dict[str, Any]:
        external_id = str(getattr(aluno, "external_id", "")).strip()
        nome = str(getattr(aluno, "nome", "")).strip()
        empresa_id = getattr(aluno, "empresa_id", None)

        if not external_id:
            raise ValueError("external_id ausente")
        if not nome:
            raise ValueError("nome ausente")
        if not isinstance(empresa_id, int) or empresa_id <= 0:
            raise ValueError("empresa_id invalido")

        school_id = f"escola_{empresa_id}"
        return {
            "school_id": school_id,
            "external_id": external_id,
            "name": nome,
            **({"photo_url": aluno.foto} if getattr(aluno, "foto", None) else {}),
        }

    @classmethod
    def _build_face_sample_form_data(cls, aluno: Any) -> dict[str, Any]:
        payload = cls._build_aluno_form_data(aluno)
        payload.pop("name", None)
        payload.pop("photo_url", None)
        return payload

    @staticmethod
    def _build_aluno_files(photo_file: Any | None) -> dict[str, Any] | None:
        if not photo_file:
            return None

        content = getattr(photo_file, "content", None)
        if not content:
            return None

        return {
            "file": (
                getattr(photo_file, "filename", None) or "foto.jpg",
                content,
                getattr(photo_file, "content_type", None) or "application/octet-stream",
            )
        }

    @staticmethod
    def _build_biometric_delete_params(aluno: Any) -> dict[str, Any]:
        external_id = str(getattr(aluno, "external_id", "")).strip()
        empresa_id = getattr(aluno, "empresa_id", None)

        if not external_id:
            raise ValueError("external_id ausente")
        if not isinstance(empresa_id, int) or empresa_id <= 0:
            raise ValueError("empresa_id invalido")

        school_id = f"escola_{empresa_id}"
        return {
            "school_id": school_id,
            "external_id": external_id,
            "confirm_external_id": external_id,
        }

    @staticmethod
    def _response_json(response: httpx.Response) -> dict[str, Any] | None:
        try:
            data = response.json()
        except (AttributeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    @classmethod
    def _response_message(cls, response: httpx.Response) -> str | None:
        data = cls._response_json(response)
        if not data:
            return None
        value = data.get("message") or data.get("detail") or data.get("error")
        return str(value) if value is not None else None

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code in RETRYABLE_STATUS_CODES or status_code >= 500

    @staticmethod
    def _normalize_timeout(timeout_seconds: float | None) -> float:
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.RECOGNITION_API_TIMEOUT_SECONDS
        )
        if timeout <= 0:
            raise ValueError("timeout_seconds deve ser maior que zero")
        return timeout

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        base_url = (base_url or "").strip().rstrip("/")
        if not base_url:
            return ""

        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("RECOGNITION_API_BASE_URL deve ser uma URL HTTP(S) valida")
        if parsed.username or parsed.password:
            raise ValueError("RECOGNITION_API_BASE_URL nao deve conter credenciais")
        if parsed.query or parsed.fragment:
            raise ValueError(
                "RECOGNITION_API_BASE_URL nao deve conter query string ou fragmento"
            )
        if settings.is_production and parsed.scheme != "https":
            raise ValueError("RECOGNITION_API_BASE_URL deve usar HTTPS em production")

        return base_url
