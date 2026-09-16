from types import SimpleNamespace


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def aluno_payload(**overrides):
    data = {
        "nome": "Ana Silva",
        "numero_inscricao": "2026-0001",
        "telefone": "88999990000",
    }
    data.update(overrides)
    return data


def stored_photo(**overrides):
    data = {
        "url": "https://res.cloudinary.com/demo/image/upload/aluno.jpg",
        "content": b"foto-bytes",
        "filename": "aluno.jpg",
        "content_type": "image/jpeg",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_listar_alunos_vazio(client, usuario_e_token):
    resp = client.get("/api/alunos/", headers=headers(usuario_e_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "paginacao" in data
    assert len(data["data"]) == 0
    assert data["paginacao"]["total"] == 0


def test_criar_aluno(client, usuario_e_token):
    resp = client.post("/api/alunos/", headers=headers(usuario_e_token), data=aluno_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["nome"] == "Ana Silva"
    assert data["numero_inscricao"] == "2026-0001"
    assert data["telefone"] == "88999990000"
    assert data["foto"] is None
    assert data["external_id"] == str(data["id"])
    assert data["empresa_id"] == data["user_id"]
    assert data["biometria_status"] == "no_photo"
    assert data["face_samples_count"] == 0


def test_criar_aluno_nao_falha_se_sync_externo_falhar(client, usuario_e_token, monkeypatch):
    from app.services.integration_service import IntegrationService
    from app.services.storage_service import StorageService

    def sync_com_erro(self, aluno, photo_file=None):
        raise RuntimeError("servico externo indisponivel")

    monkeypatch.setattr(IntegrationService, "sync_aluno", sync_com_erro)
    monkeypatch.setattr(StorageService, "save_student_photo", lambda self, foto: stored_photo())
    monkeypatch.setattr(StorageService, "delete_photo", lambda self, url: None)

    resp = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Aluno Sync"),
        files={"foto": ("aluno.jpg", b"conteudo", "image/jpeg")},
    )

    assert resp.status_code == 201
    assert resp.json()["nome"] == "Aluno Sync"
    assert resp.json()["biometria_status"] == "failed"


def test_integration_service_envia_external_id_persistido(monkeypatch):
    from app.services.integration_service import IntegrationService

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, timeout, trust_env):
            captured["timeout"] = timeout
            captured["trust_env"] = trust_env

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data, files, headers):
            captured["url"] = url
            captured["data"] = data
            captured["files"] = files
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.services.integration_service.httpx.Client", FakeClient)

    aluno = SimpleNamespace(
        id=10,
        external_id="ext-10",
        nome="Aluno Integrado",
        empresa_id=99,
        foto="https://res.cloudinary.com/demo/image/upload/aluno.jpg",
    )

    result = IntegrationService(
        base_url="https://recognition.example/api",
        timeout_seconds=3,
        api_token="secret-token",
    ).sync_aluno(
        aluno,
        photo_file=stored_photo(
            content=b"imagem-jpeg",
            filename="integrado.jpg",
            content_type="image/jpeg",
        ),
    )

    assert result.success is True
    assert captured["timeout"] == 3
    assert captured["trust_env"] is False
    assert captured["url"] == "https://recognition.example/api/students/sync"
    assert captured["data"] == {
        "school_id": "escola_99",
        "external_id": "ext-10",
        "name": "Aluno Integrado",
        "photo_url": "https://res.cloudinary.com/demo/image/upload/aluno.jpg",
    }
    assert captured["files"] == {
        "file": ("integrado.jpg", b"imagem-jpeg", "image/jpeg")
    }
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert "Content-Type" not in captured["headers"]


def test_integration_service_exclui_biometria_por_external_id(monkeypatch):
    from app.services.integration_service import IntegrationService

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, timeout, trust_env):
            captured["timeout"] = timeout
            captured["trust_env"] = trust_env

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def delete(self, url, params, headers):
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.services.integration_service.httpx.Client", FakeClient)

    aluno = SimpleNamespace(id=10, external_id="ext-10", empresa_id=99)

    result = IntegrationService(
        base_url="https://recognition.example",
        timeout_seconds=3,
        api_token="secret-token",
    ).delete_aluno_biometria(aluno)

    assert result.success is True
    assert captured["timeout"] == 3
    assert captured["trust_env"] is False
    assert captured["url"] == "https://recognition.example/api/students/faces"
    assert captured["params"] == {
        "school_id": "escola_99",
        "external_id": "ext-10",
        "confirm_external_id": "ext-10",
    }
    assert captured["headers"]["Authorization"] == "Bearer secret-token"


