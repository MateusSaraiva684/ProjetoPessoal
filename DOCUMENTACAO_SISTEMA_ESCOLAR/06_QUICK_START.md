# 🚀 QUICK START - SETUP PRÁTICO

**Público:** Novos Developers  
**Tempo total:** 30 minutos  
**Última atualização:** 08/09/2026

> **Escopo atual:** este guia cobre backend e frontend. O reconhecimento facial é um terceiro serviço; consulte [07_STATUS_ATUAL_2026.md](07_STATUS_ATUAL_2026.md) e [E2E_RECOGNITION_FLOW.md](../backend_v2%20%282%29/backend_v2/docs/E2E_RECOGNITION_FLOW.md) para a integração.

---

## ⏱️ ANTES DE COMEÇAR

### Requisitos
- ✅ Windows, macOS ou Linux
- ✅ Python 3.11+ (`python --version`)
- ✅ Node.js 18+ (`node --version`)
- ✅ Git (`git --version`)
- ✅ Postgr ESQL 15 OU Docker
- ✅ VS Code (recomendado)

### Verificar Instalação
```bash
# Python
python --version
# Esperado: Python 3.11+

# Node
node --version
# Esperado: v18.0+

# npm
npm --version
# Esperado: v9.0+

# Git
git --version
# Esperado: git version 2.x
```

---

## I. SETUP LOCAL (5 minutos)

### Passo 1: Clonar Repositório

```bash
# Navegar para pasta de projetos
cd ~/projetos  # ou seu diretório preferido

# Clonar repositório
git clone https://github.com/seu-usuario/backend_v2.git
cd "backend_v2 (2)/backend_v2"

# Verificar branch
git branch -a
# Esperado: * main
```

---

### Passo 2: Configurar Backend (Python)

#### Opção A: Virtual Environment (Recomendado)

```bash
# Criar venv
python -m venv venv

# Ativar venv
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Verificar
pip list | grep fastapi
# Esperado: fastapi  0.111.0
```

#### Opção B: Conda

```bash
# Criar ambiente
conda create -n escolar python=3.11

# Ativar
conda activate escolar

# Instalar
pip install -r requirements.txt
```

---

### Passo 3: Configurar Variáveis de Ambiente

```bash
# Criar .env arquivo (NÃO commitar!)
cp .env.example .env
# OU criar manualmente:
echo "POSTGRES_DB=escola_dev" > .env
echo "POSTGRES_USER=postgres" >> .env
echo "POSTGRES_PASSWORD=postgres" >> .env
echo "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/escola_dev" >> .env
echo "ADMIN_EMAIL=admin@escola.com" >> .env
echo "ADMIN_PASSWORD=admin123456" >> .env
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env
echo "ADMIN_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env
```

**Conteúdo .env (mínimo):**
```
POSTGRES_DB=escola_dev
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/escola_dev
ADMIN_EMAIL=admin@escola.com
ADMIN_PASSWORD=admin123456
SECRET_KEY=seu_secret_aqui
ADMIN_SECRET_KEY=seu_admin_secret_aqui
CLOUDINARY_CLOUD_NAME=seu_cloud_name
CLOUDINARY_API_KEY=sua_api_key
CLOUDINARY_API_SECRET=seu_api_secret
RECOGNITION_SERVICE_URL=http://localhost:8001
RECOGNITION_API_TOKEN=token-configurado-no-recognition-service
RECOGNITION_WEBHOOK_SECRET=mesmo-segredo-nos-dois-servicos
```

⚠️ **IMPORTANTE:** `.env` NÃO deve ser commitado!

```bash
# Verificar .gitignore
cat .gitignore
# Esperado: .env (deve estar listado)
```

---

### Passo 4: Setup Database

#### Opção A: PostgreSQL Local

```bash
# Windows (via PowerShell como admin)
# Instalar PostgreSQL via: https://www.postgresql.org/download/windows/

# macOS
brew install postgresql

# Linux (Ubuntu/Debian)
sudo apt-get install postgresql postgresql-contrib

# Criar database
createdb escola_dev

# Rodar migrations
alembic upgrade head

# Verificar
psql -d escola_dev -c "\dt"
# Esperado: 7 tabelas listadas
```

#### Opção B: Docker (Recomendado)

```bash
# Criar docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: escola_dev
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
EOF

# Iniciar containers
docker-compose up -d

# Esperar container iniciar (~10s)
sleep 10

# Rodar migrations
alembic upgrade head

# Verificar
docker-compose exec postgres psql -d escola_dev -U postgres -c "\dt"
```

