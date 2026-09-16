#!/usr/bin/env python
"""
Script de Backup Automático para PostgreSQL

Uso:
    python backup.py                    # Backup único
    python backup.py --schedule daily   # Backup agendado (daily)

Requer variáveis de ambiente:
    DATABASE_URL: postgresql://user:password@host:port/dbname
    BACKUP_DIR: Diretório para armazenar backups (padrão: ./backups)
"""

import os
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path
import argparse
from urllib.parse import urlparse

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackupManager:
    def __init__(self, database_url: str, backup_dir: str | None = None):
        """
        Args:
            database_url: PostgreSQL connection string
            backup_dir: Diretório para armazenar backups
        """
        self.database_url = database_url
        self.backup_dir = Path(backup_dir or os.getenv("BACKUP_DIR", "./backups"))
        self.backup_dir.mkdir(exist_ok=True, parents=True)
        
        # Parse database connection
        parsed = urlparse(database_url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 5432
        self.username = parsed.username or "postgres"
        self.password = parsed.password or ""
        self.database = parsed.path.lstrip("/") or "escola_dev"
        
    def criar_backup(self) -> str:
        """Cria um novo backup do banco de dados.
        
        Returns:
            Caminho do arquivo de backup criado
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"backup_escola_{timestamp}.sql"
        
        logger.info(f"Iniciando backup para {backup_file}")
        
        # Preparar comando pg_dump
        cmd = [
            "pg_dump",
            f"--host={self.host}",
            f"--port={self.port}",
            f"--username={self.username}",
            "--no-password",
            "--format=plain",
            "--verbose",
            "--no-owner",
            "--no-acl",
            self.database,
        ]
        
        # Definir password
        env = os.environ.copy()
        if self.password:
            env["PGPASSWORD"] = self.password
        
        try:
            with open(backup_file, "w") as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True,
                    timeout=300  # 5 minutos timeout
                )
            
            if result.returncode != 0:
                raise Exception(f"pg_dump falhou: {result.stderr}")
            
            file_size = backup_file.stat().st_size
            logger.info(f"✅ Backup criado com sucesso: {backup_file} ({file_size / 1024 / 1024:.2f}MB)")
            
            return str(backup_file)
            
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Backup timeout (excedeu 5 minutos)")
            backup_file.unlink(missing_ok=True)
            raise
        except Exception as e:
            logger.error(f"❌ Erro ao criar backup: {e}")
            backup_file.unlink(missing_ok=True)
            raise
    
    def limpar_backups_antigos(self, dias_retencao: int | None = None) -> int:
        """Remove backups mais antigos que o período de retenção.
        
        Args:
            dias_retencao: Número de dias a manter backups (padrão: 30)
            
        Returns:
            Número de backups removidos
        """
        from datetime import timedelta
        
        dias_retencao = dias_retencao or int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
        if dias_retencao < 1:
            raise ValueError("BACKUP_RETENTION_DAYS deve ser maior que zero")
        cutoff_date = datetime.now() - timedelta(days=dias_retencao)
        removidos = 0
        
        for backup_file in self.backup_dir.glob("backup_escola_*.sql"):
            if backup_file.stat().st_mtime < cutoff_date.timestamp():
                logger.info(f"Removendo backup antigo: {backup_file.name}")
                backup_file.unlink()
                removidos += 1
        
        if removidos > 0:
            logger.info(f"✅ {removidos} backup(s) antigos removido(s)")
        
        return removidos
    
    def restaurar_backup(self, backup_file: str) -> None:
        """Restaura um backup do banco de dados.
        
        AVISO: Esta operação sobrescreverá dados existentes!
        
        Args:
            backup_file: Caminho do arquivo de backup
        """
        backup_path = Path(backup_file)
        
        if not backup_path.exists():
            logger.error(f"❌ Arquivo de backup não encontrado: {backup_file}")
            raise FileNotFoundError(f"Backup não encontrado: {backup_file}")
        
        logger.warning(f"⚠️  Restaurando backup: {backup_path.name}")
        logger.warning("⚠️  AVISO: Dados existentes serão sobrescritos!")
        
        # Pedir confirmação
        resposta = input("Deseja continuar? (sim/não): ").strip().lower()
        if resposta != "sim":
            logger.info("Restauração cancelada")
            return
        
        # Preparar comando psql
        cmd = [
            "psql",
            f"--host={self.host}",
            f"--port={self.port}",
            f"--username={self.username}",
            "--no-password",
            self.database,
        ]
        
        # Definir password
        env = os.environ.copy()
        if self.password:
            env["PGPASSWORD"] = self.password
        
        try:
            with open(backup_path, "r") as f:
                result = subprocess.run(
                    cmd,
                    stdin=f,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True,
                    timeout=600  # 10 minutos timeout
                )
            
            if result.returncode != 0:
                raise Exception(f"psql falhou: {result.stderr}")
            
            logger.info(f"✅ Backup restaurado com sucesso!")
            
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Restauração timeout (excedeu 10 minutos)")
            raise
        except Exception as e:
            logger.error(f"❌ Erro ao restaurar backup: {e}")
            raise
    
    def listar_backups(self) -> list:
        """Lista todos os backups disponíveis.
        
        Returns:
            Lista de arquivos de backup
        """
        backups = sorted(
            self.backup_dir.glob("backup_escola_*.sql"),
            reverse=True
        )
        
        if not backups:
            logger.info("Nenhum backup encontrado")
            return []
        
        logger.info("📋 Backups disponíveis:")
        for i, backup in enumerate(backups, 1):
            size_mb = backup.stat().st_size / 1024 / 1024
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            logger.info(f"  {i}. {backup.name} ({size_mb:.2f}MB) - {mtime.strftime('%d/%m/%Y %H:%M:%S')}")
        
        return [str(b) for b in backups]


def main():
    parser = argparse.ArgumentParser(
        description="Backup automático para PostgreSQL"
    )
    parser.add_argument(
        "--action",
        choices=["backup", "restore", "list", "cleanup"],
        default="backup",
        help="Ação a executar (padrão: backup)"
    )
    parser.add_argument(
        "--file",
        help="Arquivo de backup para restaurar (required para restore)"
    )
    parser.add_argument(
        "--schedule",
        choices=["once", "daily", "weekly"],
        help="Agendar backup automático (requer APScheduler)"
    )
    parser.add_argument(
        "--backup-dir",
        default=os.getenv("BACKUP_DIR", "./backups"),
        help="Diretório para armazenar backups"
    )
    
    args = parser.parse_args()
    
    # Obter DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("❌ Variável DATABASE_URL não configurada!")
        sys.exit(1)
    
    # Criar manager
    manager = BackupManager(database_url, args.backup_dir)
    
    try:
        if args.action == "backup":
            manager.criar_backup()
            manager.limpar_backups_antigos()
        
        elif args.action == "restore":
            if not args.file:
                logger.error("❌ Arquivo de backup requerido para restore!")
                sys.exit(1)
            manager.restaurar_backup(args.file)
        
        elif args.action == "list":
            manager.listar_backups()
        
        elif args.action == "cleanup":
            manager.limpar_backups_antigos()
        
        if args.schedule:
            agendar_backup(manager, args.schedule)
    
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        sys.exit(1)


def agendar_backup(manager: BackupManager, schedule: str):
    """Agenda backups automáticos usando APScheduler."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ImportError:
        logger.error("❌ APScheduler não instalado. Execute: pip install apscheduler")
        sys.exit(1)
    
    scheduler = BlockingScheduler()
    
    if schedule == "daily":
        logger.info("⏱️  Backup agendado para rodar diariamente às 02:00")
        scheduler.add_job(manager.criar_backup, "cron", hour=2, minute=0)
    
    elif schedule == "weekly":
        logger.info("⏱️  Backup agendado para rodar semanalmente às segundas 02:00")
        scheduler.add_job(manager.criar_backup, "cron", day_of_week=0, hour=2, minute=0)
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler interrompido pelo usuário")


if __name__ == "__main__":
    main()
