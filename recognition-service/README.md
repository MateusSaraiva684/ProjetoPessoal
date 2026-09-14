# Recognition Service

Servico interno de reconhecimento facial para acoplamento ao SaaS.

O projeto expoe uma API FastAPI, enfileira reconhecimentos no Redis/RQ, processa embeddings com InsightFace e consulta PostgreSQL com pgvector.

## Status

Ainda e uma base em desenvolvimento. Ja existe uma primeira camada de hardening:

- endpoints internos protegidos por API key;
- CORS configuravel por allowlist;
- banco configurado por `DATABASE_URL`;
- healthcheck verificando Redis e PostgreSQL;
- schema inicial para `alunos`, `presencas` e `embeddings`;
- worker usando `SIMILARITY_THRESHOLD` e `USE_GPU` da configuracao.
- identidade de aluno alinhada ao SaaS por `school_id` + `external_id`;
- deduplicacao por escola/camera/aluno antes do envio de presenca ao SaaS.
- multiplas amostras faciais por aluno para melhorar reconhecimento com variacao de angulo/luz.
- auditoria operacional em `recognition_events` para success, duplicate, no_match, ambiguous_match, error e eventos de manutencao biometrica.
- endpoints protegidos para diagnostico, revisao de duplicados e exclusao LGPD de amostras faciais.

## Quick Start

```bash
cp .env.example .env
docker-compose up -d --build
```

Healthcheck:

```bash
curl http://localhost:8001/health
```

## Variaveis Principais

```env
APP_ENV=development
REDIS_URL=redis://redis:6379
DATABASE_URL=postgresql://user:password@db:5432/reconhecimento
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
RECOGNITION_API_KEYS=dev-recognition-key
SIMILARITY_THRESHOLD=0.75
MATCH_AMBIGUITY_MARGIN=0.02
MAX_FILE_SIZE_MB=10
PHOTO_URL_ALLOWED_HOSTS=res.cloudinary.com
PHOTO_URL_TIMEOUT_SECONDS=8
USE_GPU=false
SCHOOL_ID=escola_1
CAMERA_ID=entrada_principal
SAAS_PRESENCE_WEBHOOK_URL=http://host.docker.internal:8000/api/recognition/presences
SAAS_WEBHOOK_SECRET=webhook-secret
PRESENCE_DEDUP_WINDOW_SECONDS=300
```

`RECOGNITION_API_KEYS` aceita uma lista separada por virgula para facilitar rotacao de chave.

## Autenticacao

Endpoints sob `/api` exigem uma das credenciais:

```http
Authorization: Bearer dev-recognition-key
```

ou:

```http
X-API-Key: dev-recognition-key
```

## Endpoints

### POST /api/register

Cadastra um aluno e grava o embedding facial.

```bash
curl -X POST http://localhost:8001/api/register \
  -H "Authorization: Bearer dev-recognition-key" \
  -F "school_id=escola_1" \
  -F "external_id=5" \
  -F "nome=Maria Silva" \
  -F "file=@foto.jpg"
```

`school_id` e `external_id` sao opcionais neste endpoint para manter o teste local simples. Se `external_id` nao for enviado, o servico usa o ID local gerado como fallback.

### POST /api/students/sync

Endpoint interno recomendado para o SaaS sincronizar alunos com a identidade correta.

```bash
curl -X POST http://localhost:8001/api/students/sync \
  -H "Authorization: Bearer dev-recognition-key" \
  -F "school_id=escola_1" \
  -F "external_id=5" \
  -F "name=Mateus" \
  -F "file=@foto.jpg"
```

Se o aluno ja existir, o endpoint atualiza nome e embedding. Sem `file`, ele apenas atualiza o nome de aluno ja existente; para aluno novo, o `file` e obrigatorio.

Cada `file` enviado tambem cria uma nova amostra facial em `embeddings`. O aluno continua tendo uma identidade unica por `school_id + external_id`.

Tambem e possivel enviar `photo_url` em vez de `file`. Por seguranca, o download remoto so aceita HTTPS e hosts em `PHOTO_URL_ALLOWED_HOSTS` (por padrao `res.cloudinary.com`).

### POST /sync/aluno

Endpoint de compatibilidade para o `backend_v2` legado. Recebe JSON:

```json
{
  "external_id": "5",
  "nome": "Mateus",
  "empresa_id": 1,
  "photo_url": "https://res.cloudinary.com/.../foto.jpg"
}
```

`empresa_id=1` vira `school_id=escola_1`. Se `photo_url` vier preenchido, o recognition-service baixa a imagem validada e cria a amostra facial.

### POST /api/students/faces

Adiciona uma nova amostra facial para um aluno ja sincronizado.

```bash
curl -X POST http://localhost:8001/api/students/faces \
  -H "Authorization: Bearer dev-recognition-key" \
  -F "school_id=escola_1" \
  -F "external_id=5" \
  -F "file=@foto_angulo_direito.jpg"
```

