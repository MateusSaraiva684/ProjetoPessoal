def headers(token):
    return {"Authorization": f"Bearer {token}"}


def login_admin(client) -> str:
    resp = client.post(
        "/api/auth/login",
        json={"email": "admin@admin.com", "senha": "Mateusqwe123"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def criar_usuario_e_token(client, nome: str, email: str) -> tuple[int, str]:
    client.post(
        "/api/auth/registrar",
        json={"nome": nome, "email": email, "senha": "senha123"},
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "senha": "senha123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    return data["usuario"]["id"], data["access_token"]


def criar_aluno(client, token: str, nome: str, numero_inscricao: str) -> dict:
    resp = client.post(
        "/api/alunos/",
        headers=headers(token),
        data={
            "nome": nome,
            "numero_inscricao": numero_inscricao,
            "telefone": "88999990000",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_admin_deleta_usuario_com_alunos(client):
    client.post(
        "/api/auth/registrar",
        json={"nome": "Usuario", "email": "usuario@test.com", "senha": "senha123"},
    )
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "usuario@test.com", "senha": "senha123"},
    )
    user_data = login_resp.json()
    user_id = user_data["usuario"]["id"]

    aluno_resp = client.post(
        "/api/alunos/",
        headers=headers(user_data["access_token"]),
        data={
            "nome": "Aluno",
            "numero_inscricao": "MAT-900",
            "telefone": "88999990000",
        },
    )
    assert aluno_resp.status_code == 201

    admin_token = login_admin(client)
    resp = client.delete(
        f"/api/admin/usuarios/{user_id}",
        headers=headers(admin_token),
    )

    assert resp.status_code == 200
    assert resp.json()["mensagem"] == "Usuario removido com sucesso"


def test_admin_listar_alunos_rejeita_limit_invalido(client):
    admin_token = login_admin(client)
    resp = client.get(
        "/api/admin/alunos?limit=-1&page=1",
        headers=headers(admin_token),
    )

    assert resp.status_code == 422


def test_admin_lista_escolas_com_total_de_alunos(client):
    escola_a_id, token_a = criar_usuario_e_token(client, "Escola A", "escola-a@test.com")
    escola_b_id, token_b = criar_usuario_e_token(client, "Escola B", "escola-b@test.com")
    criar_aluno(client, token_a, "Ana", "A-001")
    criar_aluno(client, token_a, "Alice", "A-002")
    criar_aluno(client, token_b, "Bruno", "B-001")

    admin_token = login_admin(client)
    resp = client.get("/api/admin/escolas", headers=headers(admin_token))

    assert resp.status_code == 200
    escolas = {escola["id"]: escola for escola in resp.json()}
    assert escola_a_id in escolas
    assert escola_b_id in escolas
    assert escolas[escola_a_id]["nome"] == "Escola A"
    assert escolas[escola_a_id]["total_alunos"] == 2
    assert escolas[escola_b_id]["total_alunos"] == 1
    assert all(not escola.get("is_superuser", False) for escola in resp.json())


def test_admin_lista_alunos_por_escola(client):
    escola_a_id, token_a = criar_usuario_e_token(client, "Escola A", "escola-a@test.com")
    escola_b_id, token_b = criar_usuario_e_token(client, "Escola B", "escola-b@test.com")
    criar_aluno(client, token_a, "Ana", "A-001")
    criar_aluno(client, token_b, "Bruno", "B-001")

    admin_token = login_admin(client)
    resp = client.get(
        f"/api/admin/escolas/{escola_a_id}/alunos",
        headers=headers(admin_token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["paginacao"]["total"] == 1
    assert [aluno["nome"] for aluno in body["data"]] == ["Ana"]
    assert body["data"][0]["empresa_id"] == escola_a_id


def test_admin_lista_alunos_com_filtro_empresa_id(client):
    escola_a_id, token_a = criar_usuario_e_token(client, "Escola A", "escola-a@test.com")
    _, token_b = criar_usuario_e_token(client, "Escola B", "escola-b@test.com")
    criar_aluno(client, token_a, "Ana", "A-001")
    criar_aluno(client, token_b, "Bruno", "B-001")

    admin_token = login_admin(client)
    resp = client.get(
        f"/api/admin/alunos?empresa_id={escola_a_id}",
        headers=headers(admin_token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["paginacao"]["total"] == 1
    assert [aluno["nome"] for aluno in body["data"]] == ["Ana"]


def test_admin_nao_pode_desativar_ou_trocar_email_do_proprio_perfil(client):
    admin_token = login_admin(client)
    admin_id = client.get("/api/auth/me", headers=headers(admin_token)).json()["id"]

    desativar = client.patch(
        f"/api/admin/usuarios/{admin_id}",
        headers=headers(admin_token),
        json={"ativo": False},
    )
    assert desativar.status_code == 403

    trocar_email = client.patch(
        f"/api/admin/usuarios/{admin_id}",
        headers=headers(admin_token),
        json={"email": "novo-admin@test.com"},
    )
    assert trocar_email.status_code == 403


def test_admin_auditoria_registra_alteracao_sensivel(client):
    admin_token = login_admin(client)
    user_id, user_token = criar_usuario_e_token(client, "Usuario", "auditoria@test.com")

    response = client.patch(
        f"/api/admin/usuarios/{user_id}/senha",
        headers=headers(admin_token),
        json={"nova_senha": "nova-senha-123"},
    )
    assert response.status_code == 200

    logs = client.get("/api/admin/audit-logs", headers=headers(admin_token))
    assert logs.status_code == 200
    assert any(
        item["action"] == "admin.user.password_reset"
        and item["resource_id"] == str(user_id)
        for item in logs.json()
    )
