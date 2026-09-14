#!/bin/bash


echo "==> Instalando dependências..."
pip install -r requirements.txt --quiet

echo "==> Rodando migrações do banco..."
alembic upgrade head

echo "==> Iniciando servidor..."
uvicorn main:app --host 0.0.0.0 --port $PORT
