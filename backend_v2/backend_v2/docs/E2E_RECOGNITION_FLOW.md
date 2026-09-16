# E2E Recognition Flow

Este roteiro valida, por HTTP, o acoplamento real entre `backend_v2` e
`recognition-service` com servicos vivos. Ele nao inicia servicos, nao cria
usuarios, nao roda migrations automaticamente e nao substitui Cloudinary.

## Pre-requisitos

- Backend rodando, por exemplo `http://localhost:8000`.
- Recognition-service rodando, por exemplo `http://localhost:8001`.
- PostgreSQL do backend online.
- PostgreSQL do recognition-service online.
- Redis online.
- Worker do recognition-service rodando quando o fluxo async/camera for usado.
- Frontend opcional rodando, por exemplo `http://localhost:5173`.
- Cloudinary configurado no backend quando o sync biometric usar `photo_url`.
- Credenciais de um superusuario para `/api/admin/system-health`.
- Credenciais de uma escola/usuario de teste para criar alunos.
- Segredo `RECOGNITION_WEBHOOK_SECRET` igual ao backend.
- Imagens reais de teste em `tools/e2e/assets/`.

## Variaveis

Crie um arquivo local `.env.e2e` a partir de `.env.e2e.example`:

```powershell
python tools\e2e\prepare_env_e2e.py
```

Preencha, sem commitar segredos:

- `BACKEND_URL`
- `FRONTEND_URL`
- `RECOGNITION_SERVICE_URL`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `TEST_SCHOOL_EMAIL`
- `TEST_SCHOOL_PASSWORD`
- `RECOGNITION_WEBHOOK_SECRET`
- `RECOGNITION_API_TOKEN`
- `TEST_IMAGE_VALID`
- `TEST_IMAGE_NO_FACE`
- `TEST_IMAGE_SECOND_SAMPLE`
- `E2E_REQUIRE_NOTIFICATIONS`
- `E2E_RESPONSAVEL_NOME`
- `E2E_RESPONSAVEL_TELEFONE`
- `E2E_RESPONSAVEL_EMAIL`
- `E2E_RESPONSAVEL_PARENTESCO`

`RECOGNITION_API_TOKEN` precisa ser aceito por `RECOGNITION_API_KEYS` no
recognition-service. Ele tambem permite validar diretamente as amostras em
`GET /api/students/faces`.

Use `E2E_REQUIRE_NOTIFICATIONS=true` para a validacao completa de responsaveis
e NotificationOutbox. Nesse modo o script falha se nao conseguir criar/vincular
responsavel ao aluno de teste ou se uma presenca valida nao gerar notificacao
`pending`.

## Preparar .env.e2e no Windows

Roteiro simples no PowerShell:

```powershell
cd C:\Users\mateu\Desktop\backend_v2
python tools\e2e\prepare_env_e2e.py
notepad .env.e2e
```

Depois preencha ou confira manualmente:

- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `TEST_SCHOOL_EMAIL`
- `TEST_SCHOOL_PASSWORD`
- `RECOGNITION_WEBHOOK_SECRET`
- `RECOGNITION_API_TOKEN`

O script `prepare_env_e2e.py` pode preencher automaticamente apenas algumas
chaves permitidas a partir do `.env` local, como admin, webhook secret e token
do recognition-service. Ele nao copia `DATABASE_URL`, `SECRET_KEY`,
`CLOUDINARY_API_SECRET` nem outros segredos desnecessarios para o E2E.

Coloque as imagens reais em:

```text
tools/e2e/assets/student_valid.jpg
tools/e2e/assets/student_second.jpg
tools/e2e/assets/no_face.jpg
```

Verifique o backend:

```text
http://localhost:8000/docs
```

Verifique o recognition-service:

```text
http://localhost:8001/api/health
```

Rode o E2E real apenas depois que servicos, bancos, Redis, worker e imagens
estiverem prontos:

```powershell
python tools\e2e\e2e_full_flow.py --env-file .env.e2e
```

## Banco Render local vs produção

