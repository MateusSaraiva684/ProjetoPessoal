import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppError
from app.models.models import Aluno, NotificationOutbox, Presenca, Responsavel
from app.services.face_recognition_service import FaceRecognitionResult, FaceRecognitionService
from app.services.notification_service import (
    NotificationProviderError,
    NotificationSendResult,
    NotificationService,
    PRESENCE_ARRIVAL_TYPE,
)


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def aluno_payload(**overrides):
    data = {
        "nome": "Ana Silva",
        "numero_inscricao": "2026-1000",
        "telefone": "88999990000",
    }
    data.update(overrides)
    return data


def criar_aluno(client, token):
    return client.post(
        "/api/alunos/",
        headers=headers(token),
        data=aluno_payload(),
    ).json()


def recognition_payload(aluno, **overrides):
    data = {
        "event": "presence_detected",
        "event_id": f"presence:{aluno['user_id']}:{aluno['id']}",
        "school_id": f"escola_{aluno['user_id']}",
        "camera_id": "entrada_principal",
        "presence_id": 17,
        "student_id": str(aluno["id"]),
        "student_name": "Nome vindo do recognition-service",
        "confidence": 1.0,
        "detected_at": "2026-05-20T10:15:00+00:00",
        "message_template": "{student_name} chegou na escola as {local_time}",
    }
    data.update(overrides)
    return data


def signed_json_request(payload, secret="webhook-secret", event_id=None):
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    request_headers = {
        "Content-Type": "application/json",
        "X-Recognition-Signature": f"sha256={signature}",
    }
    if event_id is None:
        event_id = payload.get("event_id")
    if event_id is not None:
        request_headers["Idempotency-Key"] = event_id
    return raw_body, request_headers


def post_recognition_event(client, payload, secret="webhook-secret"):
    raw_body, request_headers = signed_json_request(payload, secret=secret)
    return client.post(
        "/api/recognition/presences",
        content=raw_body,
        headers=request_headers,
    )


def vincular_responsavel(db_session, aluno_id, telefone="88999991111"):
    aluno = db_session.get(Aluno, aluno_id)
    responsavel = Responsavel(
        nome="Responsavel Ana",
        telefone=telefone,
        email="resp@email.com",
    )
    aluno.responsaveis.append(responsavel)
    db_session.commit()
    return responsavel


def notificacoes(db_session):
    return db_session.query(NotificationOutbox).order_by(NotificationOutbox.id).all()


def test_registrar_presenca_manual(client, usuario_e_token):
    aluno = criar_aluno(client, usuario_e_token)

    resp = client.post(
        "/api/presencas/manual",
        headers=headers(usuario_e_token),
        json={"aluno_id": aluno["id"]},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["aluno_id"] == aluno["id"]
    assert data["origem"] == "manual"
    assert data["status"] == "confirmado"


def test_receber_presenca_da_api_reconhecimento(client, usuario_e_token, monkeypatch):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "")

    resp = client.post(
        "/api/presencas",
        json={
            "external_id": aluno["id"],
            "empresa_id": aluno["user_id"],
            "confianca": 0.91,
        },
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["aluno_id"] == aluno["id"]
    assert data["origem"] == "facial"
    assert data["confianca"] == 0.91
    assert data["status"] == "confirmado"


def test_receber_presenca_da_api_reconhecimento_exige_segredo_configurado(
    client,
    usuario_e_token,
    monkeypatch,
):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "webhook-secret")

    resp = client.post(
        "/api/presencas",
        json={
            "external_id": aluno["id"],
            "empresa_id": aluno["user_id"],
            "confianca": 0.91,
        },
    )

    assert resp.status_code == 401
    assert resp.json()["erro"] == "Credenciais invalidas"


def test_receber_presenca_da_api_reconhecimento_aceita_segredo_configurado(
    client,
    usuario_e_token,
    monkeypatch,
):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "webhook-secret")

    resp = client.post(
        "/api/presencas",
        headers={"Authorization": "Bearer webhook-secret"},
        json={
            "external_id": aluno["id"],
            "empresa_id": aluno["user_id"],
            "confianca": 0.91,
        },
    )

    assert resp.status_code == 201
    assert resp.json()["aluno_id"] == aluno["id"]


def test_webhook_reconhecimento_rejeita_sem_segredo_ou_assinatura(
    client,
    usuario_e_token,
    monkeypatch,
):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    payload = recognition_payload(aluno)
    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "webhook-secret")

    resp = client.post(
        "/api/recognition/presences",
        json=payload,
        headers={"Idempotency-Key": payload["event_id"]},
    )

    assert resp.status_code == 401
    assert resp.json()["erro"] == "Credenciais invalidas"


