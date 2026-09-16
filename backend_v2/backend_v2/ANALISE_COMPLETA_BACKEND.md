# 🔍 ANÁLISE COMPLETA DO BACKEND v2

> **Documento histórico:** os bugs e números abaixo foram registrados em abril de 2026. Paginação, validação de entrada, refresh token e parte do rate limiting já foram implementados. Para o estado atual, consulte [07_STATUS_ATUAL_2026.md](../../DOCUMENTACAO_SISTEMA_ESCOLAR/07_STATUS_ATUAL_2026.md) e [E2E_RECOGNITION_FLOW.md](docs/E2E_RECOGNITION_FLOW.md).

**Data**: 20 de abril de 2026  
**Status histórico**: análise de abril de 2026; os números de teste abaixo não representam a suíte atual

---

## 🚨 BUGS CRÍTICOS (Corrigir Imediatamente)

### 1. **Race Condition em Número de Inscrição** ⚠️ CRÍTICO
**Arquivo**: `app/services/aluno_service.py` linhas 142-150  
**Problema**: Check-then-act sem lock atômico
```python
# PROBLEMA: Check feito em SELECT, mas INSERT acontece depois
if self.alunos.numero_inscricao_exists(...):  # Query 1
    raise BadRequestError(...)
# Aqui outro request pode ter inserido o mesmo número!
aluno = Aluno(...)  # Query 2
self.alunos.add(aluno)
```
**Impacto**: Dois alunos podem ser criados com mesmo número de inscrição em requisições paralelas  
**Solução**: Usar UNIQUE constraint com Try/Except, ou transação SERIALIZABLE

---

### 2. **Vazamento de Conexão BD em get_db()** ⚠️ CRÍTICO
**Arquivo**: `app/database/session.py` linhas 20-26  
**Problema**: Sem rollback em erro
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  # ❌ Sem rollback - transação fica aberta se erro
```
**Impacto**: Transações em erro ficam abertas, pode travar BD  
**Solução**:
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    except:
        db.rollback()
        raise
    finally:
        db.close()
```

---

### 3. **Falha Silenciosa em Upload de Foto** ⚠️ CRÍTICO
**Arquivo**: `app/services/aluno_service.py` linhas 93-110  
**Problema**: Sem try/except para `salvar_foto()`
```python
def criar(...):
    # Se salvar_foto() falha, nenhuma exceção é capturada
    foto = salvar_foto(foto)  # Pode lançar AppError
    aluno = Aluno(..., foto=foto)  # Mas ainda cria aluno
    self.alunos.add(aluno)
    self.db.commit()  # Aluno fica sem foto mesmo que falha
```
**Impacto**: Aluno criado sem foto mesmo que upload falhe  
**Solução**: Adicionar try/except ou falhar o request

---

### 4. **Falta de Validação de Entrada** ⚠️ CRÍTICO
**Arquivo**: `app/routes/alunos.py` linhas 46-65  
**Problema**: Campos obrigatórios podem ser vazios
```python
@router.post("/", response_model=AlunoResponse)
def criar(
    nome: str = Form(...),  # Pode ser "   " (vazio com espaços)
    telefone: str = Form(...),  # Sem validação de formato
    ...
):
```
**Impacto**: Dados inválidos salvos no BD  
**Solução**: Adicionar validação no Pydantic schema

---

### 5. **Refresh Token Não Valida Novo Body/Cookie** ⚠️ CRÍTICO
**Arquivo**: `app/routes/auth.py` linhas 82-92  
**Problema**: Sem validação se ambos são None
```python
@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    cookie_token: Optional[str] = Cookie(default=None, alias="refresh_token"),
    body: Optional[RefreshRequest] = None,
    ...
):
    token = cookie_token or (body.refresh_token if body else None)
    # ❌ Se ambos None, token fica None
    return _token_response(auth_service.renovar(token), response)
```
**Impacto**: Pode tentar renovar com token None  
**Solução**: Validar antecipadamente

---

## 🟡 ISSUES MODERADAS (Corrigir em Breve)

### 6. **File Pointer Não Reset Após Read** 
**Arquivo**: `app/services/media.py` linha 52  
**Problema**:
```python
conteudo = foto.file.read()  # ❌ File pointer não volta ao início
if len(conteudo) > TAMANHO_MAXIMO:
    raise BadRequestError(...)
# Se passou, conteudo está vazio porque pointer está no fim
uploader.upload(conteudo, ...)  # Pode enviar vazio!
```
**Solução**: `foto.file.seek(0)` antes de usar ou após ler