A URL interna do Render normalmente usa um host parecido com `dpg-...-a`.
Essa URL costuma funcionar apenas dentro da rede privada do Render.

Para rodar o backend local apontando para um banco do Render, use a
`External Database URL` do Render, nao a URL interna. A alternativa mais segura
para E2E local continua sendo PostgreSQL local ou um banco staging descartavel.

Se aparecer erro como `getaddrinfo failed`, provavelmente o host do banco esta
inacessivel a partir da sua maquina ou o `DATABASE_URL` esta incorreto.
Este roteiro nao altera `DATABASE_URL` automaticamente.

## Migrations

Backend:

```powershell
alembic upgrade head
```

Recognition-service:

```powershell
cd C:\Users\mateu\Desktop\recognition-service
python scripts\apply_migrations.py
```

Se o recognition-service estiver em Docker Compose, rode o comando equivalente
dentro do container ou suba a stack que ja executa a inicializacao/migration
esperada pelo projeto.

## Como Rodar

No backend:

```powershell
cd C:\Users\mateu\Desktop\backend_v2
python tools\e2e\e2e_full_flow.py --env-file .env.e2e
```

O script cria alunos descartaveis com nome e inscricao iniciando por `E2E-`.
Use base local/staging propria para este teste.

## Validacao de Responsaveis e Notificacoes

O script chama:

```text
POST /api/alunos/{aluno_id}/responsaveis
```

com os dados definidos por:

- `E2E_RESPONSAVEL_NOME`
- `E2E_RESPONSAVEL_TELEFONE`
- `E2E_RESPONSAVEL_EMAIL`
- `E2E_RESPONSAVEL_PARENTESCO`

O backend cria ou reutiliza o responsavel e vincula ao aluno. Se o mesmo
telefone/e-mail ja estiver vinculado ao aluno, a rota retorna o responsavel
existente sem duplicar o relacionamento.

Com `E2E_REQUIRE_NOTIFICATIONS=true`, o harness valida:

- diagnostico facial nao cria `Presenca`;
- diagnostico facial nao cria `NotificationOutbox`;
- webhook de entrada cria presenca e notificacao `pending`;
- reenvio do mesmo webhook nao cria segunda presenca nem segunda notificacao;
- webhook de saida cria presenca de saida e outra notificacao `pending`;
- mensagens contem `chegou à escola às HH:MM.` e `saiu da escola às HH:MM.`.

Com `E2E_REQUIRE_NOTIFICATIONS=false`, o script tenta vincular o responsavel,
mas nao falha se a rota ou a notificacao nao estiverem disponiveis no ambiente.
Esse modo e util para smoke test parcial.

O teste nao envia WhatsApp/e-mail real. Ele valida somente a linha
`NotificationOutbox` em status `pending`, normalmente com provider local `log`.

## O Que O Script Valida

- Login admin e login da escola no backend.
- `GET /api/admin/system-health`.
- `GET /api/health` do recognition-service.
- Criacao de aluno com foto valida por multipart.
- Criacao/vinculacao de responsavel ao aluno.
- Polling de `biometria_status` ate `ready`.
- `external_id`, `empresa_id` e `face_samples_count`.
- Listagem direta de faces no recognition-service, quando houver token.
- Adicao de segunda amostra facial.
- Remocao de uma foto/amostra biometrica.
- Foto sem rosto nao ficando `ready` e expondo erro.
- Aluno sem foto para validar `sem_foto=true`.
- Diagnostico em `/api/reconhecimento/identificar` sem criar presenca nem notificacao.
- Webhook assinado de entrada em `/api/recognition/presences`.
- Reenvio duplicado sem duplicar presenca.
- Webhook assinado de saida.
- Listagem de notificacoes, mensagens de entrada/saida e controle de duplicidade.
- Filtros em `/api/alunos/`: `search`, `biometria_status`, `sem_foto`, `turma`.
- Propagacao minima de `trace_id`.

## Interpretando Resultado

Cada etapa imprime `==> nome da etapa`. Em caso de erro, o processo termina com:

