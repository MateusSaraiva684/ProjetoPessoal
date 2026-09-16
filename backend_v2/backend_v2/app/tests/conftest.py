import os
import pytest

# Define variáveis de ambiente ANTES de importar o app
# para que config.py não lance RuntimeError nos testes
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "chave-de-testes-nao-usar-em-producao")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("ADMIN_EMAIL", "admin@admin.com")
os.environ.setdefault("ADMIN_PASSWORD", "Mateusqwe123")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base, get_db
from main import app

TEST_DATABASE_URL = "sqlite:///./test.db"

engine_test = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
SessionTest = sessionmaker(bind=engine_test)


def override_get_db():
    db = SessionTest()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine_test)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = SessionTest()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def usuario_e_token(client):
    """Registra um usuário e retorna o access token."""
    client.post("/api/auth/registrar", json={
        "nome": "Teste",
        "email": "teste@email.com",
        "senha": "senha123"
    })
    resp = client.post("/api/auth/login", json={
        "email": "teste@email.com",
        "senha": "senha123"
    })
    return resp.json()["access_token"]