---

### 7. **Parsing Frágil de URL Cloudinary**
**Arquivo**: `app/services/media.py` linhas 79-87  
**Problema**: String split sem validação adequada
```python
partes = url.split("/upload/")
if len(partes) == 2:
    public_id_com_ext = partes[1]
    if public_id_com_ext.startswith("v") and "/" in public_id_com_ext:
        public_id_com_ext = public_id_com_ext.split("/", 1)[1]
    # ❌ Se estrutura da URL mudar, quebra
```
**Solução**: Usar regex ou URL parser

---

### 8. **Sem Logs de Falha de Validação**
**Arquivo**: `app/core/exceptions.py`  
**Problema**: Exceções não capturam contexto original
**Impacto**: Difícil debugar problemas em produção

---

### 9. **CORS Hardcoded Sem Validação**
**Arquivo**: `main.py` linhas 29-31  
**Problema**:
```python
origins = ["http://localhost:5173", "http://localhost:3000"]
if settings.FRONTEND_URL:
    origins.append(settings.FRONTEND_URL)
# ❌ Sem validação de URL, pode adicionar malwares
```
**Solução**: Validar FRONTEND_URL com urllib.parse.urlparse()

---

### 10. **Documentação Swagger Desabilitada sem Motivo em Produção**
**Arquivo**: `main.py` linhas 23-25  
**Problema**:
```python
docs_url="/docs" if not settings.is_production else None,
# ❌ Se admin precisa debugar, fica sem /docs
```
**Solução**: Usar autenticação em vez de desabilitar

---

## 🟠 ISSUES DE SEGURANÇA

### 11. **Sem Rate Limit em Endpoints de Alunos/Admin**
**Arquivo**: Todos os routes  
**Problema**: Rate limit só em /login, mas admin pode fazer bruteforce em DELETE  
**Solução**: Estender rate limit para outros endpoints

---

### 12. **Secrets em Logs de Erro**
**Arquivo**: `main.py` linha 74  
**Problema**:
```python
logger.exception("Erro inesperado em %s %s", request.method, request.url.path)
# ❌ Pode vazar tokens na query string
```
**Solução**: Sanitizar URL antes de logar

---

### 13. **ADMIN_SECRET_KEY Não Utilizado**
**Arquivo**: `app/core/config.py` linha 26  
**Problema**: Definido mas nunca usado no código  
**Solução**: Remover ou implementar uso

---

### 14. **Sem Validação de Email**
**Arquivo**: `app/schemas/schemas.py`  
**Problema**: Campo email usa `EmailStr` mas sem rate limit em registro  
**Solução**: Limitar registros por email

---

## 🔵 PROBLEMAS DE PERFORMANCE

### 15. **N+1 Queries em Admin Stats**
**Arquivo**: `app/services/admin_service.py` linhas 43-46  
**Problema**:
```python
def listar_usuarios(self) -> list[dict]:
    return [
        {
            ...
            "total_alunos": self.alunos.count_by_user(u.id),  # Query para cada user!
        }
        for u in self.usuarios.list_all()
    ]
```
**Impacto**: Se 1000 usuários, 1001 queries!  
**Solução**: Fazer join e count em uma única query

---

### 16. **Sem Índices Adequados no BD**
**Arquivo**: `app/models/models.py`  
**Problema**: Faltam índices em:
- `Presenca.aluno_id` (usado em queries frequentes)
- `Aluno.turma` (usado em filtros)
- `FaceEmbedding.aluno_id`

---

### 17. **Sem Paginação em list_by_user (Alunos)**
**Arquivo**: `app/repositories/aluno_repository.py` linhas 11-43  
**Problema**: Já implementado, mas outros endpoints podem não usar
**Solução**: Padronizar todas as listas

---

## 🟣 PROBLEMAS DE QUALIDADE DE CÓDIGO

### 18. **Inconsistência em Tratamento de Erros**
**Problema**: Alguns erros usam `AppError`, outros `BadRequestError`, alguns não tratam  
**Solução**: Padronizar em um ponto central

---

### 19. **Falta de Type Hints Completos**
**Arquivo**: Vários  
**Problema**: Parâmetros `**kwargs`, retornos `dict` sem spec  
**Solução**: Usar TypedDict ou dataclasses

