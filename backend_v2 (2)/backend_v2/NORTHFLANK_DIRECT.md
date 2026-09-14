# 🚀 Migração Direta: Render → Northflank (SEM Docker Local)

## ⚡ 50 MINUTOS - Do Render ao Northflank

---

## PASSO 1: Preparar Git (2 min)

Execute **AGORA** no PowerShell:

```powershell
cd C:\Users\mateu\Desktop\backend_v2

git add Dockerfile .dockerignore migration_helper.py northflank.yaml
git commit -m "feat: prepare for Northflank migration"
git push origin main
```

✅ **Pronto!** Seus arquivos estão no GitHub.

---

## PASSO 2: Criar Conta Northflank (3 min)

1. Abra https://northflank.com
2. Clique "Sign Up"
3. Use seu email
4. Criar senha
5. Confirmar email

---

## PASSO 3: Criar Projeto (5 min)

1. Dashboard → "New Project"
2. Nome: `escola-backend` (ou outro nome)
3. Region: escolha a mais perto do Brasil (ex: `us-east`)
4. Clique "Create"

---

## PASSO 4: Conectar seu GitHub (5 min)

1. Dashboard do projeto → "Add Service"
2. Tipo: **Source Code (Docker)**
3. Provider: **GitHub**
4. Clique "Authorize Northflank"
   - GitHub abre em nova aba
   - Clique "Authorize"
   - Volta para Northflank automaticamente
5. Selecione seu repositório `backend_v2`
6. Branch: `main`
7. Clique "Continue"

---

## PASSO 5: Configurar Build Docker (3 min)

1. **Builder**: Docker (padrão)
2. **Dockerfile**: `./Dockerfile` ✅ (já existe)
3. **Build Arguments**: Deixe em branco
4. Clique "Continue"

Northflank vai fazer build automaticamente!

---

## PASSO 6: Provisionar PostgreSQL (10 min)

1. No projeto, clique "Add Database"
2. Tipo: **PostgreSQL**
3. Version: **15** (ou a mais recente)
4. Instance: **Micro** (para dev/teste)
5. Database Name: `escola` (ou similar)
6. Username: `admin`
7. Password: gere uma forte
8. Clique "Create"

⏳ Aguarde 2-3 minutos (BD criando...)

Quando terminar, Northflank gera uma `DATABASE_URL` automaticamente.
**Copie essa string** - você vai precisar.

---

## PASSO 7: Provisionar Redis (Opcional - 5 min)

Se você usa Celery para background tasks:

1. Clique "Add Cache"
2. Tipo: **Redis**
3. Version: **7** (ou mais recente)
4. Instance: **Micro**
5. Clique "Create"

Northflank gera `REDIS_URL` automaticamente.

---

## PASSO 8: Configurar Variáveis de Ambiente (10 min)

No seu serviço, vá para "Environment Variables":

### Adicione as variáveis (ambiente):

```
ENVIRONMENT=production
TRUST_PROXY_HEADERS=true
PORT=8000
```

### Adicione os Secrets (dados sensíveis):

No seu serviço, vá para "Secrets":

1. **DATABASE_URL**: Cole aquela string do Passo 6
2. **SECRET_KEY**: Use isso:
   ```
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Cole o resultado
3. **ADMIN_EMAIL**: `admin@admin.com`
4. **ADMIN_PASSWORD**: Escolha uma senha forte
5. **ADMIN_SECRET_KEY**: Use isso:
   ```
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
6. **FRONTEND_URL**: `https://seu-frontend.vercel.app`
7. **CLOUDINARY_CLOUD_NAME**: Seu cloud name
8. **CLOUDINARY_API_KEY**: Sua API key
9. **CLOUDINARY_API_SECRET**: Seu secret
10. **FACE_RECOGNITION_SERVICE_URL**: (se usar)

**Se usar Redis:**
- **REDIS_URL**: Cole aquela string do Passo 7
- **CELERY_BROKER_URL**: `redis://user:pass@host:port/0`
- **CELERY_RESULT_BACKEND**: `redis://user:pass@host:port/1`

---

## PASSO 9: Deploy! (10 min)

1. Volte para seu serviço
2. Clique em "Deploy"
3. Status: `Building...` → aguarde
4. Status: `Running...` ✅ Sucesso!

Northflank vai:
- ✅ Fazer git clone
- ✅ Executar docker build
- ✅ Rodar container
- ✅ Expor na internet

---

## PASSO 10: Migrar Dados do Render (10 min)

### Backup do Render (no seu computador):

```powershell
# Obter credenciais do Render
# (procure em: Dashboard Render → seu serviço → Database → Connection String)

$renderHost = "seu-host-render.postgres.database.azure.com"
$renderUser = "seu-usuario"
$renderPass = "sua-senha"
$renderDB = "seu-db"

# Fazer backup
pg_dump -h $renderHost -U $renderUser -d $renderDB -W > render_backup.sql
# (vai pedir senha, cole $renderPass)
```

### Restaurar no Northflank (via terminal web):

1. Dashboard Northflank → seu projeto → PostgreSQL
2. Clique na aba "Shell" ou "Terminal"
3. Execute:

```bash
psql postgresql://user:pass@host:5432/escola < render_backup.sql
```

(Substitua `user:pass@host` pela DATABASE_URL do Northflank)

---

## PASSO 11: Finalizar (5 min)

No terminal do Northflank (ou via logs), execute:

```bash
# Rodar migrations
alembic upgrade head

# Sincronizar admin
python cli.py sync-admin
```

---

## ✅ Pronto!

Sua app está rodando em Northflank! 🎉

### Testar:

- Health: `https://seu-app-xyz.run.northflank.io/health`
- Docs: `https://seu-app-xyz.run.northflank.io/docs`
- Admin: `https://seu-app-xyz.run.northflank.io/admin` (depende da sua implementação)

### Próximos passos:

1. ✅ Configure DNS custom (opcional)
2. ✅ Configure alertas de uptime
3. ✅ Configure backups automáticos (já é default)
4. ✅ Monitore logs primeiros dias

---

## 🆘 Problemas?

### "Build failed"
→ Vá em "Build Logs" e procure o erro
→ Geralmente é arquivo faltando ou typo

### "Connection refused no database"
→ `DATABASE_URL` copiada corretamente?
→ Aguarde mais 2-3 minutos para BD ficar pronto

### "502 Bad Gateway"
→ Verifique logs do container
→ App iniciou?

### "Admin password não funciona"
→ Execute: `python cli.py sync-admin`

---

## 📞 Links Úteis

- **Northflank Docs**: https://docs.northflank.com
- **Northflank Support**: support@northflank.com
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **PostgreSQL Docs**: https://www.postgresql.org

---

## ⏱️ Timeline

```
00:00 - Commit Git
00:05 - Northflank account + projeto
00:10 - PostgreSQL criado
00:20 - Redis criado (opcional)
00:30 - Variáveis configuradas
00:40 - Deploy
00:50 - Dados migrados + finalizações
```

**Total: 50 minutos** ⚡

---

**Estatus**: 🟢 Pronto para começar  
**Próximo passo**: Execute o Passo 1!
