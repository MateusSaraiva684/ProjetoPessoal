"""Live E2E harness for backend_v2 + recognition-service coupling.

This script intentionally exercises deployed/running HTTP services. It does not
start containers, run migrations, create users, or bypass authentication.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER_VALUES = {
    "seu_admin@email.com",
    "sua_senha_admin",
    "email_da_escola_teste@email.com",
    "senha_da_escola_teste",
    "mesmo_secret_do_backend_e_recognition",
    "mesmo_token_aceito_pelo_recognition",
}
REQUIRED_ENV_MESSAGES = {
    "BACKEND_URL": "Variável BACKEND_URL não foi preenchida. Informe a URL do backend SaaS no .env.e2e.",
    "RECOGNITION_SERVICE_URL": "Variável RECOGNITION_SERVICE_URL não foi preenchida. Informe a URL do recognition-service no .env.e2e.",
    "ADMIN_EMAIL": "Variável ADMIN_EMAIL ainda não foi preenchida. Informe o login de um admin existente no .env.e2e.",
    "ADMIN_PASSWORD": "Variável ADMIN_PASSWORD ainda não foi preenchida. Informe a senha do admin existente no .env.e2e.",
    "TEST_SCHOOL_EMAIL": "Variável TEST_SCHOOL_EMAIL ainda não foi preenchida. Crie uma escola/usuário de teste no sistema e informe o login no .env.e2e.",
    "TEST_SCHOOL_PASSWORD": "Variável TEST_SCHOOL_PASSWORD ainda não foi preenchida. Informe a senha da escola/usuário de teste no .env.e2e.",
    "RECOGNITION_WEBHOOK_SECRET": "Variável RECOGNITION_WEBHOOK_SECRET ainda não foi preenchida. Use o mesmo secret configurado no backend e no recognition-service.",
    "RECOGNITION_API_TOKEN": "Variável RECOGNITION_API_TOKEN ainda não foi preenchida. Use um token aceito por RECOGNITION_API_KEYS no recognition-service.",
}


class E2EError(RuntimeError):
    pass


@dataclass(frozen=True)
class E2EConfig:
    backend_url: str
    frontend_url: str
    recognition_url: str
    admin_email: str
    admin_password: str
    school_email: str
    school_password: str
    webhook_secret: str
    recognition_api_token: str
    image_valid: Path
    image_no_face: Path
    image_second: Path
    require_notifications: bool
    responsavel_nome: str
    responsavel_telefone: str
    responsavel_email: str
    responsavel_parentesco: str
    poll_seconds: int
    poll_interval_seconds: float


class E2ERunner:
    def __init__(self, config: E2EConfig) -> None:
        self.config = config
        self.client = httpx.Client(timeout=30.0, trust_env=False)
        self.admin_token = ""
        self.school_token = ""
        self.school_user: dict[str, Any] = {}
        self.created_alunos: list[int] = []
        self.responsavel: dict[str, Any] | None = None

    def close(self) -> None:
        self.client.close()

    def run(self) -> None:
        self._step("Validating local config")
        self._validate_config()

        self._step("Logging in to backend")
        admin = self.login(self.config.admin_email, self.config.admin_password)
        school = self.login(self.config.school_email, self.config.school_password)
        self.admin_token = admin["access_token"]
        self.school_token = school["access_token"]
        self.school_user = school.get("usuario") or {}
        if not self.school_user.get("id"):
            raise E2EError("Backend login did not return usuario.id for TEST_SCHOOL_EMAIL.")

        self._step("Checking backend health")
        backend_health = self.backend_health()
        self._expect(backend_health.get("backend", {}).get("status") == "online", "backend health is not online")
        self._expect(backend_health.get("database", {}).get("status") == "online", "backend database is not online")
        self._expect("recognition_service" in backend_health, "backend health did not include recognition_service")
        self._expect("cloudinary" in backend_health, "backend health did not include cloudinary")
        self._expect("webhook" in backend_health, "backend health did not include webhook")
        self._expect("notifications" in backend_health, "backend health did not include notifications")
        self._expect(backend_health.get("trace_id"), "backend health did not include trace_id")

        self._step("Checking recognition-service health")
        recognition_health = self.recognition_health()
        self._expect(recognition_health.get("status") in {"online", "ok"}, "recognition-service is not online")
        self._expect(recognition_health.get("database") == "online", "recognition-service database is not online")
        self._expect(recognition_health.get("redis") == "online", "recognition-service redis is not online")
        self._expect("model_loaded" in recognition_health, "recognition health did not include model_loaded")
        self._expect("webhook_configured" in recognition_health, "recognition health did not include webhook_configured")
        self._expect(recognition_health.get("school_id"), "recognition health did not include school_id")
        self._expect(recognition_health.get("camera_id"), "recognition health did not include camera_id")

        self._step("Creating student with valid photo")
        run_id = uuid.uuid4().hex[:10]
        name = f"E2E Recognition {run_id}"
        turma = f"E2E-{run_id[:4]}"
        aluno = self.create_student(name=name, turma=turma, image_path=self.config.image_valid)
        self.created_alunos.append(aluno["id"])
        aluno = self.poll_student(aluno["id"], expected_statuses={"ready"})
        self._expect(aluno.get("external_id"), "created student did not include external_id")
        self._expect(aluno.get("face_samples_count", 0) >= 1, "student did not reach at least one face sample")
        school_id = f"escola_{aluno['empresa_id']}"

        self._step("Creating/linking responsible person")
        self.responsavel = self.create_or_link_responsavel(aluno["id"])
        if self.responsavel:
            aluno = self.get_student(aluno["id"])
            responsaveis = aluno.get("responsaveis") or []
            self._expect(
                any(item.get("id") == self.responsavel.get("id") for item in responsaveis),
                "student response did not include linked responsavel",
            )
        elif self.config.require_notifications:
            raise E2EError("E2E_REQUIRE_NOTIFICATIONS=true but responsavel could not be created/linked.")

        self._step("Checking recognition-service face sample visibility")
        faces = self.list_recognition_faces(school_id, aluno["external_id"])
        if faces is None:
            print("WARN recognition-service direct face listing skipped; RECOGNITION_API_TOKEN is empty.")
        else:
            self._expect(faces.get("count", 0) >= 1, "recognition-service did not list the first face sample")
            self._expect(faces.get("school_id") == school_id, "recognition-service school_id mismatch")
            self._expect(str(faces.get("external_id")) == str(aluno["external_id"]), "recognition-service external_id mismatch")

        self._step("Adding second biometric photo")
        before_count = int(aluno.get("face_samples_count") or 0)
        second_photo = self.add_student_photo(aluno["id"], self.config.image_second)
        aluno_after_second = self.poll_student(aluno["id"], expected_statuses={"ready"})
        self._expect(second_photo.get("biometria_status") == "ready", "second photo did not reach ready status")
        self._expect(
            int(aluno_after_second.get("face_samples_count") or 0) >= max(2, before_count + 1),
            "face_samples_count did not increase after second photo",
        )

        self._step("Removing one biometric photo")
        self.delete_student_photo(aluno["id"], second_photo["id"])
        aluno_after_delete = self.poll_student(aluno["id"], expected_statuses={"ready", "no_photo", "failed"})
        self._expect(
            int(aluno_after_delete.get("face_samples_count") or 0) <= int(aluno_after_second.get("face_samples_count") or 0),
            "face_samples_count increased after deleting a photo",
        )

        self._step("Testing no-face image")
        no_face = self.create_student(
            name=f"E2E No Face {run_id}",
            turma=turma,
            image_path=self.config.image_no_face,
            suffix="NOFACE",
        )
        self.created_alunos.append(no_face["id"])
        no_face = self.poll_student(no_face["id"], expected_statuses={"needs_new_photo", "failed", "no_photo"})
        self._expect(no_face.get("biometria_status") != "ready", "no-face image incorrectly reached ready status")
        self._expect(no_face.get("biometria_error"), "no-face flow did not expose biometria_error")

        self._step("Creating no-photo student for sem_foto filter")
        no_photo = self.create_student_without_photo(
            name=f"E2E Sem Foto {run_id}",
            turma=turma,
            suffix="NOFOTO",
        )
        self.created_alunos.append(no_photo["id"])
        self._expect(no_photo.get("biometria_status") == "no_photo", "no-photo student did not return no_photo status")

        self._step("Running identify-only diagnosis")
        presencas_before = self.list_presencas(aluno["id"])
        notifications_before_diag = self.list_notifications()
        trace_id = f"e2e-trace-{uuid.uuid4()}"
        diagnosis = self.identify(self.config.image_valid, trace_id=trace_id)
        self._expect(diagnosis.get("trace_id"), "diagnosis did not return trace_id")
        self._expect(diagnosis.get("status") in {"success", "ok"}, "diagnosis did not return a success-like status")
        self._expect("confianca" in diagnosis, "diagnosis did not include confidence")
        self._expect(len(self.list_presencas(aluno["id"])) == len(presencas_before), "diagnosis created a Presenca")
        self._expect(
            len(self.list_notifications()) == len(notifications_before_diag),
            "diagnosis created NotificationOutbox rows",
        )

        self._step("Simulating entry webhook")
        notifications_before_entry = self.list_notifications(status="pending")
        entry_event_id = f"e2e-entry-{uuid.uuid4()}"
        entry_payload = self.webhook_payload(
            event_id=entry_event_id,
            school_id=school_id,
            external_id=aluno["external_id"],
            student_name=aluno["nome"],
            camera_id="entrada_principal",
            tipo_evento="entrada",
        )
        entry = self.post_webhook(entry_payload)
        self._expect(entry.get("tipo_evento") == "entrada", "entry webhook did not create entrada")
        self._expect(entry.get("origem") in {"facial", "webhook"}, "entry webhook origem is not facial/webhook")
        self._expect(abs(float(entry.get("confianca") or 0) - 0.91) < 0.0001, "entry confidence was not saved")
        self._expect(entry.get("camera_id") == "entrada_principal", "entry camera_id was not saved")
        notifications_after_entry = self.list_notifications(status="pending")
        entry_notifications = self.new_notifications(
            before=notifications_before_entry,
            after=notifications_after_entry,
            aluno_id=aluno["id"],
            presenca_id=entry["id"],
        )
        if self.should_require_notifications():
            self._expect(entry_notifications, "entry webhook did not create a pending notification")
            self._expect(
                any("chegou à escola às" in str(n.get("mensagem", "")) for n in entry_notifications),
                "entry notification message did not match the expected arrival text",
            )

        self._step("Re-sending duplicate webhook")
        duplicate = self.post_webhook(entry_payload)
        self._expect(duplicate.get("id") == entry.get("id"), "duplicate webhook created a second Presenca")
        notifications_after_duplicate = self.list_notifications(status="pending")
        self._expect(
            len(notifications_after_duplicate) == len(notifications_after_entry),
            "duplicate webhook created a second notification",
        )

        self._step("Simulating exit webhook")
        exit_event_id = f"e2e-exit-{uuid.uuid4()}"
        exit_payload = self.webhook_payload(
            event_id=exit_event_id,
            school_id=school_id,
            external_id=aluno["external_id"],
            student_name=aluno["nome"],
            camera_id="saida_principal",
            tipo_evento="saida",
        )
        exit_presence = self.post_webhook(exit_payload)
        self._expect(exit_presence.get("tipo_evento") == "saida", "exit webhook did not create saida")
        self._expect(exit_presence.get("camera_id") == "saida_principal", "exit camera_id was not saved")

        self._step("Checking notifications")
        pending_notifications = self.list_notifications(status="pending")
        exit_notifications = self.new_notifications(
            before=notifications_after_duplicate,
            after=pending_notifications,
            aluno_id=aluno["id"],
            presenca_id=exit_presence["id"],
        )
        if self.should_require_notifications():
            self._expect(exit_notifications, "exit webhook did not create a pending notification")
            self._expect(
                any("saiu da escola às" in str(n.get("mensagem", "")) for n in exit_notifications),
                "exit notification message did not match the expected departure text",
            )
        else:
            print("WARN notification creation is not required; set E2E_REQUIRE_NOTIFICATIONS=true to make this mandatory.")
        self._expect(
            len(self.list_notifications(status="pending")) == len(pending_notifications),
            "duplicate checks caused notification count instability",
        )

        self._step("Checking student filters")
        self.assert_student_filter("search", name, aluno["id"])
        self.assert_student_filter("biometria_status", "ready", aluno["id"], allow_absent=True)
        self.assert_student_filter("sem_foto", "true", no_photo["id"])
        self.assert_student_filter("turma", turma, aluno["id"])

        self._step("Trace ID checks")
        self._expect(trace_id == diagnosis.get("trace_id"), "diagnosis did not propagate supplied X-Trace-Id")
        self._expect(entry_payload["trace_id"], "webhook payload did not include trace_id")

        print("\nE2E completed successfully.")

    def login(self, email: str, password: str) -> dict[str, Any]:
        response = self.client.post(
            self.url(self.config.backend_url, "/api/auth/login"),
            json={"email": email, "senha": password},
        )
        return self.json_response(response, "backend login", expected={200})

    def backend_health(self) -> dict[str, Any]:
        response = self.client.get(
            self.url(self.config.backend_url, "/api/admin/system-health"),
            headers=self.auth(self.admin_token),
        )
        return self.json_response(response, "backend system-health", expected={200})

    def recognition_health(self) -> dict[str, Any]:
        response = self.client.get(self.url(self.config.recognition_url, "/api/health"))
        return self.json_response(response, "recognition-service health", expected={200})

    def create_student(self, *, name: str, turma: str, image_path: Path, suffix: str = "VALID") -> dict[str, Any]:
        numero = f"E2E-{suffix}-{uuid.uuid4().hex[:12]}"
        with image_path.open("rb") as image:
            response = self.client.post(
                self.url(self.config.backend_url, "/api/alunos/"),
                headers=self.auth(self.school_token),
                data={
                    "nome": name,
                    "numero_inscricao": numero,
                    "telefone": "88999990000",
                    "turma": turma,
                },
                files={"foto": (image_path.name, image, self._content_type(image_path))},
            )
        return self.json_response(response, "create student", expected={201})

    def create_student_without_photo(self, *, name: str, turma: str, suffix: str) -> dict[str, Any]:
        numero = f"E2E-{suffix}-{uuid.uuid4().hex[:12]}"
        response = self.client.post(
            self.url(self.config.backend_url, "/api/alunos/"),
            headers=self.auth(self.school_token),
            data={
                "nome": name,
                "numero_inscricao": numero,
                "telefone": "88999990000",
                "turma": turma,
            },
        )
        return self.json_response(response, "create no-photo student", expected={201})

    def get_student(self, aluno_id: int) -> dict[str, Any]:
        response = self.client.get(
            self.url(self.config.backend_url, f"/api/alunos/{aluno_id}"),
            headers=self.auth(self.school_token),
        )
        return self.json_response(response, f"get student {aluno_id}", expected={200})

    def create_or_link_responsavel(self, aluno_id: int) -> dict[str, Any] | None:
        response = self.client.post(
            self.url(self.config.backend_url, f"/api/alunos/{aluno_id}/responsaveis"),
            headers=self.auth(self.school_token),
            json={
                "nome": self.config.responsavel_nome,
                "telefone": self.config.responsavel_telefone,
                "email": self.config.responsavel_email or None,
                "parentesco": self.config.responsavel_parentesco,
            },
        )
        if response.status_code in {404, 405, 501} and not self.config.require_notifications:
            print(
                "WARN responsavel endpoint is not available; "
                "notification assertions will stay optional."
            )
            return None
        return self.json_response(response, "create/link responsavel", expected={200, 201})

    def poll_student(self, aluno_id: int, *, expected_statuses: set[str]) -> dict[str, Any]:
        deadline = time.monotonic() + self.config.poll_seconds
        last: dict[str, Any] | None = None
        while time.monotonic() <= deadline:
            last = self.get_student(aluno_id)
            if str(last.get("biometria_status")) in expected_statuses:
                return last
            time.sleep(self.config.poll_interval_seconds)
        raise E2EError(
            f"Student {aluno_id} did not reach {sorted(expected_statuses)} within "
            f"{self.config.poll_seconds}s. Last payload: {json.dumps(last, default=str)}"
        )

    def list_recognition_faces(self, school_id: str, external_id: str) -> dict[str, Any] | None:
        if not self.config.recognition_api_token:
            return None
        response = self.client.get(
            self.url(self.config.recognition_url, "/api/students/faces"),
            params={"school_id": school_id, "external_id": external_id},
            headers=self.recognition_auth(),
        )
        return self.json_response(response, "recognition-service list faces", expected={200})

    def add_student_photo(self, aluno_id: int, image_path: Path) -> dict[str, Any]:
        with image_path.open("rb") as image:
            response = self.client.post(
                self.url(self.config.backend_url, f"/api/alunos/{aluno_id}/fotos"),
                headers=self.auth(self.school_token),
                files={"foto": (image_path.name, image, self._content_type(image_path))},
            )
        return self.json_response(response, "add student photo", expected={201})

    def delete_student_photo(self, aluno_id: int, foto_id: int) -> None:
        response = self.client.delete(
            self.url(self.config.backend_url, f"/api/alunos/{aluno_id}/fotos/{foto_id}"),
            headers=self.auth(self.school_token),
        )
        if response.status_code != 204:
            self.json_response(response, "delete student photo", expected={204})

    def identify(self, image_path: Path, *, trace_id: str) -> dict[str, Any]:
        with image_path.open("rb") as image:
            response = self.client.post(
                self.url(self.config.backend_url, "/api/reconhecimento/identificar"),
                headers={**self.auth(self.school_token), "X-Trace-Id": trace_id},
                files={"imagem": (image_path.name, image, self._content_type(image_path))},
            )
        return self.json_response(response, "identify-only diagnosis", expected={200})

    def list_presencas(self, aluno_id: int) -> list[dict[str, Any]]:
        response = self.client.get(
            self.url(self.config.backend_url, f"/api/presencas/aluno/{aluno_id}"),
            headers=self.auth(self.school_token),
        )
        data = self.json_response(response, "list presencas", expected={200})
        if not isinstance(data, list):
            raise E2EError("list presencas did not return a list")
        return data

    def list_notifications(self, status: str | None = None) -> list[dict[str, Any]]:
        params = {"status": status} if status else None
        response = self.client.get(
            self.url(self.config.backend_url, "/api/notificacoes"),
            headers=self.auth(self.school_token),
            params=params,
        )
        data = self.json_response(response, "list notifications", expected={200})
        if not isinstance(data, list):
            raise E2EError("list notifications did not return a list")
        return data

    def new_notifications(
        self,
        *,
        before: list[dict[str, Any]],
        after: list[dict[str, Any]],
        aluno_id: int,
        presenca_id: int,
    ) -> list[dict[str, Any]]:
        before_ids = {item.get("id") for item in before}
        return [
            item
            for item in after
            if item.get("id") not in before_ids
            and item.get("aluno_id") == aluno_id
            and item.get("presenca_id") == presenca_id
            and item.get("status") == "pending"
        ]

    def webhook_payload(
        self,
        *,
        event_id: str,
        school_id: str,
        external_id: str,
        student_name: str,
        camera_id: str,
        tipo_evento: str,
    ) -> dict[str, Any]:
        return {
            "event": "presence_detected",
            "event_id": event_id,
            "school_id": school_id,
            "camera_id": camera_id,
            "student_id": str(external_id),
            "student_name": student_name,
            "confidence": 0.91,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "tipo_evento": tipo_evento,
            "trace_id": f"e2e-trace-{uuid.uuid4()}",
        }

    def post_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        digest = hmac.new(self.config.webhook_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Recognition-Signature": f"sha256={digest}",
            "Idempotency-Key": payload["event_id"],
            "X-Trace-Id": payload.get("trace_id", ""),
        }
        response = self.client.post(
            self.url(self.config.backend_url, "/api/recognition/presences"),
            content=body,
            headers=headers,
        )
        return self.json_response(response, f"webhook {payload['event_id']}", expected={200, 201})

    def assert_student_filter(self, key: str, value: str, aluno_id: int, *, allow_absent: bool = False) -> None:
        response = self.client.get(
            self.url(self.config.backend_url, "/api/alunos/"),
            headers=self.auth(self.school_token),
            params={key: value},
        )
        payload = self.json_response(response, f"student filter {key}", expected={200})
        data = payload.get("data")
        self._expect(isinstance(data, list), f"student filter {key} did not return data list")
        found = any(item.get("id") == aluno_id for item in data)
        if not found and not allow_absent:
            raise E2EError(f"student {aluno_id} was not returned by filter {key}={value}")

    def json_response(self, response: httpx.Response, label: str, *, expected: set[int]) -> Any:
        if response.status_code not in expected:
            body = response.text[:1200]
            raise E2EError(f"{label} failed with HTTP {response.status_code}. Body: {body}")
        if response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise E2EError(f"{label} did not return JSON. Body: {response.text[:500]}") from exc

    def _validate_config(self) -> None:
        required = {
            "BACKEND_URL": self.config.backend_url,
            "RECOGNITION_SERVICE_URL": self.config.recognition_url,
            "ADMIN_EMAIL": self.config.admin_email,
            "ADMIN_PASSWORD": self.config.admin_password,
            "TEST_SCHOOL_EMAIL": self.config.school_email,
            "TEST_SCHOOL_PASSWORD": self.config.school_password,
            "RECOGNITION_WEBHOOK_SECRET": self.config.webhook_secret,
            "RECOGNITION_API_TOKEN": self.config.recognition_api_token,
        }
        for key, value in required.items():
            self._validate_required_env(key, value)

        images = {
            "TEST_IMAGE_VALID": self.config.image_valid,
            "TEST_IMAGE_SECOND_SAMPLE": self.config.image_second,
            "TEST_IMAGE_NO_FACE": self.config.image_no_face,
        }
        for key, path in images.items():
            if not path.exists():
                raise E2EError(f"Imagem configurada em {key} não existe: {path}")
            if not path.is_file():
                raise E2EError(f"Caminho configurado em {key} não é um arquivo: {path}")

    @staticmethod
    def _validate_required_env(key: str, value: str) -> None:
        normalized = (value or "").strip()
        if not normalized or normalized in PLACEHOLDER_VALUES:
            raise E2EError(REQUIRED_ENV_MESSAGES[key])

    def should_require_notifications(self) -> bool:
        return self.config.require_notifications

    @staticmethod
    def _expect(condition: Any, message: str) -> None:
        if not condition:
            raise E2EError(message)

    @staticmethod
    def _step(message: str) -> None:
        print(f"\n==> {message}")

    @staticmethod
    def url(base_url: str, path: str) -> str:
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    @staticmethod
    def auth(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def recognition_auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.recognition_api_token}"}

    @staticmethod
    def _content_type(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".png":
            return "image/png"
        return "application/octet-stream"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise E2EError(f"{name} must be an integer") from exc


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise E2EError(f"{name} must be a number") from exc


def resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def build_config(env_file: Path) -> E2EConfig:
    load_env_file(env_file)
    return E2EConfig(
        backend_url=os.getenv("BACKEND_URL", "http://localhost:8000"),
        frontend_url=os.getenv("FRONTEND_URL", "http://localhost:5173"),
        recognition_url=os.getenv("RECOGNITION_SERVICE_URL", "http://localhost:8001"),
        admin_email=os.getenv("ADMIN_EMAIL", ""),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
        school_email=os.getenv("TEST_SCHOOL_EMAIL", ""),
        school_password=os.getenv("TEST_SCHOOL_PASSWORD", ""),
        webhook_secret=os.getenv("RECOGNITION_WEBHOOK_SECRET", ""),
        recognition_api_token=os.getenv("RECOGNITION_API_TOKEN", ""),
        image_valid=resolve_path(os.getenv("TEST_IMAGE_VALID", "tools/e2e/assets/student_valid.jpg")),
        image_no_face=resolve_path(os.getenv("TEST_IMAGE_NO_FACE", "tools/e2e/assets/no_face.jpg")),
        image_second=resolve_path(os.getenv("TEST_IMAGE_SECOND_SAMPLE", "tools/e2e/assets/student_second.jpg")),
        require_notifications=env_bool("E2E_REQUIRE_NOTIFICATIONS", False),
        responsavel_nome=os.getenv("E2E_RESPONSAVEL_NOME", "Responsavel E2E"),
        responsavel_telefone=os.getenv("E2E_RESPONSAVEL_TELEFONE", "+5588999999999"),
        responsavel_email=os.getenv("E2E_RESPONSAVEL_EMAIL", "responsavel.e2e@example.com"),
        responsavel_parentesco=os.getenv("E2E_RESPONSAVEL_PARENTESCO", "responsavel"),
        poll_seconds=env_int("E2E_POLL_SECONDS", 30),
        poll_interval_seconds=env_float("E2E_POLL_INTERVAL_SECONDS", 2.0),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live backend_v2 + recognition-service E2E checks.")
    parser.add_argument(
        "--env-file",
        default=str(ROOT / ".env.e2e"),
        help="Path to the E2E env file. Defaults to .env.e2e in the backend_v2 root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = build_config(Path(args.env_file))
        runner = E2ERunner(config)
        try:
            runner.run()
        finally:
            runner.close()
        return 0
    except E2EError as exc:
        print(f"\nE2E FAILED: {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"\nE2E FAILED: HTTP error {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