Recomendacao operacional: manter 3 a 5 amostras boas por aluno, variando levemente angulo e iluminacao. Evite cadastrar varias vezes a mesma foto.

### GET /api/students/faces

Lista amostras faciais de um aluno sem retornar embedding cru nem imagem.

```bash
curl "http://localhost:8001/api/students/faces?school_id=escola_1&external_id=5" \
  -H "Authorization: Bearer dev-recognition-key"
```

Resposta inclui `count`, `ids` e `created_at` de cada amostra.

### DELETE /api/students/faces/{face_sample_id}

Remove uma amostra facial especifica. A confirmacao explicita evita apagar amostra do aluno errado.

```bash
curl -X DELETE "http://localhost:8001/api/students/faces/1002?school_id=escola_1&external_id=5&confirm_external_id=5" \
  -H "Authorization: Bearer dev-recognition-key"
```

### DELETE /api/students/faces

Exclui todas as amostras biometricas de um aluno. Presencas historicas permanecem. Por padrao o aluno local fica cadastrado, mas sem embeddings para reconhecimento.

```bash
curl -X DELETE "http://localhost:8001/api/students/faces?school_id=escola_1&external_id=5&confirm_external_id=5" \
  -H "Authorization: Bearer dev-recognition-key"
```

`remove_student=true` so remove o aluno local se nao houver presencas historicas. Se houver historico, o endpoint retorna conflito para preservar auditoria.

### GET /api/students/duplicates

Lista possiveis duplicados no mesmo `school_id`, com `external_id` diferentes, por nomes parecidos e/ou embeddings proximos. A resposta nao inclui embeddings crus.

```bash
curl "http://localhost:8001/api/students/duplicates?school_id=escola_1&embedding_distance_threshold=0.08&name_similarity_threshold=0.88" \
  -H "Authorization: Bearer dev-recognition-key"
```

### POST /api/students/duplicates/archive

Arquiva o cadastro duplicado e mantem o aluno correto intacto. O reconhecimento ignora alunos arquivados, mas presencas historicas nao sao apagadas.

```bash
curl -X POST http://localhost:8001/api/students/duplicates/archive \
  -H "Authorization: Bearer dev-recognition-key" \
  -F "school_id=escola_1" \
  -F "correct_external_id=5" \
  -F "duplicate_external_id=6" \
  -F "confirmation=archive:escola_1:5:6" \
  -F "reason=duplicado confirmado por secretaria"
```

Procedimento recomendado:

1. Use `GET /api/students/duplicates` para levantar candidatos.
2. Confira no SaaS qual `external_id` e o aluno correto.
3. Liste amostras dos dois alunos com `GET /api/students/faces`.
4. Arquive apenas o `duplicate_external_id` com a confirmacao `archive:{school_id}:{correct_external_id}:{duplicate_external_id}`.
5. Nao apague presencas historicas; elas sao trilha operacional.

### POST /api/recognize

Enfileira uma tarefa de reconhecimento facial.

```bash
curl -X POST http://localhost:8001/api/recognize \
  -H "Authorization: Bearer dev-recognition-key" \
  -F "file=@foto.jpg"
```

Resposta:

```json
{
  "status": "processing",
  "job_id": "12345abc",
  "message": "Reconhecimento facial em processamento"
}
```

### GET /api/recognize/{job_id}

Consulta o status de um job.

```bash
curl http://localhost:8001/api/recognize/12345abc \
  -H "Authorization: Bearer dev-recognition-key"
```

### POST /api/recognize/sync

Reconhecimento sincrono apenas para identificacao, sem criar presenca local e sem enviar webhook ao SaaS. Esse e o endpoint recomendado para o `backend_v2` atender a tela existente `POST /api/reconhecimento/facial`, porque o backend cria a presenca e as notificacoes nesse fluxo.

```bash
curl -X POST http://localhost:8001/api/recognize/sync \
  -H "Authorization: Bearer dev-recognition-key" \
  -F "file=@foto.jpg"
```

Resposta de sucesso:

```json
{
  "status": "success",
  "student_id": "5",
  "external_id": "5",
  "confidence": 0.95,
  "face_sample_id": 1001
}
```

O endpoint legado `POST /facial` tambem existe para compatibilidade, protegido pela mesma API key.

## Camera Local

```bash
set RECOGNITION_API_KEYS=dev-recognition-key
python camera_recognition.py
```

No PowerShell:

```powershell
$env:RECOGNITION_API_KEYS = "dev-recognition-key"
python camera_recognition.py
```

## Evento de Presenca para o SaaS

O recognition-service nao deve enviar WhatsApp ou SMS diretamente. Quando reconhece um aluno, ele envia um evento assinado para o SaaS; o SaaS consulta o responsavel do aluno e dispara a mensagem.

