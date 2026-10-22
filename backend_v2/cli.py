#!/usr/bin/env python3
"""CLI para tarefas administrativas seguras."""

import argparse
import getpass
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def create_admin(email: str | None = None, nome: str | None = None) -> bool:
    """Cria ou redefine um administrador sem persistir a senha em ambiente."""
    from sqlalchemy.orm import Session
    from app.database.session import SessionLocal
    from app.models.models import Usuario
    from app.core.security import hash_senha
    
    email = (email or input("E-mail do administrador: ")).strip().lower()
    nome = (nome or input("Nome do administrador [Administrador]: ").strip() or "Administrador")
    senha = getpass.getpass("Nova senha (minimo 12 caracteres): ")
    confirmacao = getpass.getpass("Confirme a senha: ")

    if len(senha) < 12:
        logger.error("A senha deve ter pelo menos 12 caracteres")
        return False
    if senha != confirmacao:
        logger.error("As senhas nao conferem")
        return False
    
    db: Session = SessionLocal()
    try:
        admin = db.query(Usuario).filter(Usuario.email == email).first()
        
        if not admin:
            logger.info("Admin nao encontrado no banco, criando novo admin...")
            admin = Usuario(
                nome=nome,
                email=email,
                senha=hash_senha(senha),
                is_superuser=True,
                role="superadmin",
                ativo=True,
            )
            db.add(admin)
            db.flush()
            db.commit()
            db.refresh(admin)
            logger.info("Admin criado com sucesso: %s", email)
            return True
        
        logger.info("Atualizando administrador existente...")
        admin.nome = nome
        admin.senha = hash_senha(senha)
        admin.is_superuser = True
        admin.role = "superadmin"
        admin.ativo = True
        db.flush()
        db.commit()
        logger.info("Admin atualizado com sucesso: %s", email)
        return True
        
    except Exception as e:
        logger.error(f"Erro: {str(e)}", exc_info=True)
        return False
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Tarefas administrativas do sistema")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create-admin", help="criar ou redefinir o administrador")
    create_parser.add_argument("--email")
    create_parser.add_argument("--nome")
    args = parser.parse_args()

    if args.command == "create-admin":
        return 0 if create_admin(args.email, args.nome) else 1
    return 1

if __name__ == "__main__":
    sys.exit(main())