def test_integration_service_rejeita_payload_invalido():
    from app.services.integration_service import IntegrationService

    aluno = SimpleNamespace(
        id=10,
        external_id="",
        nome="Aluno Integrado",
        empresa_id=99,
    )

    result = IntegrationService(
        base_url="https://recognition.example/api",
        timeout_seconds=3,
    ).sync_aluno(aluno)

    assert result.success is False
    assert result.retryable is False
    assert result.error == "invalid_payload"


def test_derive_recognition_api_base_url_remove_ultimo_segmento(monkeypatch):
    from app.core.config import _derive_recognition_api_base_url

    monkeypatch.delenv("RECOGNITION_API_BASE_URL", raising=False)
    monkeypatch.delenv("FACE_RECOGNITION_API_BASE_URL", raising=False)

    assert (
        _derive_recognition_api_base_url(service_url="https://recognition.example/facial")
        == "https://recognition.example"
    )
    assert (
        _derive_recognition_api_base_url(
            service_url="https://recognition.example/api/recognize"
        )
        == "https://recognition.example/api"
    )
    assert (
        _derive_recognition_api_base_url(
            service_url="https://recognition.example/api/v1/facial/"
        )
        == "https://recognition.example/api/v1"
    )


def test_criar_aluno_rejeita_campos_em_branco(client, usuario_e_token):
    resp = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="   ", telefone="   "),
    )
    assert resp.status_code == 422


def test_listar_alunos_apos_criar(client, usuario_e_token):
    client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
    )
    resp = client.get("/api/alunos/", headers=headers(usuario_e_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "paginacao" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["nome"] == "Ana"


def test_buscar_aluno(client, usuario_e_token):
    criado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
    ).json()
    resp = client.get(f"/api/alunos/{criado['id']}", headers=headers(usuario_e_token))
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Ana"


def test_vincular_responsavel_ao_aluno(client, usuario_e_token):
    criado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
    ).json()

    resp = client.post(
        f"/api/alunos/{criado['id']}/responsaveis",
        headers=headers(usuario_e_token),
        json={
            "nome": "Responsavel E2E",
            "telefone": "+5588999999999",
            "email": "responsavel.e2e@example.com",
            "parentesco": "responsavel",
        },
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["nome"] == "Responsavel E2E"
    assert data["telefone"] == "+5588999999999"
    assert data["email"] == "responsavel.e2e@example.com"

    aluno_resp = client.get(f"/api/alunos/{criado['id']}", headers=headers(usuario_e_token))
    assert aluno_resp.status_code == 200
    responsaveis = aluno_resp.json()["responsaveis"]
    assert len(responsaveis) == 1
    assert responsaveis[0]["id"] == data["id"]


def test_vincular_responsavel_nao_duplica_mesmo_telefone_ou_email(client, usuario_e_token):
    criado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
    ).json()
    payload = {
        "nome": "Responsavel E2E",
        "telefone": "+5588999999999",
        "email": "responsavel.e2e@example.com",
    }

    primeiro = client.post(
        f"/api/alunos/{criado['id']}/responsaveis",
        headers=headers(usuario_e_token),
        json=payload,
    )
    segundo = client.post(
        f"/api/alunos/{criado['id']}/responsaveis",
        headers=headers(usuario_e_token),
        json={**payload, "nome": "Outro Nome"},
    )

    assert primeiro.status_code == 201
    assert segundo.status_code == 201
    assert segundo.json()["id"] == primeiro.json()["id"]
    aluno_resp = client.get(f"/api/alunos/{criado['id']}", headers=headers(usuario_e_token))
    assert len(aluno_resp.json()["responsaveis"]) == 1


def test_vincular_responsavel_respeita_isolamento_entre_escolas(client):
    for email in ["a@test.com", "b@test.com"]:
        client.post("/api/auth/registrar", json={"nome": "N", "email": email, "senha": "senha123"})

    token_a = client.post("/api/auth/login", json={"email": "a@test.com", "senha": "senha123"}).json()["access_token"]
    token_b = client.post("/api/auth/login", json={"email": "b@test.com", "senha": "senha123"}).json()["access_token"]
    criado = client.post(
        "/api/alunos/",
        headers=headers(token_a),
        data=aluno_payload(nome="Aluno de A", numero_inscricao="A-RESP"),
    ).json()

    resp = client.post(
        f"/api/alunos/{criado['id']}/responsaveis",
        headers=headers(token_b),
        json={"nome": "Responsavel", "telefone": "88999999999"},
    )

    assert resp.status_code == 404