def test_webhook_reconhecimento_aceita_assinatura_valida_cria_presenca_e_notificacao_pendente(
    client,
    usuario_e_token,
    db_session,
    monkeypatch,
):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    vincular_responsavel(db_session, aluno["id"])
    payload = recognition_payload(aluno)

    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setattr(settings, "NOTIFICATION_PROVIDER", "log")

    resp = post_recognition_event(client, payload)

    assert resp.status_code == 201
    data = resp.json()
    assert data["aluno_id"] == aluno["id"]
    assert data["origem"] == "facial"
    assert data["status"] == "confirmado"
    assert data["confianca"] == 1.0
    outbox = notificacoes(db_session)
    assert len(outbox) == 1
    assert outbox[0].tipo == "presence_arrival"
    assert outbox[0].status == "pending"
    assert outbox[0].canal == "log"
    assert outbox[0].presenca_id == data["id"]
    assert outbox[0].aluno_id == aluno["id"]
    assert outbox[0].telefone_destino == "5588999991111"
    assert outbox[0].mensagem == "Ana Silva chegou \u00e0 escola \u00e0s 07:15."


def test_webhook_reconhecimento_rejeita_assinatura_invalida(
    client,
    usuario_e_token,
    monkeypatch,
):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    payload = recognition_payload(aluno)
    raw_body, request_headers = signed_json_request(payload)
    request_headers["X-Recognition-Signature"] = "sha256=assinatura-invalida"
    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "webhook-secret")

    resp = client.post(
        "/api/recognition/presences",
        content=raw_body,
        headers=request_headers,
    )

    assert resp.status_code == 401
    assert resp.json()["erro"] == "Credenciais invalidas"


def test_webhook_reconhecimento_evento_repetido_nao_duplica_presenca_nem_notificacao(
    client,
    usuario_e_token,
    db_session,
    monkeypatch,
):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    vincular_responsavel(db_session, aluno["id"])
    payload = recognition_payload(aluno)

    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setattr(settings, "NOTIFICATION_PROVIDER", "log")

    primeira = post_recognition_event(client, payload)
    segunda = post_recognition_event(client, payload)

    assert primeira.status_code == 201
    assert segunda.status_code == 201
    assert segunda.json()["id"] == primeira.json()["id"]
    assert len(notificacoes(db_session)) == 1


def test_webhook_reconhecimento_aluno_sem_responsavel_nao_quebra(
    client,
    usuario_e_token,
    db_session,
    monkeypatch,
):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    payload = recognition_payload(aluno)
    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "webhook-secret")

    resp = post_recognition_event(client, payload)

    assert resp.status_code == 201
    assert resp.json()["aluno_id"] == aluno["id"]
    assert notificacoes(db_session) == []


class ProviderOk:
    channel = "log"

    def send(self, notification):
        assert notification.mensagem == "Ana Silva chegou \u00e0 escola \u00e0s 07:15."
        return NotificationSendResult(provider_message_id=f"fake-{notification.id}")


class ProviderFalha:
    channel = "log"

    def send(self, notification):
        raise NotificationProviderError("provider_down", retryable=True)


def test_processador_marca_notificacao_como_sent_quando_provider_funciona(
    client,
    usuario_e_token,
    db_session,
    monkeypatch,
):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    vincular_responsavel(db_session, aluno["id"])
    payload = recognition_payload(aluno)
    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "webhook-secret")
    post_recognition_event(client, payload)

    resultado = NotificationService(db_session, provider=ProviderOk()).processar_pendentes()

    notification = notificacoes(db_session)[0]
    assert resultado == {"processed": 1, "sent": 1, "failed": 0, "retried": 0}
    assert notification.status == "sent"
    assert notification.provider_message_id == f"fake-{notification.id}"
    assert notification.sent_at is not None


