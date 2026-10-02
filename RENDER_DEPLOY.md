# Deploy no Render

O blueprint `render.yaml` publica somente o backend e o frontend. O
`recognition-service` fica fora do deploy até que uma plataforma própria seja
definida.

## Backend

- Serviço: `sistema-escolar-backend`
- Tipo: Docker Web Service
- Diretório: `backend_v2 (2)/backend_v2`
- Health check: `/api/health`
- O comando do Dockerfile executa `alembic upgrade head` antes de iniciar o
  Uvicorn.

Preencha no Render as variáveis marcadas como secret no blueprint. O backend
precisa de PostgreSQL, Redis e `SECRET_KEY`. Sem o recognition-service, deixe
`RECOGNITION_SERVICE_URL`, `FACE_RECOGNITION_SERVICE_URL` e
`RECOGNITION_API_BASE_URL` vazias.

`CELERY_WORKER_REQUIRED=false` permite que a API fique saudável sem um
worker separado. Tarefas de notificações que dependem do Celery não serão
processadas até que um worker seja publicado.

## Frontend

- Serviço: `sistema-escolar-frontend`
- Tipo: Static Site
- Diretório: `frontend_v2`
- Build: `npm install && npm run build`
- Publicação: `dist`
- `VITE_API_URL`: URL pública do backend, por exemplo
  `https://sistema-escolar-backend.onrender.com`

O rewrite de SPA já está incluído no blueprint. Depois do primeiro deploy,
configure `FRONTEND_URL` no backend com a URL pública do frontend e faça um
novo deploy.