def test_buscar_aluno_nao_encontrado(client, usuario_e_token):
    resp = client.get("/api/alunos/9999", headers=headers(usuario_e_token))
    assert resp.status_code == 404


def test_atualizar_aluno(client, usuario_e_token):
    criado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
    ).json()
    resp = client.put(
        f"/api/alunos/{criado['id']}",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana Souza", numero_inscricao="2026-0099", telefone="88888880000"),
    )
    assert resp.status_code == 200
    assert resp.json()["nome"] == "Ana Souza"
    assert resp.json()["numero_inscricao"] == "2026-0099"


def test_atualizar_aluno_com_nome_novo_chama_sync(client, usuario_e_token, monkeypatch):
    from app.services.integration_service import IntegrationService
    from app.services.storage_service import StorageService

    chamadas = []

    def sync_fake(self, aluno, photo_file=None):
        chamadas.append(
            {
                "id": aluno.id,
                "external_id": aluno.external_id,
                "nome": aluno.nome,
                "empresa_id": aluno.empresa_id,
                "foto": aluno.foto,
                "photo_file": photo_file,
            }
        )

    monkeypatch.setattr(IntegrationService, "sync_aluno", sync_fake)
    monkeypatch.setattr(StorageService, "save_student_photo", lambda self, foto: stored_photo())
    monkeypatch.setattr(StorageService, "delete_photo", lambda self, url: None)

    criado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
        files={"foto": ("aluno.jpg", b"conteudo", "image/jpeg")},
    ).json()
    chamadas.clear()

    resp = client.put(
        f"/api/alunos/{criado['id']}",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana Souza"),
    )

    assert resp.status_code == 200
    assert len(chamadas) == 1
    assert chamadas[0]["external_id"] == str(criado["id"])
    assert chamadas[0]["nome"] == "Ana Souza"
    assert chamadas[0]["photo_file"] is None


def test_atualizar_aluno_com_foto_nova_chama_sync_com_photo_url(
    client,
    usuario_e_token,
    monkeypatch,
):
    from app.services.integration_service import IntegrationService
    from app.services.storage_service import StorageService

    chamadas = []
    nova_url = "https://res.cloudinary.com/demo/image/upload/nova.jpg"

    def sync_fake(self, aluno, photo_file=None):
        chamadas.append(
            {
                "external_id": aluno.external_id,
                "nome": aluno.nome,
                "empresa_id": aluno.empresa_id,
                "foto": aluno.foto,
                "photo_file": photo_file,
            }
        )

    monkeypatch.setattr(IntegrationService, "sync_aluno", sync_fake)
    monkeypatch.setattr(
        StorageService,
        "save_student_photo",
        lambda self, foto: stored_photo(
            url=nova_url,
            content=b"nova-foto",
            filename="nova.jpg",
            content_type="image/jpeg",
        ),
    )
    monkeypatch.setattr(StorageService, "delete_photo", lambda self, url: None)

    criado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
    ).json()
    chamadas.clear()

    resp = client.put(
        f"/api/alunos/{criado['id']}",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
        files={"foto": ("nova.jpg", b"conteudo", "image/jpeg")},
    )

    assert resp.status_code == 200
    assert resp.json()["foto"] == nova_url
    assert len(chamadas) == 1
    assert chamadas[0]["external_id"] == str(criado["id"])
    assert chamadas[0]["foto"] == nova_url
    assert chamadas[0]["photo_file"].content == b"nova-foto"


def test_atualizar_aluno_nao_desfaz_update_se_sync_falhar(
    client,
    usuario_e_token,
    monkeypatch,
):
    from app.services.integration_service import IntegrationService
    from app.services.storage_service import StorageService

    def sync_com_erro(self, aluno, photo_file=None):
        raise RuntimeError("servico externo indisponivel")

    monkeypatch.setattr(IntegrationService, "sync_aluno", sync_com_erro)
    monkeypatch.setattr(StorageService, "save_student_photo", lambda self, foto: stored_photo())
    monkeypatch.setattr(StorageService, "delete_photo", lambda self, url: None)

    criado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
        files={"foto": ("aluno.jpg", b"conteudo", "image/jpeg")},
    ).json()

    resp = client.put(
        f"/api/alunos/{criado['id']}",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana Atualizada"),
    )

    assert resp.status_code == 200
    assert resp.json()["nome"] == "Ana Atualizada"