def test_processador_reagenda_e_depois_falha_quando_provider_falha(
    client,
    usuario_e_token,
    db_session,
    monkeypatch,
):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    vincular_responsavel(db_session, aluno["id"])
    payload = recognition_payload(aluno)
    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setattr(settings, "NOTIFICATION_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "NOTIFICATION_RETRY_SECONDS", 60)
    post_recognition_event(client, payload)

    service = NotificationService(db_session, provider=ProviderFalha())
    agora = datetime.now(timezone.utc)
    primeira = service.processar_pendentes(now=agora)
    notification = notificacoes(db_session)[0]

    assert primeira == {"processed": 1, "sent": 0, "failed": 0, "retried": 1}
    assert notification.status == "pending"
    assert notification.attempts == 1
    assert notification.next_attempt_at is not None
    assert notification.last_error == "provider_down"

    segunda = service.processar_pendentes(now=agora + timedelta(seconds=61))
    notification = notificacoes(db_session)[0]

    assert segunda == {"processed": 1, "sent": 0, "failed": 1, "retried": 0}
    assert notification.status == "failed"
    assert notification.attempts == 2
    assert notification.next_attempt_at is None


def test_constraint_impede_notificacao_duplicada_para_mesma_presenca_responsavel_canal(
    client,
    usuario_e_token,
    db_session,
    monkeypatch,
):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    responsavel = vincular_responsavel(db_session, aluno["id"])
    payload = recognition_payload(aluno)
    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "webhook-secret")
    post_recognition_event(client, payload)
    existente = notificacoes(db_session)[0]

    duplicada = NotificationOutbox(
        tipo=PRESENCE_ARRIVAL_TYPE,
        status="pending",
        canal=existente.canal,
        presenca_id=existente.presenca_id,
        aluno_id=aluno["id"],
        responsavel_id=responsavel.id,
        telefone_destino="5588999991111",
        mensagem=existente.mensagem,
    )
    db_session.add(duplicada)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_webhook_reconhecimento_student_id_invalido_retorna_erro_controlado(
    client,
    usuario_e_token,
    monkeypatch,
):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    payload = recognition_payload(
        aluno,
        event_id=f"presence:{aluno['user_id']}:999",
        student_id="999",
    )
    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "webhook-secret")

    resp = post_recognition_event(client, payload)

    assert resp.status_code == 400
    assert resp.json()["erro"] == "external_id invalido para empresa_id informado"


def test_receber_presenca_rejeita_external_id_invalido(client, usuario_e_token, monkeypatch):
    from app.core.config import settings

    aluno = criar_aluno(client, usuario_e_token)
    monkeypatch.setattr(settings, "RECOGNITION_WEBHOOK_SECRET", "")

    resp = client.post(
        "/api/presencas",
        json={
            "external_id": "inexistente",
            "empresa_id": aluno["user_id"],
            "confianca": 0.91,
        },
    )

    assert resp.status_code == 400
    assert resp.json()["erro"] == "external_id invalido para empresa_id informado"


