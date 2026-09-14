# 🚀 Guia Completo: Migração de Render para Northflank

## 📋 Pré-requisitos

- Conta ativa no Northflank (https://northflank.com)
- Repositório Git (GitHub, GitLab, ou Bitbucket)
- Dockerfile criado ✅ (já incluído neste projeto)
- Todas as variáveis de ambiente documentadas

---

## 📦 Fase 1: Preparar o Repositório

### 1.1 Arquivos Criados

- ✅ `Dockerfile` - Build multi-stage otimizado
- ✅ `northflank.yaml` - Configuração do Northflank (opcional, pode usar UI)

### 1.2 Commits Git

```bash
git add Dockerfile northflank.yaml
git commit -m "feat: add Docker configuration for Northflank migration"
git push origin main
```

---

## 🔧 Fase 2: Setup no Northflank Dashboard

### 2.1 Criar Projeto

1. Acesse https://northflank.com
2. Login na sua conta
3. Clique em "Create Project"
4. Escolha um nome (ex: `escola-backend-prod`)
5. Selecione a região mais próxima

### 2.2 Conectar Repositório Git

1. No projeto, clique em "Add Service"
2. Selecione "Source Code" (Docker)
3. Escolha seu provider Git (GitHub/GitLab/Bitbucket)
4. Autorize Northflank a acessar seu repositório
5. Selecione o repositório e branch (main/master)

### 2.3 Configurar Build

1. **Builder**: Docker (multi-stage recomendado)
2. **Dockerfile**: `./Dockerfile` (caminho padrão)
3. **Build Arguments**: Deixe em branco
4. **Registry**: Use o Northflank Registry (padrão)

---

## 🗄️ Fase 3: Banco de Dados

### 3.1 Provisionar PostgreSQL

1. No projeto, clique em "Add Database"
2. Tipo: **PostgreSQL**
3. Version: **15.x** (compatível com projeto)
4. Configurações:
   - **Name**: `postgresql` ou `école-db`
   - **Instance Type**: Micro (para desenvolvimento) ou Small (produção)
   - **Storage**: 20GB (padrão)
   - **Backup**: Ativar (automático)
5. Clique em "Create"

**Importante**: Northflank fornecerá a CONNECTION STRING automaticamente.

### 3.2 Provisionar Redis (se usar Celery)

1. Clique em "Add Cache"
2. Tipo: **Redis**
3. Version: **7.x**
4. Configurações:
   - **Name**: `redis`
   - **Instance Type**: Micro
   - **Eviction Policy**: `allkeys-lru`
5. Clique em "Create"

Northflank fornecerá `REDIS_URL` automaticamente.

---

## 🔐 Fase 4: Variáveis de Ambiente

### 4.1 Obter Connection Strings

Após criar DB e Redis, Northflank gera automaticamente:
- `DATABASE_URL` - PostgreSQL
- `REDIS_URL` - Redis

### 4.2 Configurar Secrets

No dashboard do Northflank, na seção "Secrets" do seu serviço, adicione:

```
DATABASE_URL = postgresql://user:pass@host:5432/dbname
SECRET_KEY = <gerar com: python -c "import secrets; print(secrets.token_urlsafe(32))">
ADMIN_EMAIL = admin@admin.com
ADMIN_PASSWORD = <senha-forte>
ADMIN_SECRET_KEY = <chave-secreta>
FRONTEND_URL = https://seu-frontend.vercel.app
CLOUDINARY_CLOUD_NAME = seu-cloud-name
CLOUDINARY_API_KEY = sua-api-key
CLOUDINARY_API_SECRET = seu-api-secret
FACE_RECOGNITION_SERVICE_URL = https://seu-servico/facial
ENVIRONMENT = production
TRUST_PROXY_HEADERS = true
REDIS_URL = redis://default:pass@host:port
CELERY_BROKER_URL = redis://default:pass@host:port/0
CELERY_RESULT_BACKEND = redis://default:pass@host:port/1
```

### 4.3 Comparar com Render

Se você tem essas variáveis no Render, copie os valores (exceto `DATABASE_URL` e `REDIS_URL` que são novas).

---

## 🚀 Fase 5: Deploy do Serviço

### 5.1 Configurar o Serviço

1. Clique em "Add Service"
2. Selecione "Docker" source
3. Conecte seu repositório Git
4. Dockerfile: `./Dockerfile`
5. Port: `8000` (expor publicamente)

### 5.2 Configurar Variáveis

1. Na aba "Environment Variables":
   - `ENVIRONMENT = production`
   - `TRUST_PROXY_HEADERS = true`
   - `PORT = 8000`

2. Na aba "Secrets":
   - Adicione todas as secrets listadas em 4.2

### 5.3 Health Check

Configure health check (já está no Dockerfile):

```
Endpoint: /health
Interval: 30s
Timeout: 10s
```

### 5.4 Deploy

1. Clique em "Deploy" ou "Trigger"
2. Aguarde o build completar (2-5 minutos)
3. Verifique os logs em "Logs"
4. Teste a API em: `https://seu-dominio.app/docs`

---

## 📝 Fase 6: Migrations Database

### 6.1 Executar Migrations

Após o primeiro deploy, execute Alembic:

**Opção 1 - Via Terminal (Northflank Shell)**
```bash
# No dashboard, abra o shell do container
alembic upgrade head
```

**Opção 2 - Via Comando Customizado**
1. Vá para "Advanced"
2. Start Command: `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000`

### 6.2 Criar Admin

```bash
# Via Terminal
python cli.py sync-admin
```

Ou verifique se a variável `SYNC_ADMIN_PASSWORD_ON_STARTUP=true` está configurada.

---

## 🔄 Fase 7: Migração de Dados (Importante!)

### 7.1 Backup do Render

```bash
# No terminal local
pg_dump -h <render-host> -U <user> -d <dbname> > backup.sql
```

### 7.2 Restaurar no Northflank

```bash
# Copiar arquivo para dentro do container
psql -h <northflank-host> -U <user> -d <dbname> < backup.sql
```

**Alternativa**: Use Northflank's built-in database migration tools (mais seguro).

---

## ✅ Checklist Final

- [ ] Dockerfile criado e testado localmente
- [ ] Repository conectado ao Northflank
- [ ] PostgreSQL provisionado
- [ ] Redis provisionado (se usar Celery)
- [ ] Todas as secrets configuradas
- [ ] Banco de dados migrado
- [ ] Migrations rodadas com sucesso
- [ ] Admin criado/sincronizado
- [ ] API responde em `/health`
- [ ] Frontend consegue conectar na API
- [ ] Logs sem erros críticos

---

## 🐛 Troubleshooting

### Erro: "Connection refused" no Database

```
✓ Solução: Aguarde 2-3 minutos para o DB estar pronto
✓ Verifique a CONNECTION STRING em env vars
✓ Certifique-se que TRUST_PROXY_HEADERS=true
```

### Erro: "502 Bad Gateway"

```
✓ Verifique se a aplicação está rodando (não crashed)
✓ Check logs: docker logs <container-id>
✓ Verifique porta (deve ser 8000)
```

### Erro: "Failed to build image"

```
✓ Dockerfile tem sintaxe correta?
✓ Todos os arquivos existem? (requirements.txt, main.py)
✓ Verifique a aba "Build Logs"
```

### Admin Password não sincroniza

```
✓ Certifique-se que SYNC_ADMIN_PASSWORD_ON_STARTUP=true OU
✓ Execute no shell: python cli.py sync-admin
```

---

## 📚 Recursos Úteis

- **Docs Northflank**: https://docs.northflank.com
- **Docker Best Practices**: https://docs.docker.com/develop/dev-best-practices/
- **FastAPI Deployment**: https://fastapi.tiangolo.com/deployment/
- **Alembic Docs**: https://alembic.sqlalchemy.org/

---

## 💡 Dicas de Performance

1. **Use BuildKit**: `DOCKER_BUILDKIT=1 docker build .`
2. **Cache de dependências**: Multi-stage build já otimizado
3. **Health checks**: Mantenha ativo para melhor uptime
4. **Logs estruturados**: Configure em `app/core/logging_config.py`
5. **Limpar uploads antigos**: Configure política de retenção

---

## 📞 Próximos Passos

1. Contatar suporte Northflank se tiver dúvidas
2. Monitorar primeiro deploy com atenção
3. Testar todas as funcionalidades principais
4. Configurar alertas de uptime
5. Documentar processo para futuros deploys

**Data Migração**: 28 de abril de 2026
**Status**: ✅ Pronto para iniciar
