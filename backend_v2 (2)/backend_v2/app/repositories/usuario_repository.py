from sqlalchemy.orm import Session

from app.models.models import RefreshToken, Usuario


class UsuarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int, ativo: bool | None = None) -> Usuario | None:
        query = self.db.query(Usuario).filter(Usuario.id == user_id)
        if ativo is not None:
            query = query.filter(Usuario.ativo == ativo)
        return query.first()

    def get_by_email(self, email: str, ativo: bool | None = None) -> Usuario | None:
        query = self.db.query(Usuario).filter(Usuario.email == email)
        if ativo is not None:
            query = query.filter(Usuario.ativo == ativo)
        return query.first()

    def list_all(self) -> list[Usuario]:
        return self.db.query(Usuario).order_by(Usuario.id.desc()).all()

    def list_escolas(self) -> list[Usuario]:
        return (
            self.db.query(Usuario)
            .filter(Usuario.is_superuser == False)
            .order_by(Usuario.nome)
            .all()
        )

    def count_all(self) -> int:
        return self.db.query(Usuario).count()

    def count_active(self) -> int:
        return self.db.query(Usuario).filter(Usuario.ativo == True).count()

    def add(self, usuario: Usuario) -> Usuario:
        self.db.add(usuario)
        return usuario

    def delete(self, usuario: Usuario) -> None:
        self.db.delete(usuario)

    def email_exists_for_other_user(self, email: str, user_id: int) -> bool:
        return (
            self.db.query(Usuario)
            .filter(Usuario.email == email, Usuario.id != user_id)
            .first()
            is not None
        )


class RefreshTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, refresh_token: RefreshToken) -> RefreshToken:
        self.db.add(refresh_token)
        return refresh_token

    def get_by_token(self, token: str) -> RefreshToken | None:
        return self.db.query(RefreshToken).filter(RefreshToken.token == token).first()
