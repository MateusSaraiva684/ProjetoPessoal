def test_registrar_sucesso(client):
    resp = client.post("/api/auth/registrar", json={
        "nome": "João",
        "email": "joao@email.com",
        "senha": "senha123"
    })
    assert resp.status_code == 201
    assert resp.json()["mensagem"] == "Conta criada com sucesso"


def test_registrar_email_duplicado(client):
    dados = {"nome": "João", "email": "joao@email.com", "senha": "senha123"}
    client.post("/api/auth/registrar", json=dados)
    resp = client.post("/api/auth/registrar", json=dados)
    assert resp.status_code == 400
    assert "E-mail já cadastrado" in resp.json()["erro"]


def test_registrar_senha_curta(client):
    resp = client.post("/api/auth/registrar", json={
        "nome": "João", "email": "joao@email.com", "senha": "123"
    })
    assert resp.status_code == 422  # Pydantic validation error


def test_login_sucesso(client):
    client.post("/api/auth/registrar", json={
        "nome": "João", "email": "joao@email.com", "senha": "senha123"
    })
    resp = client.post("/api/auth/login", json={
        "email": "joao@email.com", "senha": "senha123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "expires_in" in data
    assert data["usuario"]["email"] == "joao@email.com"


def test_login_credenciais_invalidas(client):
    resp = client.post("/api/auth/login", json={
        "email": "nao@existe.com", "senha": "errada"
    })
    assert resp.status_code == 401


def test_admin_login_fallback_cria_ou_sincroniza(client):
    resp = client.post("/api/auth/login", json={
        "email": "admin@admin.com",
        "senha": "Mateusqwe123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["usuario"]["email"] == "admin@admin.com"
    assert data["usuario"]["is_superuser"] is True

    # O admin deve ser persistido no banco após o login fallback
    resp2 = client.post("/api/auth/login", json={
        "email": "admin@admin.com",
        "senha": "Mateusqwe123",
    })
    assert resp2.status_code == 200
    assert resp2.json()["usuario"]["email"] == "admin@admin.com"


def test_me_autenticado(client, usuario_e_token):
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {usuario_e_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "teste@email.com"


def test_me_sem_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_refresh_token(client):
    client.post("/api/auth/registrar", json={
        "nome": "João", "email": "joao@email.com", "senha": "senha123"
    })
    login_resp = client.post("/api/auth/login", json={
        "email": "joao@email.com", "senha": "senha123"
    })
    # Pega o refresh token do cookie
    refresh_token = login_resp.cookies.get("refresh_token")
    assert refresh_token is not None

    # Usa o refresh token para obter novo access token
    resp = client.post("/api/auth/refresh", cookies={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