def test_listar_historico_presencas(client, usuario_e_token):
    aluno = criar_aluno(client, usuario_e_token)
    client.post(
        "/api/presencas/manual",
        headers=headers(usuario_e_token),
        json={"aluno_id": aluno["id"]},
    )

    resp = client.get(
        f"/api/presencas/aluno/{aluno['id']}",
        headers=headers(usuario_e_token),
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_reconhecimento_facial_cria_presenca(client, usuario_e_token, monkeypatch):
    aluno = criar_aluno(client, usuario_e_token)

    async def reconhecer_fake(self, payload):
        assert payload.base64_image == "imagem-em-base64"
        return FaceRecognitionResult(
            aluno_id=None,
            external_id=str(aluno["id"]),
            school_id=f"escola_{aluno['user_id']}",
            confianca=0.97,
        )

    monkeypatch.setattr(FaceRecognitionService, "reconhecer", reconhecer_fake)

    resp = client.post(
        "/api/reconhecimento/facial",
        headers=headers(usuario_e_token),
        json={"imagem_base64": "imagem-em-base64"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["aluno_id"] == aluno["id"]
    assert data["confianca"] == 0.97
    assert data["presenca"]["origem"] == "facial"
    assert data["presenca"]["status"] == "confirmado"


def test_identificar_facial_nao_cria_presenca(client, usuario_e_token, db_session, monkeypatch):
    aluno = criar_aluno(client, usuario_e_token)
    total_antes = db_session.query(Presenca).count()

    async def reconhecer_fake(self, payload):
        assert payload.base64_image == "imagem-em-base64"
        return FaceRecognitionResult(
            aluno_id=None,
            external_id=str(aluno["id"]),
            school_id=f"escola_{aluno['user_id']}",
            confianca=0.95,
        )

    monkeypatch.setattr(FaceRecognitionService, "reconhecer", reconhecer_fake)

    resp = client.post(
        "/api/reconhecimento/identificar",
        headers=headers(usuario_e_token),
        json={"imagem_base64": "imagem-em-base64"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["aluno_id"] == aluno["id"]
    assert data["external_id"] == str(aluno["id"])
    assert data["confianca"] == 0.95
    assert data["aluno"]["id"] == aluno["id"]
    assert db_session.query(Presenca).count() == total_antes


def test_reconhecimento_facial_rejeita_resposta_apenas_com_aluno_id(
    client,
    usuario_e_token,
    db_session,
    monkeypatch,
):
    aluno = criar_aluno(client, usuario_e_token)
    total_antes = db_session.query(Presenca).count()

    async def reconhecer_fake(self, payload):
        return FaceRecognitionResult(aluno_id=aluno["id"], external_id=None, confianca=0.97)

    monkeypatch.setattr(FaceRecognitionService, "reconhecer", reconhecer_fake)

    resp = client.post(
        "/api/reconhecimento/facial",
        headers=headers(usuario_e_token),
        json={"imagem_base64": "imagem-em-base64"},
    )

    assert resp.status_code == 400
    assert resp.json()["erro"] == "Resposta do reconhecimento sem identificador de aluno"
    assert db_session.query(Presenca).count() == total_antes


def test_reconhecimento_facial_rejeita_school_id_de_outra_empresa(
    client,
    usuario_e_token,
    db_session,
    monkeypatch,
):
    aluno = criar_aluno(client, usuario_e_token)
    total_antes = db_session.query(Presenca).count()

    async def reconhecer_fake(self, payload):
        return FaceRecognitionResult(
            aluno_id=None,
            external_id=str(aluno["id"]),
            school_id="escola_999",
            confianca=0.97,
        )

    monkeypatch.setattr(FaceRecognitionService, "reconhecer", reconhecer_fake)

    resp = client.post(
        "/api/reconhecimento/facial",
        headers=headers(usuario_e_token),
        json={"imagem_base64": "imagem-em-base64"},
    )

    assert resp.status_code == 400
    assert resp.json()["erro"] == "school_id do reconhecimento nao corresponde ao usuario autenticado"
    assert db_session.query(Presenca).count() == total_antes


def test_reconhecimento_facial_usa_external_id_do_recognition_service(
    client,
    usuario_e_token,
    monkeypatch,
):
    aluno = criar_aluno(client, usuario_e_token)

    async def reconhecer_fake(self, payload):
        return FaceRecognitionResult(
            aluno_id=None,
            external_id=str(aluno["id"]),
            school_id=f"escola_{aluno['user_id']}",
            confianca=0.94,
        )

    monkeypatch.setattr(FaceRecognitionService, "reconhecer", reconhecer_fake)

    resp = client.post(
        "/api/reconhecimento/facial",
        headers=headers(usuario_e_token),
        json={"imagem_base64": "imagem-em-base64"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["aluno_id"] == aluno["id"]
    assert data["confianca"] == 0.94
    assert data["presenca"]["aluno_id"] == aluno["id"]


def test_face_recognition_service_parseia_resposta_atual_do_recognition_service():
    resultado = FaceRecognitionService()._parse_result(
        {
            "status": "success",
            "student_id": "42",
            "external_id": "42",
            "school_id": "escola_1",
            "confidence": 0.93,
            "face_sample_id": 1001,
        }
    )

    assert resultado.aluno_id is None
    assert resultado.external_id == "42"
    assert resultado.school_id == "escola_1"
    assert resultado.confianca == 0.93


def test_face_recognition_service_rejeita_resposta_sem_external_id():
    with pytest.raises(AppError) as exc:
        FaceRecognitionService()._parse_result(
            {
                "status": "success",
                "aluno_id": 42,
                "confidence": 0.93,
            }
        )

    assert exc.value.status_code == 502


@pytest.mark.parametrize(
    ("service_error", "expected_status"),
    [
        (AppError(404, "Nenhum aluno reconhecido na imagem"), 404),
        (AppError(409, "Reconhecimento facial ambiguo; revise cadastros duplicados"), 409),
        (AppError(422, "Erro no reconhecimento facial"), 422),
    ],
)
def test_reconhecimento_facial_erros_do_servico_nao_criam_presenca(
    client,
    usuario_e_token,
    db_session,
    monkeypatch,
    service_error,
    expected_status,
):
    total_antes = db_session.query(Presenca).count()

    async def reconhecer_fake(self, payload):
        raise service_error

    monkeypatch.setattr(FaceRecognitionService, "reconhecer", reconhecer_fake)

    resp = client.post(
        "/api/reconhecimento/facial",
        headers=headers(usuario_e_token),
        json={"imagem_base64": "imagem-em-base64"},
    )

    assert resp.status_code == expected_status
    assert db_session.query(Presenca).count() == total_antes


def test_reconhecimento_facial_exige_imagem(client, usuario_e_token):
    resp = client.post(
        "/api/reconhecimento/facial",
        headers=headers(usuario_e_token),
        json={},
    )

    assert resp.status_code == 400


def test_reconhecimento_facial_rejeita_imagem_muito_grande(
    client,
    usuario_e_token,
    monkeypatch,
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_IMAGE_UPLOAD_BYTES", 4)
    resp = client.post(
        "/api/reconhecimento/facial",
        headers={**headers(usuario_e_token), "content-type": "image/jpeg"},
        content=b"12345",
    )

    assert resp.status_code == 400
