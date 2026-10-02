from dataclasses import dataclass
import asyncio

import httpx

from app.core.config import settings
from app.core.exceptions import AppError, BadRequestError, ServiceUnavailableError


@dataclass(frozen=True)
class FaceImagePayload:
    content: bytes | None = None
    filename: str | None = None
    content_type: str | None = None
    base64_image: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class FaceRecognitionResult:
    aluno_id: int | None
    confianca: float
    external_id: str | None = None
    school_id: str | None = None
    status: str = "success"
    candidates: list[dict] | None = None


class FaceRecognitionService:
    def _headers(self, trace_id: str | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        token = settings.RECOGNITION_API_TOKEN.strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if trace_id:
            headers["X-Trace-Id"] = trace_id
        return headers

    async def reconhecer(self, payload: FaceImagePayload) -> FaceRecognitionResult:
        service_urls = self._recognition_urls()
        if not service_urls:
            raise ServiceUnavailableError("Servico de reconhecimento facial nao configurado")
        if not payload.content and not payload.base64_image:
            raise BadRequestError("Imagem nao fornecida")

        try:
            async with httpx.AsyncClient(
                timeout=settings.FACE_RECOGNITION_TIMEOUT_SECONDS,
                trust_env=False,
            ) as client:
                last_index = len(service_urls) - 1
                for index, service_url in enumerate(service_urls):
                    try:
                        if payload.content:
                            files = {
                                "file": (
                                    payload.filename or "imagem.jpg",
                                    payload.content,
                                    payload.content_type or "application/octet-stream",
                                )
                            }
                            response = await client.post(
                                service_url,
                                files=files,
                                headers=self._headers(payload.trace_id),
                            )
                        else:
                            response = await client.post(
                                service_url,
                                json={"imagem_base64": payload.base64_image},
                                headers=self._headers(payload.trace_id),
                            )
                        response.raise_for_status()
                        data = await self._read_recognition_response(
                            client,
                            response,
                            service_url,
                            trace_id=payload.trace_id,
                        )
                        break
                    except httpx.HTTPStatusError as exc:
                        if index < last_index and exc.response.status_code in {404, 405}:
                            continue
                        raise
        except httpx.TimeoutException as exc:
            raise AppError(504, "Servico de reconhecimento facial demorou para responder") from exc
        except httpx.HTTPStatusError as exc:
            raise AppError(
                502,
                f"Servico de reconhecimento facial retornou erro {exc.response.status_code}",
            ) from exc
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError("Falha ao chamar servico de reconhecimento facial") from exc

        return self._parse_result(data)

    async def _read_recognition_response(
        self,
        client: httpx.AsyncClient,
        response: httpx.Response,
        service_url: str,
        trace_id: str | None = None,
    ) -> dict:
        try:
            data = response.json()
        except ValueError as exc:
            raise AppError(502, "Resposta invalida do servico de reconhecimento facial") from exc

        if data.get("status") == "processing" and data.get("job_id"):
            return await self._poll_job_result(
                client,
                str(data["job_id"]),
                service_url,
                trace_id=trace_id,
            )
        if data.get("status") == "completed" and isinstance(data.get("result"), dict):
            return data["result"]
        return data

    async def _poll_job_result(
        self,
        client: httpx.AsyncClient,
        job_id: str,
        service_url: str,
        trace_id: str | None = None,
    ) -> dict:
        status_url = f"{self._async_recognition_url(service_url)}/{job_id}"
        attempts = max(1, int(settings.FACE_RECOGNITION_TIMEOUT_SECONDS))
        for _ in range(attempts):
            response = await client.get(status_url, headers=self._headers(trace_id))
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "completed" and isinstance(data.get("result"), dict):
                return data["result"]
            if data.get("status") == "failed":
                raise AppError(502, "Servico de reconhecimento facial falhou no processamento")
            await asyncio.sleep(1)

        raise AppError(504, "Servico de reconhecimento facial demorou para responder")

    def _recognition_urls(self) -> list[str]:
        configured_url = settings.FACE_RECOGNITION_SERVICE_URL.strip().rstrip("/")
        service_base_url = settings.RECOGNITION_SERVICE_URL.strip().rstrip("/")
        candidates: list[str] = []

        if configured_url:
            candidates.append(self._sync_recognition_url(configured_url))
            candidates.append(configured_url)
        if service_base_url:
            candidates.append(self._sync_recognition_url(service_base_url))
            candidates.append(self._async_recognition_url(service_base_url))

        urls: list[str] = []
        for url in candidates:
            if url and url not in urls:
                urls.append(url)
        return urls

    @staticmethod
    def _sync_recognition_url(url: str) -> str:
        url = url.rstrip("/")
        if url.endswith("/api/recognize"):
            return f"{url}/sync"
        if url.endswith("/api/recognize/sync"):
            return url
        if not url.endswith("/sync") and not url.endswith("/facial"):
            return f"{url}/api/recognize/sync"
        return url

    @staticmethod
    def _async_recognition_url(url: str) -> str:
        url = url.rstrip("/")
        if url.endswith("/api/recognize/sync"):
            return url[: -len("/sync")]
        if url.endswith("/sync") and not url.endswith("/api/recognize/sync"):
            return url[: -len("/sync")]
        if url.endswith("/api/recognize"):
            return url
        return f"{url}/api/recognize"

    def _parse_result(self, data: dict) -> FaceRecognitionResult:
        status = data.get("status")
        if status in {None, "success"}:
            try:
                confianca = float(data.get("confianca", data.get("confidence")))
                if not 0 <= confianca <= 1:
                    raise ValueError("confianca fora da faixa esperada")

                external_id = str(data.get("student_id") or data.get("external_id") or "").strip()
                if not external_id:
                    raise ValueError("external_id ausente")
                return FaceRecognitionResult(
                    aluno_id=None,
                    confianca=confianca,
                    external_id=external_id,
                    school_id=str(data.get("school_id")).strip() if data.get("school_id") else None,
                    status=str(status or "success"),
                    candidates=data.get("candidates") if isinstance(data.get("candidates"), list) else None,
                )
            except (TypeError, ValueError) as exc:
                raise AppError(502, "Resposta invalida do servico de reconhecimento facial") from exc

        if status == "no_match":
            raise AppError(404, "Nenhum aluno reconhecido na imagem")
        if status == "ambiguous_match":
            raise AppError(409, "Reconhecimento facial ambiguo; revise cadastros duplicados")
        if status == "duplicate":
            raise AppError(409, "Presenca ja registrada recentemente")
        if status == "error":
            raise AppError(422, data.get("error") or "Erro no reconhecimento facial")

        raise AppError(502, "Resposta invalida do servico de reconhecimento facial")
