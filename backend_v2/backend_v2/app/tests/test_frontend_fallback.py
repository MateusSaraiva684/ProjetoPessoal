import main


def test_rota_frontend_redireciona_para_frontend_url(client, monkeypatch):
    monkeypatch.setattr(main.settings, "FRONTEND_URL", "https://frontend.example.com")

    resp = client.get("/alunos?pagina=2", follow_redirects=False)

    assert resp.status_code == 307
    assert resp.headers["location"] == "https://frontend.example.com/alunos?pagina=2"


def test_rota_api_inexistente_continua_404_json(client, monkeypatch):
    monkeypatch.setattr(main.settings, "FRONTEND_URL", "https://frontend.example.com")

    resp = client.get("/api/rota-inexistente")

    assert resp.status_code == 404
    assert resp.json() == {"erro": "Not Found"}


def test_rota_frontend_sem_frontend_url_continua_404_json(client, monkeypatch):
    monkeypatch.setattr(main.settings, "FRONTEND_URL", "")

    resp = client.get("/alunos")

    assert resp.status_code == 404
    assert resp.json() == {"erro": "Not Found"}