def test_atualizar_aluno_rejeita_campos_em_branco(client, usuario_e_token):
    criado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
    ).json()
    resp = client.put(
        f"/api/alunos/{criado['id']}",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="   "),
    )
    assert resp.status_code == 422


def test_deletar_aluno(client, usuario_e_token):
    criado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
    ).json()
    resp = client.delete(f"/api/alunos/{criado['id']}", headers=headers(usuario_e_token))
    assert resp.status_code == 204

    resp = client.get(f"/api/alunos/{criado['id']}", headers=headers(usuario_e_token))
    assert resp.status_code == 404


def test_deletar_aluno_chama_exclusao_biometrica(client, usuario_e_token, monkeypatch):
    from app.services.integration_service import IntegrationService

    chamadas = []

    def delete_fake(self, aluno):
        chamadas.append(
            {
                "id": aluno.id,
                "external_id": aluno.external_id,
                "empresa_id": aluno.empresa_id,
            }
        )

    monkeypatch.setattr(IntegrationService, "delete_aluno_biometria", delete_fake)

    criado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
    ).json()

    resp = client.delete(f"/api/alunos/{criado['id']}", headers=headers(usuario_e_token))

    assert resp.status_code == 204
    assert chamadas == [
        {
            "id": criado["id"],
            "external_id": str(criado["id"]),
            "empresa_id": criado["user_id"],
        }
    ]


def test_deletar_aluno_falha_biometrica_nao_vaza_segredo(
    client,
    usuario_e_token,
    monkeypatch,
    caplog,
):
    from app.services.integration_service import IntegrationService

    def delete_com_erro(self, aluno):
        raise RuntimeError("segredo-super-sensivel")

    monkeypatch.setattr(IntegrationService, "delete_aluno_biometria", delete_com_erro)

    criado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana"),
    ).json()

    with caplog.at_level("ERROR"):
        resp = client.delete(f"/api/alunos/{criado['id']}", headers=headers(usuario_e_token))

    assert resp.status_code == 204
    assert "segredo-super-sensivel" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_isolamento_entre_usuarios(client):
    """Usuário B não pode ver alunos do usuário A."""
    for email in ["a@test.com", "b@test.com"]:
        client.post("/api/auth/registrar", json={"nome": "N", "email": email, "senha": "senha123"})

    token_a = client.post("/api/auth/login", json={"email": "a@test.com", "senha": "senha123"}).json()["access_token"]
    token_b = client.post("/api/auth/login", json={"email": "b@test.com", "senha": "senha123"}).json()["access_token"]

    criado = client.post(
        "/api/alunos/",
        headers=headers(token_a),
        data=aluno_payload(nome="Aluno de A", numero_inscricao="A-001", telefone="88000000000"),
    ).json()

    resp = client.get(f"/api/alunos/{criado['id']}", headers=headers(token_b))
    assert resp.status_code == 404


def test_numero_inscricao_duplicado_na_mesma_escola(client, usuario_e_token):
    primeiro = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Ana", numero_inscricao="MAT-100"),
    )
    assert primeiro.status_code == 201

    duplicado = client.post(
        "/api/alunos/",
        headers=headers(usuario_e_token),
        data=aluno_payload(nome="Bruno", numero_inscricao="MAT-100", telefone="88999991111"),
    )
    assert duplicado.status_code == 400
    assert duplicado.json()["erro"] == "Numero de inscricao ja cadastrado para esta escola"


def test_numero_inscricao_pode_repetir_em_escolas_diferentes(client):
    for email in ["a@test.com", "b@test.com"]:
        client.post("/api/auth/registrar", json={"nome": "N", "email": email, "senha": "senha123"})

    token_a = client.post("/api/auth/login", json={"email": "a@test.com", "senha": "senha123"}).json()["access_token"]
    token_b = client.post("/api/auth/login", json={"email": "b@test.com", "senha": "senha123"}).json()["access_token"]

    resp_a = client.post(
        "/api/alunos/",
        headers=headers(token_a),
        data=aluno_payload(nome="Aluno A", numero_inscricao="MAT-200"),
    )
    resp_b = client.post(
        "/api/alunos/",
        headers=headers(token_b),
        data=aluno_payload(nome="Aluno B", numero_inscricao="MAT-200", telefone="88999992222"),
    )

    assert resp_a.status_code == 201
    assert resp_b.status_code == 201


def test_sem_autenticacao(client):
    resp = client.get("/api/alunos/")
    assert resp.status_code == 401