Configure:

```env
SAAS_PRESENCE_WEBHOOK_URL=http://host.docker.internal:8000/api/recognition/presences
SAAS_WEBHOOK_SECRET=webhook-secret
SCHOOL_ID=escola_1
CAMERA_ID=entrada_principal
PRESENCE_DEDUP_WINDOW_SECONDS=300
```

Payload enviado ao SaaS:

```json
{
  "event": "presence_detected",
  "event_id": "presence:escola_1:4",
  "school_id": "escola_1",
  "camera_id": "entrada_principal",
  "presence_id": 4,
  "student_id": "5",
  "student_name": "Mateus",
  "confidence": 1.0,
  "detected_at": "2026-05-20T10:15:00+00:00",
  "message_template": "{student_name} chegou na escola as {local_time}"
}
```

Headers:

```http
Idempotency-Key: presence:escola_1:4
X-Recognition-Signature: sha256=<hmac_sha256_do_payload>
```

O `student_id` enviado ao SaaS e sempre `alunos.external_id`, nunca o ID local da tabela do recognition-service. O SaaS deve validar a assinatura com `SAAS_WEBHOOK_SECRET`, ignorar eventos repetidos pelo `Idempotency-Key` e enviar a mensagem ao responsavel. Exemplo: `Mateus chegou na escola as 07:15`.

Antes de inserir uma nova presenca, o worker aplica uma trava Redis atomica com `SET NX EX` na chave:

```text
presence:dedup:{school_id}:{camera_id}:{external_id}
```

Se a mesma camera reconhecer o mesmo aluno dentro de `PRESENCE_DEDUP_WINDOW_SECONDS`, o job retorna:

```json
{
  "status": "duplicate",
  "student_id": "5",
  "message": "Presenca ja registrada recentemente"
}
```

Se duas identidades diferentes ficarem proximas demais no ranking de embeddings, o recognition-service nao cria presenca nem envia webhook. Nesse caso o job retorna `ambiguous_match`, para evitar mandar presença para o `external_id` errado. Ajuste fino em:

```env
MATCH_AMBIGUITY_MARGIN=0.02
```

Esse estado normalmente indica cadastro duplicado ou fotos muito parecidas entre alunos diferentes e deve ser revisado antes de liberar notificacao automatica.

Eventos `ambiguous_match` sao gravados em `recognition_events` com candidatos, distancias e `face_sample_id`, sem embedding cru e sem imagem. Para consultar:

```bash
curl "http://localhost:8001/api/recognition-events/ambiguous?limit=50" \
  -H "Authorization: Bearer dev-recognition-key"
```

## Diagnostico Operacional

Endpoint protegido:

```bash
curl http://localhost:8001/api/diagnostics \
  -H "Authorization: Bearer dev-recognition-key"
```

Retorna estado de database, Redis, fila RQ, modelo InsightFace carregado ou nao, `school_id`, `camera_id`, webhook configurado, ultima presenca, ultimo `recognition_event` e ultimo erro de webhook. Nao retorna API keys, webhook secret nem URLs sensiveis.

## Auditoria e LGPD

`presencas` continua sendo a fonte de presenca real. `recognition_events` e auditoria operacional para entender por que o reconhecimento criou presenca, ignorou duplicidade, recusou match ambiguo, nao encontrou aluno ou falhou.

A exclusao biometrica remove linhas de `embeddings` e atualiza `alunos.embedding` para a amostra restante mais recente ou `NULL`. Imagens brutas nao sao salvas por padrao. Exclusoes e arquivamentos tambem geram eventos de auditoria.

## Banco

O schema inicial fica em `db/init/001_schema.sql` e roda automaticamente quando o volume do Postgres e criado pela primeira vez.

Volumes existentes devem ser atualizados com migrations versionadas:

```bash
docker compose run --rm migrate
```

As migrations ficam em `db/migrations/` e sao registradas na tabela `schema_migrations`.

O reconhecimento consulta a tabela `embeddings`:

```sql
SELECT a.id, a.school_id, a.external_id, a.nome, e.id, e.embedding <-> :embedding AS distance
FROM embeddings e
JOIN alunos a ON a.id = e.aluno_id
WHERE a.school_id = :school_id
  AND a.archived_at IS NULL
ORDER BY distance
LIMIT 1;
```

`alunos.embedding` fica como amostra principal/compatibilidade; as amostras adicionais ficam em `embeddings`.

`recognition_events` possui indices por `school_id`, `camera_id`, `external_id`, `status` e `created_at` para diagnostico de operacao escolar.

## Dependencias Externas

O recognition-service apenas reconhece, registra presenca local e envia webhook assinado. O backend SaaS (`backend_v2`) continua responsavel por validar assinatura/idempotencia, consultar responsaveis e enviar WhatsApp/SMS.
