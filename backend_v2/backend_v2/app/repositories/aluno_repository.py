from datetime import date, datetime, time, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.models import Aluno, Usuario


class AlunoRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(
        self,
        user_id: int,
        turma: str | None = None,
        busca: str | None = None,
        biometria_status: str | None = None,
        sem_foto: bool | None = None,
        com_erro_biometria: bool | None = None,
        criado_de: date | None = None,
        criado_ate: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Aluno], int]:
        """Lista alunos com paginação.
        
        Args:
            user_id: ID do usuário
            turma: Filtrar por turma (opcional)
            busca: Buscar por nome ou número de inscrição (opcional)
            skip: Número de registros a pular
            limit: Número máximo de registros a retornar
            
        Returns:
            Tupla (alunos, total)
        """
        query = self.db.query(Aluno).filter(Aluno.empresa_id == user_id)
        query = self._apply_filters(
            query,
            turma=turma,
            busca=busca,
            biometria_status=biometria_status,
            sem_foto=sem_foto,
            com_erro_biometria=com_erro_biometria,
            criado_de=criado_de,
            criado_ate=criado_ate,
        )
        
        # Contar total ANTES de aplicar skip/limit
        total = query.count()
        
        # Aplicar paginação
        alunos = query.order_by(Aluno.nome).offset(skip).limit(limit).all()
        
        return alunos, total

    def list_all_with_usuario(
        self,
        skip: int = 0,
        limit: int = 50,
        empresa_id: int | None = None,
        turma: str | None = None,
        busca: str | None = None,
        biometria_status: str | None = None,
        sem_foto: bool | None = None,
        com_erro_biometria: bool | None = None,
        criado_de: date | None = None,
        criado_ate: date | None = None,
    ) -> tuple[list, int]:
        """Lista todos os alunos com informações do usuário e paginação.
        
        Args:
            skip: Número de registros a pular
            limit: Número máximo de registros a retornar
            
        Returns:
            Tupla (alunos_com_usuario, total)
        """
        query = (
            self.db.query(Aluno, Usuario.nome.label("usuario_nome"), Usuario.email.label("usuario_email"))
            .join(Usuario, Aluno.empresa_id == Usuario.id)
        )
        if empresa_id is not None:
            query = query.filter(Aluno.empresa_id == empresa_id)
        query = self._apply_filters(
            query,
            turma=turma,
            busca=busca,
            biometria_status=biometria_status,
            sem_foto=sem_foto,
            com_erro_biometria=com_erro_biometria,
            criado_de=criado_de,
            criado_ate=criado_ate,
        )
        
        # Contar total ANTES de aplicar skip/limit
        total = query.count()
        
        # Aplicar paginação
        result = query.order_by(Aluno.nome).offset(skip).limit(limit).all()
        
        return result, total

    def _apply_filters(
        self,
        query,
        *,
        turma: str | None = None,
        busca: str | None = None,
        biometria_status: str | None = None,
        sem_foto: bool | None = None,
        com_erro_biometria: bool | None = None,
        criado_de: date | None = None,
        criado_ate: date | None = None,
    ):
        if turma:
            query = query.filter(Aluno.turma == turma)
        if busca:
            termo = f"%{busca.strip()}%"
            query = query.filter(or_(Aluno.nome.ilike(termo), Aluno.numero_inscricao.ilike(termo)))
        if biometria_status:
            query = query.filter(Aluno.biometria_status == biometria_status)
        if sem_foto is True:
            query = query.filter(or_(Aluno.foto.is_(None), Aluno.foto == ""))
        elif sem_foto is False:
            query = query.filter(Aluno.foto.isnot(None), Aluno.foto != "")
        if com_erro_biometria is True:
            query = query.filter(Aluno.biometria_error.isnot(None), Aluno.biometria_error != "")
        elif com_erro_biometria is False:
            query = query.filter(or_(Aluno.biometria_error.is_(None), Aluno.biometria_error == ""))
        if criado_de:
            query = query.filter(Aluno.criado_em >= datetime.combine(criado_de, time.min, tzinfo=timezone.utc))
        if criado_ate:
            query = query.filter(Aluno.criado_em <= datetime.combine(criado_ate, time.max, tzinfo=timezone.utc))
        return query

    def list_turmas_by_user(self, user_id: int) -> list[str]:
        resultado = (
            self.db.query(Aluno.turma)
            .filter(Aluno.empresa_id == user_id, Aluno.turma.isnot(None), Aluno.turma != "")
            .distinct()
            .order_by(Aluno.turma)
            .all()
        )
        return [r.turma for r in resultado]

    def list_all_by_user(self, user_id: int) -> list[Aluno]:
        return self.db.query(Aluno).filter(Aluno.empresa_id == user_id).all()

    def get(self, aluno_id: int) -> Aluno | None:
        return self.db.query(Aluno).filter(Aluno.id == aluno_id).first()

    def get_by_user(self, aluno_id: int, user_id: int) -> Aluno | None:
        return self.db.query(Aluno).filter(Aluno.id == aluno_id, Aluno.empresa_id == user_id).first()

    def get_by_external_id(self, external_id: str, empresa_id: int) -> Aluno | None:
        return (
            self.db.query(Aluno)
            .filter(Aluno.external_id == external_id, Aluno.empresa_id == empresa_id)
            .first()
        )

    def count_all(self) -> int:
        return self.db.query(Aluno).count()

    def count_by_user(self, user_id: int) -> int:
        return self.db.query(Aluno).filter(Aluno.empresa_id == user_id).count()

    def count_by_user_map(self) -> dict[int, int]:
        resultado = (
            self.db.query(Aluno.empresa_id, func.count(Aluno.id))
            .group_by(Aluno.empresa_id)
            .all()
        )
        return {empresa_id: total for empresa_id, total in resultado}

    def numero_inscricao_exists(
        self,
        user_id: int,
        numero_inscricao: str,
        aluno_id: int | None = None,
    ) -> bool:
        query = self.db.query(Aluno).filter(
            Aluno.empresa_id == user_id,
            Aluno.numero_inscricao == numero_inscricao,
        )
        if aluno_id is not None:
            query = query.filter(Aluno.id != aluno_id)
        return query.first() is not None

    def add(self, aluno: Aluno) -> Aluno:
        self.db.add(aluno)
        return aluno

    def delete(self, aluno: Aluno) -> None:
        self.db.delete(aluno)