```text
E2E FAILED: motivo claro da falha
```

Falhas HTTP incluem o status code e um trecho do corpo retornado. Corrija a
causa, rode novamente e preserve a evidencia da primeira falha quando ela
indicar problema de contrato.

## Falhas Comuns

- Banco backend nao conecta: `system-health.database.status` vem `error`.
- Recognition-service offline: backend health mostra recognition offline/error ou `/api/health` falha.
- Redis offline: `/api/health` retorna `redis=error` ou HTTP 503.
- Cloudinary sem API key: `system-health.cloudinary.configured=false`; o fluxo com `photo_url` pode nao ficar `ready`.
- Imagem ausente: o runner falha antes de fazer chamadas HTTP.
- Foto sem rosto pronta indevidamente: bug no pipeline biometric; esperado e `needs_new_photo`, `failed` ou `no_photo`.
- Assinatura invalida: webhook retorna 401; confirme `RECOGNITION_WEBHOOK_SECRET` e HMAC `sha256=<digest>`.
- Evento duplicado criando nova presenca: bug de idempotencia por `recognition_event_id`.
- Evento duplicado criando nova notificacao: confira a chave unica `tipo + presenca_id + responsavel_id + canal`.
- Sem notificacao pending: confirme se o responsavel foi vinculado ao aluno e se `NOTIFICATION_PROVIDER` esta em modo local seguro, como `log`.
- Biometria nao fica `ready`: veja resposta do aluno, logs do backend, logs do recognition-service e se `RECOGNITION_API_TOKEN`/Cloudinary estao alinhados.

## Logs e Trace ID

O diagnostico envia `X-Trace-Id` e espera o mesmo `trace_id` na resposta.
O webhook tambem envia `trace_id` no payload e em `X-Trace-Id`. Confira nos logs:

- Backend: logs de reconhecimento, sync biometric e webhook.
- Recognition-service: logs de `/api/students/sync`, `/api/students/faces`, worker e webhook.

## Checklist Final

- Health backend ok.
- Health recognition-service ok.
- Aluno criado.
- Biometria `ready`.
- Responsavel criado/vinculado ao aluno.
- Segunda amostra adicionada.
- Uma amostra removida sem inconsistencia.
- Foto sem rosto rejeitada/erro normalizado.
- Diagnostico nao cria presenca.
- Webhook entrada cria presenca.
- Webhook duplicado nao duplica.
- Webhook saida cria saida.
- Notificacao pending criada para entrada.
- Notificacao pending criada para saida.
- Mensagens de entrada/saida corretas.
- Duplicado nao cria notificacao duplicada.
- Filtros funcionando.
- `trace_id` visivel no diagnostico e nos logs.

## Checklist de Execucao

- [ ] `.env.e2e` existe
- [ ] `BACKEND_URL` abre `/docs`
- [ ] `RECOGNITION_SERVICE_URL` abre `/api/health`
- [ ] `ADMIN_EMAIL`/`ADMIN_PASSWORD` funcionam
- [ ] `TEST_SCHOOL_EMAIL`/`TEST_SCHOOL_PASSWORD` funcionam
- [ ] `RECOGNITION_API_TOKEN` bate com `RECOGNITION_API_KEYS` do recognition-service
- [ ] `RECOGNITION_WEBHOOK_SECRET` bate nos dois servicos
- [ ] Redis esta rodando
- [ ] Worker esta rodando
- [ ] PostgreSQL backend acessivel
- [ ] PostgreSQL recognition acessivel
- [ ] Imagens existem em `tools/e2e/assets`
- [ ] `alembic upgrade head` executado
- [ ] E2E executado

## Teste Manual Com Camera Real

Este harness nao valida captura ao vivo. Para fechar o fluxo com camera real,
rode o recognition-service com a camera configurada (`CAMERA_INDEX`, `SCHOOL_ID`,
`CAMERA_ID`, webhook e API keys), inicie o worker, abra a camera e confirme que
uma deteccao real gera webhook assinado para o backend e aparece no painel.
