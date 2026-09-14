#!/usr/bin/env python3
"""
CLI para gerenciamento do sistema.
Uso: python cli.py sync-admin
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def sync_admin():
    """Sincroniza credenciais do admin com .env"""
    from sqlalchemy.orm import Session
    from app.database.session import SessionLocal
    from app.models.models import Usuario
    from app.core.security import hash_senha, verificar_senha
    from app.core.config import settings
    
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        logger.error("ADMIN_EMAIL ou ADMIN_PASSWORD nao configurados em .env")
        return False
    
    db: Session = SessionLocal()
    try:
        admin = db.query(Usuario).filter(Usuario.email == settings.ADMIN_EMAIL).first()
        
        if not admin:
            logger.info("Admin nao encontrado no banco, criando novo admin...")
            admin = Usuario(
                nome="Administrador",
                email=settings.ADMIN_EMAIL,
                senha=hash_senha(settings.ADMIN_PASSWORD),
                is_superuser=True,
                ativo=True,
            )
            db.add(admin)
            db.flush()
            db.commit()
            db.refresh(admin)
            logger.info("Admin criado com sucesso: %s", settings.ADMIN_EMAIL)
            return True
        
        if verificar_senha(settings.ADMIN_PASSWORD, admin.senha):
            logger.info("Admin ja esta sincronizado com .env")
            return True
        
        logger.info("Sincronizando admin existente...")
        admin.senha = hash_senha(settings.ADMIN_PASSWORD)
        admin.is_superuser = True
        admin.ativo = True
        db.flush()
        db.commit()
        logger.info("Admin sincronizado com sucesso: %s", settings.ADMIN_EMAIL)
        return True
        
    except Exception as e:
        logger.error(f"Erro: {str(e)}", exc_info=True)
        return False
    finally:
        db.close()

def main():
    if len(sys.argv) < 2:
        print("Uso: python cli.py <comando>")
        print("\nComandos disponíveis:")
        print("  sync-admin    Sincronizar credenciais do admin com .env")
        return 1
    
    command = sys.argv[1]
    
    if command == "sync-admin":
        success = sync_admin()
        return 0 if success else 1
    else:
        logger.error(f"Comando desconhecido: {command}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
