from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")
_is_local = _is_sqlite or any(h in DATABASE_URL for h in ("localhost", "127.0.0.1"))

if _is_sqlite:
    # SQLite: não suporta sslmode; check_same_thread necessário para testes
    connect_args = {"check_same_thread": False}
elif _is_local:
    # PostgreSQL local: sem SSL
    connect_args = {}
else:
    # PostgreSQL remoto (Render, Supabase, etc): exige SSL
    connect_args = {"sslmode": "require"}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
