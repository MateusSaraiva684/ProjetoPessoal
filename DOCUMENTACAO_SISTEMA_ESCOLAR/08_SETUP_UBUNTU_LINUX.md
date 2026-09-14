  # Setup na Máquina Atual: Ubuntu/Linux

**Data:** 08/09/2026  
**Escopo:** backend, frontend, bancos, recognition-service e testes

## Estado desta máquina

A máquina é Ubuntu x86_64, com memória e disco suficientes para o ambiente local. No diagnóstico inicial:

- Python disponível: 3.14.4;
- Python recomendado pelo projeto: 3.11;
- Node.js/npm: não instalados;
- Docker/Compose: não instalados;
- PostgreSQL client e Redis local: não instalados.

O Python 3.14 deve ser mantido fora dos ambientes do projeto: as versões fixadas de `numpy`, `opencv-python`, `insightface` e `onnxruntime` podem não ter wheels compatíveis.

## 1. Pacotes do sistema

Instale Git, Python 3.11, ferramentas de compilação e bibliotecas usadas por imagens:

```bash
sudo apt update
sudo apt install -y \
  git curl build-essential pkg-config \
  python3.11 python3.11-venv python3.11-dev \
  libgl1 libglib2.0-0
```

Se `python3.11` não estiver disponível no Ubuntu instalado, use `pyenv` ou instale uma versão 3.11 por um repositório confiável. Não substitua o `python3` do sistema sem necessidade.

Instale Node.js 20 LTS. Com `nvm`:

```bash
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20
node --version
npm --version
```

Instale Docker Engine e o plugin Compose seguindo o repositório oficial do Docker para Ubuntu. Depois confirme:

```bash
docker --version
docker compose version
sudo usermod -aG docker "$USER"
```

Faça logout/login após adicionar o usuário ao grupo `docker`. Até lá, os comandos Docker podem exigir `sudo`.

## 2. Backend e banco SaaS

Crie o ambiente Python do backend:

```bash
cd "/home/mateus/Área de trabalho/SaaS/backend_v2 (2)/backend_v2"
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Suba um PostgreSQL local separado para o banco SaaS:

```bash
docker volume create saas_postgres_data
docker run -d --name saas-postgres \
  -e POSTGRES_DB=escola \
  -e POSTGRES_USER=saas \
  -e POSTGRES_PASSWORD=saas_dev_password \
  -p 5432:5432 \
  -v saas_postgres_data:/var/lib/postgresql/data \
  postgres:15
```

O reconhecimento possui outro banco próprio; não use o banco do recognition-service como banco do backend.

Como já existe um `.env` nesta máquina, faça backup antes de alterar. Para uma configuração local nova:

```bash
cp .env.example .env.local.example
```

No `.env` usado pelo backend, confira pelo menos:

```env
DATABASE_URL=postgresql://saas:saas_dev_password@localhost:5432/escola
ENVIRONMENT=development
FRONTEND_URL=http://localhost:5173
RECOGNITION_SERVICE_URL=http://localhost:8001
FACE_RECOGNITION_SERVICE_URL=http://localhost:8001/api/recognize/sync
RECOGNITION_API_BASE_URL=http://localhost:8001
RECOGNITION_API_TOKEN=dev-recognition-key
RECOGNITION_WEBHOOK_SECRET=webhook-secret
NOTIFICATION_PROVIDER=log
```

Preencha `SECRET_KEY`, `ADMIN_EMAIL` e `ADMIN_PASSWORD` com valores locais. Para o fluxo completo de cadastro com foto, configure também Cloudinary válido; sem ele, os testes de autenticação podem funcionar, mas o fluxo biométrico por `photo_url` não ficará completo.

Rode migrações e sincronize o administrador:

```bash
alembic upgrade head
python cli.py sync-admin
```

Inicie o backend:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Verifique em outro terminal:

```bash
curl http://localhost:8000/health
```

## 3. Recognition-service, PostgreSQL/pgvector e Redis

O caminho recomendado é Docker Compose, pois o serviço depende de InsightFace, OpenCV, ONNX Runtime, PostgreSQL com pgvector, Redis e worker RQ:

```bash
cd "/home/mateus/Área de trabalho/SaaS/recognition-service"
cp .env.example .env
docker compose up -d --build
```

A stack sobe:

- API em `http://localhost:8001`;
- `recognition-db` com pgvector;
- `recognition-redis`;
- migration inicial;
- `recognition-worker` para jobs RQ.