---

### Passo 5: Seed Admin User

```bash
# Se não foi feito automaticamente
python reset_admin.py

# Esperado:
# Usuário admin criado com sucesso!
# Email: admin@escola.com
# Senha: admin123456
```

---

### Passo 6: Rodar Backend

```bash
# Ativar venv (se não estiver)
source venv/bin/activate  # macOS/Linux
# ou
venv\Scripts\activate  # Windows

# Rodar FastAPI
python main.py
# OU com uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Esperado:
# INFO:     Application startup complete
# INFO:     Uvicorn running on http://0.0.0.0:8000
# ✅ Backend rodando!

# Testar em novo terminal
curl http://localhost:8000/health
# Esperado: {"status":"ok"}
```

---

### Passo 7: Setup Frontend (Node.js)

```bash
# Ir para a raiz do workspace e entrar na pasta frontend
cd ../../frontend_v2

# Instalar dependências
npm install

# Testar build
npm run build
# Esperado: ✓ built in XXXms (sem erros)

# Rodar dev server
npm run dev

# Esperado:
# ➜  Local:   http://localhost:5173/
# ➜  press h to show help
# ✅ Frontend rodando!
```

### Passo 8: Recognition-service

O serviço facial possui seu próprio ambiente, banco PostgreSQL com pgvector,
Redis e worker RQ. Para desenvolvimento local:

```bash
cd ../recognition-service
docker compose up --build
```

Não use os valores padrão de `docker-compose.yml` em produção. Configure
`RECOGNITION_API_KEYS`, `SAAS_WEBHOOK_SECRET`, `DATABASE_URL`, `POSTGRES_PASSWORD`,
`SCHOOL_ID` e `SAAS_PRESENCE_WEBHOOK_URL` com secrets reais e tenant explícito.

O backend deve usar o mesmo segredo de webhook e um token aceito por
`RECOGNITION_API_KEYS`.

---

## II. DOCKER COMPOSE COMPLETO

**Arquivo: `docker-compose.yml`**

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: escola_postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-escola_dev}
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - escola

  # Redis Cache (Mês 2+)
  redis:
    image: redis:7-alpine
    container_name: escola_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - escola

  # Backend FastAPI
  backend:
    build:
      context: ./backend_v2
      dockerfile: Dockerfile
    container_name: escola_backend
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/escola_dev
      REDIS_URL: redis://redis:6379
      SECRET_KEY: ${SECRET_KEY}
      ADMIN_EMAIL: ${ADMIN_EMAIL}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend_v2/app:/app/app  # Hot reload
    networks:
      - escola

volumes:
  postgres_data:
  redis_data:

networks:
  escola:
    driver: bridge
```

**Uso:**
```bash
# Iniciar tudo
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar
docker-compose down

# Limpar tudo
docker-compose down -v
```

---

## III. PRIMEIRO LOGIN

### No Browser

```
URL: http://localhost:5173/
Login: admin@escola.com
Senha: admin123456
```

### Fluxo
1. ✅ Digitar credenciais
2. ✅ Clicar "Entrar"
3. ✅ Ver dashboard (Alunos, Presencas, Admin)
4. ✅ Criar um aluno de teste
5. ✅ Registrar presença manual

---

## IV. TESTES

### Rodar Testes Backend

```bash
# Ativar venv
source venv/bin/activate  # macOS/Linux

# Rodar pytest
pytest
# OU com output
pytest -v
# OU com coverage
pytest --cov=app --cov-report=html

# Esperado:
# =================== 24 passed in 2.34s ===================
# ✅ Todos os testes passam!
```

### Testes Individuais

```bash
# Apenas auth
pytest tests/test_auth.py -v

# Apenas alunos
pytest tests/test_alunos.py -v

# Com coverage
pytest tests/test_auth.py --cov=app.routes.auth

# Modo watch (pytest-watch)
ptw  # Rerun testes quando código muda
```

### Coverage Report

```bash
# Gerar HTML report
pytest --cov=app --cov-report=html

# Abrir em browser
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
```

---

## V. DESENVOLVIMENTO DIÁRIO

### Workflow Padrão

```bash
# 1. Ativar ambiente
source venv/bin/activate

# 2. Fazer mudanças no código
# (Seu editor aqui)

# 3. Testar localmente
pytest tests/test_seu_arquivo.py -v

# 4. Rodar backend
python main.py
# (Ele faz hot reload com --reload)

