#!/usr/bin/env python3
"""
Script auxiliar para migração Render → Northflank
Use este script para automatizar tarefas comuns.
"""

import os
import sys
import secrets
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Cores para output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")

def check_docker():
    """Verifica se Docker está instalado"""
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
        print_success("Docker encontrado")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_error("Docker não encontrado. Instale em https://docker.com")
        return False

def build_docker():
    """Constrói a imagem Docker localmente"""
    print_info("Iniciando build Docker...")
    try:
        result = subprocess.run(
            ["docker", "build", "-t", "backend:latest", "."],
            cwd=".",
        )
        if result.returncode == 0:
            print_success("Imagem Docker construída com sucesso!")
            return True
        else:
            print_error("Erro ao construir imagem Docker")
            return False
    except Exception as e:
        print_error(f"Erro: {e}")
        return False

def generate_secret_key():
    """Gera uma SECRET_KEY segura"""
    key = secrets.token_urlsafe(32)
    print_success(f"SECRET_KEY gerada: {key}")
    return key

def check_files():
    """Verifica arquivos necessários"""
    required_files = [
        "Dockerfile",
        ".dockerignore",
        "requirements.txt",
        "main.py",
    ]
    
    print_info("Verificando arquivos necessários...")
    all_found = True
    
    for file in required_files:
        if Path(file).exists():
            print_success(f"{file} encontrado")
        else:
            print_error(f"{file} não encontrado")
            all_found = False
    
    return all_found

def check_env_vars():
    """Verifica variáveis de ambiente"""
    load_dotenv()
    
    required_vars = [
        "DATABASE_URL",
        "SECRET_KEY",
        "ADMIN_EMAIL",
        "ADMIN_PASSWORD",
        "FRONTEND_URL",
    ]
    
    print_info("Verificando variáveis de ambiente...")
    missing = []
    
    for var in required_vars:
        if os.getenv(var):
            print_success(f"{var} configurada")
        else:
            print_warning(f"{var} não configurada")
            missing.append(var)
    
    return len(missing) == 0

def run_tests():
    """Executa testes pytest"""
    print_info("Executando testes...")
    try:
        result = subprocess.run(
            ["pytest", "app/tests/", "-v"],
            capture_output=False,
        )
        if result.returncode == 0:
            print_success("Todos os testes passaram!")
            return True
        else:
            print_warning("Alguns testes falharam")
            return False
    except Exception as e:
        print_error(f"Erro ao executar testes: {e}")
        return False

def show_migration_checklist():
    """Exibe checklist de migração"""
    print(f"\n{Colors.BLUE}{'='*60}")
    print("📋 CHECKLIST DE MIGRAÇÃO RENDER → NORTHFLANK")
    print(f"{'='*60}{Colors.RESET}\n")
    
    checklist = [
        ("Conta Northflank criada", False),
        ("Repositório Git conectado", False),
        ("Dockerfile criado", True),  # Já criado por nós
        ("Docker testado localmente", False),
        ("PostgreSQL provisionado no Northflank", False),
        ("Redis provisionado no Northflank", False),
        ("Variáveis de ambiente configuradas", False),
        ("Secrets configurados", False),
        ("Database migrada do Render", False),
        ("Migrations rodadas", False),
        ("Admin sincronizado", False),
        ("Health check ativo", True),  # Já configurado no Dockerfile
        ("API respondendo em /docs", False),
        ("Frontend conectando corretamente", False),
    ]
    
    for idx, (item, done) in enumerate(checklist, 1):
        status = "✓" if done else "○"
        color = Colors.GREEN if done else Colors.YELLOW
        print(f"{color}[{status}] {idx:2d}. {item}{Colors.RESET}")
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")

def show_commands():
    """Exibe comandos úteis"""
    print(f"\n{Colors.BLUE}{'='*60}")
    print("💻 COMANDOS ÚTEIS")
    print(f"{'='*60}{Colors.RESET}\n")
    
    commands = {
        "Build local": "docker build -t backend:latest .",
        "Rodar localmente": "docker run -p 8000:8000 backend:latest",
        "Entrar no container": "docker run -it backend:latest /bin/bash",
        "Ver logs": "docker logs <container-id>",
        "Rodar migrations": "alembic upgrade head",
        "Sincronizar admin": "python cli.py sync-admin",
        "Executar testes": "pytest app/tests/ -v",
        "Gerar SECRET_KEY": "python -c 'import secrets; print(secrets.token_urlsafe(32))'",
    }
    
    for label, cmd in commands.items():
        print(f"{Colors.YELLOW}{label}:{Colors.RESET}")
        print(f"  {Colors.GREEN}{cmd}{Colors.RESET}\n")

def main():
    """Menu principal"""
    print(f"\n{Colors.BLUE}")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║     Migração Render → Northflank - Script Auxiliar       ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}\n")
    
    while True:
        print(f"{Colors.BLUE}Opções:{Colors.RESET}")
        print("1. Verificar arquivos necessários")
        print("2. Verificar Docker")
        print("3. Build local da imagem Docker")
        print("4. Verificar variáveis de ambiente")
        print("5. Executar testes")
        print("6. Gerar SECRET_KEY segura")
        print("7. Exibir checklist de migração")
        print("8. Exibir comandos úteis")
        print("9. Executar full check-up")
        print("0. Sair")
        
        choice = input(f"\n{Colors.YELLOW}Escolha uma opção (0-9): {Colors.RESET}").strip()
        
        if choice == "1":
            check_files()
        elif choice == "2":
            check_docker()
        elif choice == "3":
            if check_docker():
                build_docker()
        elif choice == "4":
            check_env_vars()
        elif choice == "5":
            run_tests()
        elif choice == "6":
            generate_secret_key()
        elif choice == "7":
            show_migration_checklist()
        elif choice == "8":
            show_commands()
        elif choice == "9":
            print_info("Executando full check-up...")
            print()
            check_files()
            print()
            check_docker()
            print()
            check_env_vars()
            print()
            if check_docker():
                build_docker()
        elif choice == "0":
            print_success("Até logo!")
            sys.exit(0)
        else:
            print_error("Opção inválida")
        
        input(f"\n{Colors.BLUE}Pressione Enter para continuar...{Colors.RESET}")
        print("\n" * 2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\nOperação cancelada pelo usuário")
        sys.exit(1)
