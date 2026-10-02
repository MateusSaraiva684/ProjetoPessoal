# 🔐 Troubleshooting - Problemas de Autenticação

## ❌ "E-mail ou senha incorretos" (Erro 401 no Login)

### 🔍 Diagnóstico

Se você consegue fazer login uma vez, mas depois não consegue mais, é um problema de **sincronização de credenciais**.

**Causa:** O hash da senha no banco ficou desincronizado do `.env`.

### ✅ Solução Rápida (Recomendado)

```bash
# Sincronizar admin com as credenciais em .env
python cli.py sync-admin
```

Isso vai:
- ✔️ Verificar se a senha em `.env` corresponde ao banco
- ✔️ Se não corresponder, sincronizar automaticamente
- ✔️ Garantir que `is_superuser=True` e `ativo=True`

**Depois:** Reinicie o backend

```bash
# Terminal com backend ativo: Ctrl+C
# Depois:
python -m uvicorn main:app --reload
```

### 🔄 Quando Rodar sync-admin

- ✅ Ao alterar `ADMIN_PASSWORD` em `.env`
- ✅ Se login falhar com erro 401
- ✅ Após resetar o banco de dados
- ✅ Após clonar o repositório em novo ambiente

---

## 📝 Fluxo de Login

```
Frontend (email + senha)
        ↓
Backend /api/auth/login
        ↓
Busca usuário no banco por email
        ↓
Usa bcrypt.verify(senha_recebida, hash_armazenado)
        ↓
Se OK → Retorna JWT token (200)
Se ERRO → Retorna "E-mail ou senha incorretos" (401)
```

**IMPORTANTE:** Bcrypt compara a **senha recebida** com o **hash armazenado no banco**. Se o hash for antigo, a comparação falha mesmo que a senha esteja correta.

---

## 🛠️ Debug (Se Persistir)

### Opção 1: Logs do Backend

Reinicie com logs verbosos:

```bash
python -m uvicorn main:app --reload --log-level debug
```

Procure por:
- `🔄 Sincronizando admin existente` → seed está rodando
- `✅ Admin sincronizado` → credenciais foram atualizadas
- `Erro ao sincronizar` → problema no seed

### Opção 2: Verificar Banco Diretamente

```sql
-- Ver hash armazenado
SELECT id, email, is_superuser, ativo FROM usuarios WHERE email = 'admin@admin.com';
```

---

## 🔐 Segurança: Nunca Compartilhe

- ❌ Não faça commit de `.env` no Git
- ❌ Não exponha `ADMIN_PASSWORD` em logs/console
- ❌ Use senhas fortes (mín. 12 caracteres com símbolos)

---

## 📞 Resumo de Comandos

| Problema | Solução |
|----------|---------|
| Login não funciona | `python cli.py sync-admin` |
| Mudou senha em `.env` | `python cli.py sync-admin` |
| Admin desapareceu | Reinicie backend (seed recria) |
| Quer limpar tudo | Ver migration docs |

---

**Última atualização:** 17 de abril de 2026