# 5. Testar manualmente
curl http://localhost:8000/seu-endpoint

# 6. Rodar linter
flake8 app/

# 7. Fazer commit
git add .
git commit -m "feat: sua mensagem aqui"

# 8. Push
git push origin main
```

### Hot Reload

Backend (FastAPI) já vem com hot reload:
```bash
# Ele monitora mudanças e reinicia automaticamente
python main.py
```

Frontend também tem hot reload:
```bash
npm run dev
# Salve o arquivo e ele recompila automaticamente
```

---

## VI. TROUBLESHOOTING

### ❌ Problema: "ModuleNotFoundError: No module named 'fastapi'"

**Solução:**
```bash
# Verificar venv está ativado
which python  # macOS/Linux
where python  # Windows
# Esperado: /caminho/para/venv/bin/python

# Se não estiver, ativar:
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Reinstalar
pip install -r requirements.txt
```

---

### ❌ Problema: "psycopg2.OperationalError: connection refused"

**Solução:**
```bash
# PostgreSQL não está rodando
# Opção 1: Iniciar PostgreSQL
# macOS:
brew services start postgresql

# Linux:
sudo systemctl start postgresql

# Opção 2: Usar Docker (mais fácil)
docker-compose up -d postgres

# Verificar conexão
psql -d escola_dev -U postgres
```

---

### ❌ Problema: "Port 8000 already in use"

**Solução:**
```bash
# Matar processo na porta 8000
# macOS/Linux
lsof -i :8000
kill -9 <PID>

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# OU usar porta diferente
python main.py --port 8001
```

---

### ❌ Problema: "npm ERR! code ERESOLVE"

**Solução:**
```bash
# Limpar cache npm
npm cache clean --force

# Reinstalar
rm -rf node_modules package-lock.json
npm install

# Ou força instalação
npm install --legacy-peer-deps
```

---

### ❌ Problema: "Migrations failed"

**Solução:**
```bash
# Verificar status
alembic current

# Ver histórico
alembic history

# Reset (CUIDADO: deleta tudo!)
alembic downgrade base
alembic upgrade head

# OU em Docker
docker-compose exec postgres dropdb -U postgres escola_dev
docker-compose exec postgres createdb -U postgres escola_dev
alembic upgrade head
```

---

### ❌ Problema: "Frontend não conecta ao backend"

**Solução:**
```bash
# Verificar backend está rodando
curl http://localhost:8000/health
# Esperado: {"status":"ok"}

# Verificar .env frontend
cat .env  # Se tiver
# Esperado: VITE_API_URL=http://localhost:8000

# Limpar browser cache
# Ctrl+Shift+Del → Limpar tudo → Hard reload (Ctrl+Shift+R)

# Se ainda não funcionar, verificar CORS
# Backend deve ter CORS habilitado:
# Procurar em main.py por "add_middleware(CORSMiddleware"
```

---

### ❌ Problema: "Tests falham"

**Solução:**
```bash
# Rodar 1 teste com mais verbosidade
pytest tests/test_auth.py::test_login_válido -vv

# Ver logs
pytest tests/ -v --log-cli-level=DEBUG

# Resetar database
alembic downgrade base
alembic upgrade head
pytest

# Se persiste, rodar tests em isolation
pytest -x  # Para no primeiro erro
pytest --tb=short  # Traceback curto
```

---

## VII. FAQ

### P: Como mudei o código mas não aparece mudança?

**R:** Vários motivos possíveis:

```bash
# 1. Backend: Pode precisar de restart manual (se --reload não funcionar)
# Kill processo (Ctrl+C) e rodar novamente
python main.py

# 2. Frontend: Limpar cache
# Ctrl+Shift+Del → Limpar cache de aplicação → Reload (F5)

# 3. npm: Venv pode estar com versão antiga
npm cache clean --force
npm install

# 4. Browser: Cache agressivo
# Abrir DevTools (F12) → Settings → Disable cache (checkbox)
```

---

### P: Qual é meu primeiro ticket?

**R:** Depende do seu interesse:

**Backend:**
1. Implementar paginação (crítico)
2. Adicionar 3 testes faltando (test_presencas_reconhecimento.py)
3. Implementar rate limiting

**Frontend:**
1. Adicionar loading spinner (componente)
2. Melhorar validação de formulário
3. Adicionar testes (Vitest)

**DevOps:**
1. Setup CI/CD (GitHub Actions)
2. Configurar monitoring
3. Setup de backup automático

---

### P: Como faço uma feature nova?

**R:** Workflow padrão:

```bash
# 1. Criar branch
git checkout -b feature/minha-feature