Verifique:

```bash
curl http://localhost:8001/health
docker compose ps
docker compose logs --tail=100 api worker migrate
```

### Comunicação Docker com backend no Linux

O Compose usa `host.docker.internal` no webhook. O projeto já declara este mapeamento nos serviços `api` e `worker` para funcionar no Docker Engine Linux:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Se o arquivo tiver sido alterado localmente e o bloco não existir, adicione-o e recrie os containers:

```bash
docker compose up -d --build --force-recreate
```

O segredo `SAAS_WEBHOOK_SECRET` do recognition-service deve ser igual a `RECOGNITION_WEBHOOK_SECRET` do backend. O token do backend deve existir em `RECOGNITION_API_KEYS`.

Os valores padrão do Compose (`dev-recognition-key`, `webhook-secret`, senha `password` e `SCHOOL_ID=escola_1`) são somente para desenvolvimento local. Nunca os use em produção.

## 4. Frontend

Em outro terminal:

```bash
cd "/home/mateus/Área de trabalho/SaaS/frontend_v2"
npm install
printf 'VITE_API_URL=http://localhost:8000\n' > .env.local
npm run dev
```

Acesse `http://localhost:5173`. O `package.json` define `dev`, `build` e `preview`; não existe `npm start`.

## 5. Testes

### Backend

```bash
cd "/home/mateus/Área de trabalho/SaaS/backend_v2 (2)/backend_v2"
source .venv/bin/activate
pytest -q
```

A suíte usa SQLite e cria tabelas diretamente. Isso não substitui um teste com PostgreSQL e Alembic.

### Recognition-service

Os testes usam componentes Python e podem ser executados em um ambiente Python 3.11 com as dependências instaladas:

```bash
cd "/home/mateus/Área de trabalho/SaaS/recognition-service"
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Para validar o comportamento real, mantenha PostgreSQL/pgvector, Redis e o worker ativos. A suíte local não substitui o E2E.

### Frontend

```bash
cd "/home/mateus/Área de trabalho/SaaS/frontend_v2"
npm run build
```

Não há testes automatizados configurados no frontend.

### E2E entre os serviços

Com backend, frontend opcional, recognition-service, bancos, Redis e worker ativos, siga [E2E_RECOGNITION_FLOW.md](../backend_v2%20%282%29/backend_v2/docs/E2E_RECOGNITION_FLOW.md). O E2E precisa de credenciais de teste, imagens reais e Cloudinary quando o fluxo usar `photo_url`.

## 6. Ordem recomendada de inicialização

1. Docker Engine.
2. PostgreSQL SaaS (`saas-postgres`).
3. Backend: migrations e API na porta 8000.
4. Recognition-service: migration, API na porta 8001 e worker.
5. Frontend na porta 5173.
6. Testes unitários.
7. E2E somente em banco local/staging descartável.

## 7. Diagnóstico rápido

| Sintoma | Verificação |
|---|---|
| Backend não inicia | `.env`, `DATABASE_URL`, `SECRET_KEY` e `alembic upgrade head` |
| `Connection refused` no banco | `docker ps`, porta 5432 e volume `saas-postgres` |
| Recognition offline | `docker compose ps` e logs de `api`, `worker`, `migrate` |
| Webhook não chega ao backend | `extra_hosts`, URL, segredo e logs do worker |
| Biometria não fica `ready` | Cloudinary, token, `SCHOOL_ID`, imagem JPEG/PNG e logs dos dois serviços |
| Frontend não conecta | `VITE_API_URL=http://localhost:8000` e CORS/backend ativo |
| Teste facial falha instalando dependência | usar Python 3.11 ou executar o serviço via Docker |
