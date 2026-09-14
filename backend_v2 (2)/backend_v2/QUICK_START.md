# ⚡ Guia Rápido: Migração Render → Northflank (SEM Docker Local)

## ✅ Pré-requisitos
- [x] Dockerfile criado
- [x] .dockerignore criado
- [x] Documentação completa preparada
- [x] Repositório Git conectado

---

## 🚀 PASSO 1: Commit e Push para Git (2 min)

Execute no PowerShell (na pasta do projeto):

```powershell
cd C:\Users\mateu\Desktop\backend_v2

# Adicionar os novos arquivos
git add Dockerfile .dockerignore migration_helper.py northflank.yaml

# Commit
git commit -m "feat: prepare for Northflank migration"

# Push para o repositório
git push origin main
```

✅ Depois, Northflank faz o build automaticamente!

---

## 📋 PASSO 2: Setup Northflank (10 min)

1. Acesse https://northflank.com
2. Clique em "Create Project"
3. Dê um nome (ex: `escola-prod`)
4. Escolha uma região

### Conectar Repositório Git

1. No projeto, clique em "Add Service"
2. Selecione "Source Code (Docker)"
3. Clique em "GitHub" (ou GitLab/Bitbucket)
4. Autorize Northflank a acessar suas repos
5. Selecione seu repositório `backend_v2`
6. Branch: `main`

---

## 🗄️ PASSO 3: Provisionar Banco de Dados (10 min)

### PostgreSQL

1. Ir para "Add Database" no projeto
2. Tipo: **PostgreSQL 15**
3. Instance: **Micro** (dev) ou **Small** (prod)
4. Copiar `DATABASE_URL` que será gerada
5. Clicar "Create"

### Redis (Opcional, se usar Celery)

1. Ir para "Add Cache"
2. Tipo: **Redis 7**
3. Instance: **Micro**
4. Copiar `REDIS_URL`
5. Clicar "Create"

---

## 🔐 PASSO 4: Configurar Variáveis (10 min)

### No Dashboard Northflank

1. Adicionar novo "Service" → Docker
2. Conectar repositório
3. Dockerfile: `./Dockerfile`
4. Port: `8000` (público)

### Secrets (criar uma por uma)

```
DATABASE_URL=postgresql://user:pass@host:5432/db
SECRET_KEY=<gerar com: python -c "import secrets; print(secrets.token_urlsafe(32))">
ADMIN_EMAIL=admin@admin.com
ADMIN_PASSWORD=<sua-senha-forte>
ADMIN_SECRET_KEY=<outra-chave-secreta>
FRONTEND_URL=https://seu-frontend.vercel.app
CLOUDINARY_CLOUD_NAME=seu-cloud-name
CLOUDINARY_API_KEY=sua-api-key
CLOUDINARY_API_SECRET=seu-api-secret
ENVIRONMENT=production
TRUST_PROXY_HEADERS=true
```

**Se usar Celery:**
```
REDIS_URL=redis://default:pass@host:port
CELERY_BROKER_URL=redis://default:pass@host:port/0
CELERY_RESULT_BACKEND=redis://default:pass@host:port/1
```

---

## 🚀 PASSO 5: Deploy (15 min)

1. Clicar "Deploy" no dashboard
2. Aguardar build (2-5 min)
3. Aguardar container iniciar
4. Ver logs em "Logs" tab

### Validar Deploy

```bash
# Verificar status
curl https://seu-app.run.northflank.io/api/health

# Acessar API docs
# https://seu-app.run.northflank.io/docs

# Checar logs
# Dashboard → Logs
```

---

## 🔄 PASSO 6: Migrar Dados (20 min)

### Opção A: Backup + Restore (Recomendado)

```bash
# 1. Exportar do Render
pg_dump -h <render-host> -U <user> -d <dbname> > backup.sql

# 2. Restaurar no Northflank (via terminal no dashboard)
psql -h <northflank-host> -U <user> -d <dbname> < backup.sql
```

### Opção B: Via Northflank UI

1. Dashboard → Database → Backups
2. Import backup file

---

## ✨ PASSO 7: Pós-Deploy (5 min)

```bash
# Via terminal do container (no dashboard)

# 1. Rodar migrations
alembic upgrade head

# 2. Sincronizar admin
python cli.py sync-admin

# 3. Verificar logs
docker logs <container>
```

---

## ✅ Checklist Rápido

```
☐ Git add/commit/push realizado
☐ Conta Northflank criada
☐ Projeto Northflank criado
☐ Git conectado ao Northflank
☐ PostgreSQL provisionado
☐ Redis provisionado (se necessário)
☐ Todas as secrets configuradas
☐ Deploy executado
☐ Dados migrados do Render
☐ Migrations rodadas
☐ Admin sincronizado
☐ Health check respondendo
☐ Frontend conectando
```

---

## 🎯 Tempo Total: ~50 minutos

| Etapa | Tempo |
|-------|-------|
| Commit & Push | 2 min |
| Setup Northflank | 10 min |
| DB + Redis | 10 min |
| Config vars | 10 min |
| Deploy | 10 min |
| Migrar dados | 10 min |
| Post-deploy | 10 min |
| **TOTAL** | **~50 min** |

---

## 🆘 Problemas Comuns

### "Connection refused no database"
```
→ Aguarde 2-3 min até BD ficar pronto
→ Verifique DATABASE_URL nas secrets
→ Check: TRUST_PROXY_HEADERS=true
```

### "502 Bad Gateway"
```
→ Verifique logs do container
→ App está rodando na porta 8000?
→ Há erro de startup nos logs?
```

### "502 Timeout"
```
→ Health check pode estar falhando
→ Certifique-se que /health endpoint existe
→ Aumentar timeout health check
```

### "Admin password não funciona"
```
→ Execute: python cli.py sync-admin
→ Ou set: SYNC_ADMIN_PASSWORD_ON_STARTUP=true
```

---

## 📞 Recursos

- **Northflank Docs**: https://docs.northflank.com
- **FastAPI**: https://fastapi.tiangolo.com
- **Alembic**: https://alembic.sqlalchemy.org
- **Docker**: https://docs.docker.com

---

## 💡 Dicas Pro

1. **Teste tudo localmente** com Docker antes de subir
2. **Backup de dados** antes de migrar
3. **Use staging** para testar antes de produção
4. **Monitore logs** nos primeiros dias
5. **Configurar alertas** de uptime
6. **Documentar** todo o processo

---

**Status**: ✅ Pronto para iniciar (SEM Docker Local)  
**Data**: 28 de abril de 2026  
**Tempo estimado**: 50 minutos (direto ao Northflank)