# 2. Fazer mudanças
# (código aqui)

# 3. Testes
pytest -v

# 4. Commit
git add .
git commit -m "feat: descrição da feature"

# 5. Push
git push origin feature/minha-feature

# 6. Criar Pull Request (GitHub UI)
# Descrever o quê, por quê, como testar
```

---

### P: Como resetar tudo (nuclear option)?

**R:** Se tudo quebrou:

```bash
# Backend
rm -rf venv
python -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# Database (Docker)
docker-compose down -v
docker-compose up -d

# Frontend
rm -rf node_modules package-lock.json
npm install

# Fazer seed
python reset_admin.py

# Tudo novo!
```

---

### P: Quanto tempo leva fazer um feature típico?

**R:** Depende da complexidade:

```
Feature                    Tempo      Inclui
─────────────────────────────────────────────
Bug fix simples            30 min     Code + 2 testes
Novo endpoint CRUD         2-4 horas  Endpoint + 5 testes + validação
Nova página React          4-6 horas  Componente + Forms + integração
Feature complexa (WebSock) 2-3 dias   Design + Backend + Frontend + testes
```

---

## VIII. GIT WORKFLOW

### Branches

```
main (always deployable)
  ↑
develop (integration branch)
  ↑
feature/* (seu trabalho)
  feature/paginacao
  feature/rate-limiting
  bugfix/wrong-calculation
```

### Commits

**Bom exemplo:**
```
feat: implementar paginação em GET /alunos

- Adiciona page e limit parameters
- Atualiza resposta com dados de paginação
- Adiciona testes (test_pagination)

Fixes #123
```

**Ruim:**
```
fix stuff
changes
update
```

### Pull Request

1. Push sua branch
2. GitHub → Criar PR
3. Descrever:
   - O quê mudou?
   - Por quê?
   - Como testar?
   - Antes/Depois (se UI)
4. Aguardar review
5. Fazer mudanças se pedidas
6. Merge quando aprovado

---

## IX. COMANDOS ÚTEIS

### Backend

```bash
# Rodar servidor
python main.py

# Rodar com hot reload explícito
uvicorn main:app --reload

# Listar todas as rotas
python -c "from main import app; print([str(r) for r in app.routes])"

# Criar novo migration
alembic revision --autogenerate -m "adicionar campo x"

# Ver database queries (log SQL)
# Adicionar em .env: SQL_LOG=true

# Contar linhas de código
wc -l app/**/*.py
```

### Frontend

```bash
# Dev server com Vite
npm run dev

# Build otimizado
npm run build

# Preview build localmente
npm run preview

# Lint + Fix automático
npm run lint
npm run lint -- --fix

# Análise de bundle
npm run build -- --analyze
```

### Database

```bash
# Conectar via psql
psql -d escola_dev -U postgres

# Listar tabelas
\dt

# Ver schema de tabela
\d alunos

# Rodar query
SELECT COUNT(*) FROM alunos;

# Exit
\q
```

### Docker

```bash
# Ver containers rodando
docker-compose ps

# Ver logs de um serviço
docker-compose logs -f postgres

# Executar comando dentro container
docker-compose exec backend bash

# Parar tudo
docker-compose down

# Remover tudo (including volumes)
docker-compose down -v
```

---

## X. PRÓXIMOS PASSOS

**Agora que você tem tudo rodando:**

1. ✅ Ler [03_ANALISE_COMPLETA_CODEBASES.md](03_ANALISE_COMPLETA_CODEBASES.md) (2h)
2. ✅ Estudar [04_DIAGRAMAS_ARQUITETURA.md](04_DIAGRAMAS_ARQUITETURA.md) (45 min)
3. ✅ Implementar seu primeiro feature
4. ✅ Fazer seu primeiro Pull Request

**Links importantes:**
- 📚 [Índice de Documentação](05_INDICE_DOCUMENTACAO.md)
- 🏗️ [Análise Técnica](03_ANALISE_COMPLETA_CODEBASES.md)
- 📊 [Diagramas](04_DIAGRAMAS_ARQUITETURA.md)

---

## VERSÃO DO DOCUMENTO

| Versão | Data | Mudanças |
|--------|------|----------|
| 1.0 | 18/04/2026 | Versão inicial |

---

**👍 Sucesso! Bem-vindo ao time!**

*Quick Start | Sistema Escolar v2.0 | 18/04/2026*
