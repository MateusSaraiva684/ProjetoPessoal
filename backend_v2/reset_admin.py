#!/usr/bin/env python3
"""
Script utilitário: Força sincronização/reset de credenciais do admin
Uso: python reset_admin.py
"""

import sys
import logging
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def reset_admin():
    """Reseta hash da senha do admin para sincronizar com .env"""
    from app.database.session import SessionLocal
    from app.models.models import Usuario
    from app.core.security import hash_senha
    from app.core.config import settings
    
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        logger.error("ADMIN_EMAIL ou ADMIN_PASSWORD nao configurados em .env")
        return False
    
    db: Session = SessionLocal()
    try:
        # Busca admin
        admin = db.query(Usuario).filter(Usuario.email == settings.ADMIN_EMAIL).first()
        
        if not admin:
            logger.error(f"Usuario admin '{settings.ADMIN_EMAIL}' nao encontrado no banco")
            return False
        
        # Computa novo hash
        novo_hash = hash_senha(settings.ADMIN_PASSWORD)
        # Atualiza
        admin.senha = novo_hash
        admin.is_superuser = True
        admin.ativo = True
        
        db.flush()
        db.commit()
        
        logger.info("Admin sincronizado com sucesso!")
        logger.info(f"   Email: {settings.ADMIN_EMAIL}")
        logger.info(f"   Superuser: True")
        logger.info("\nAgora voce pode fazer login com:")
        logger.info(f"   Email: {settings.ADMIN_EMAIL}")
        logger.info("   Senha: use o valor configurado em ADMIN_PASSWORD")
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao resetar admin: {str(e)}", exc_info=True)
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = reset_admin()
    sys.exit(0 if success else 1)