---

### 20. **Sincronização de Admin Confusa em Startup**
**Arquivo**: `main.py` linhas 78-138  
**Problema**: Lógica complexa, múltiplas flags booleanas  
**Solução**: Simplificar ou mover para migração Alembic

---

### 21. **Sem Docstrings em Repositórios**
**Arquivo**: `app/repositories/`  
**Problema**: Métodos sem documentação  
**Solução**: Adicionar docstrings

---

### 22. **Variável `_is_local` Não Utilizada**
**Arquivo**: `app/database/session.py` linha 13  
**Problema**: Definida mas não usada em lugar algum  
**Solução**: Remover ou utilizar

---

## 📋 PROBLEMAS DE CONFIGURAÇÃO

### 23. **DATABASE_URL Sem Validação de Formato**
**Arquivo**: `app/core/config.py`  
**Problema**: Aceita qualquer string, pode falhar ao conectar  
**Solução**: Validar formato de URL

---

### 24. **Sem Logs de Startup**
**Arquivo**: `main.py`  
**Problema**: Difícil saber o que aconteceu durante inicialização  
**Solução**: Adicionar mais logs de debug

---

### 25. **Timeout em Face Recognition é Float Literal**
**Arquivo**: `app/core/config.py` linhas 36-37  
**Problema**:
```python
FACE_RECOGNITION_TIMEOUT_SECONDS: float = float(
    os.getenv("FACE_RECOGNITION_TIMEOUT_SECONDS", "10")
)
```
Sem validação se é positivo  
**Solução**: Validar range (0.1 - 300)

---

## 📝 PROBLEMAS DE TESTES

### 26. **Sem Teste de Concorrência**
**Arquivo**: `app/tests/`  
**Problema**: Não testa race conditions  
**Solução**: Adicionar testes com threading

---

### 27. **Sem Teste de Timeout**
**Arquivo**: `app/tests/`  
**Problema**: Não testa comportamento quando serviço é lento  
**Solução**: Mock asyncio.sleep

---

### 28. **Fixtures Compartilhadas Sem Reset**
**Arquivo**: `app/tests/conftest.py`  
**Problema**: BD de teste pode ter dados de teste anterior  
**Solução**: Fazer drop/recreate antes de cada teste

---

---

## 🎯 PRIORIDADE DE CORREÇÃO

### URGENT (Fazer Hoje)
1. ✅ Bug #2: Rollback em get_db()
2. ✅ Bug #1: Race condition número de inscrição
3. ✅ Bug #3: Falha silenciosa foto
4. ✅ Bug #5: Refresh token validação
5. ✅ Issue #12: Secrets em logs

### HIGH (Esta Semana)
6. ✅ Bug #4: Validação de entrada
7. ✅ Bug #6: File pointer reset
8. ✅ Issue #9: CORS validation
9. ✅ Issue #15: N+1 queries

### MEDIUM (Próximas Semanas)
10. Issue #7: Parsing Cloudinary
11. Issue #10: Swagger docs
12. Issue #11: Rate limit expandido
13. Issue #16: Índices BD

### LOW (Refatoração)
14. Issue #8: Logs melhorados
15. Issue #18-22: Code quality
16. Issue #23-28: Config e testes

---

## 💡 RECOMENDAÇÕES GERAIS

1. **Adicionar middleware de transação** com rollback automático
2. **Usar SQLAlchemy Events** para audit de mudanças
3. **Implementar Circuit Breaker** para Cloudinary
4. **Adicionar Observabilidade** (OpenTelemetry)
5. **Usar Pydantic Validators** mais rigorosos
6. **Migrar para async** onde possível
7. **Adicionar integration tests** de verdade
8. **Documentar API** com OpenAPI schemas

---

## 📊 RESUMO

| Categoria | Quantidade | Severidade |
|-----------|-----------|-----------|
| Bugs Críticos | 5 | 🚨 |
| Issues Moderadas | 5 | 🟡 |
| Segurança | 4 | 🟠 |
| Performance | 3 | 🔵 |
| Qualidade | 5 | 🟣 |
| Config/Testes | 4 | 📋 |
| **TOTAL** | **28** | ⚠️ |

✅ **Testes**: 24/24 passando  
❌ **Cobertura**: ~45% (estimado)  
⚠️ **Dívida Técnica**: MODERADA
