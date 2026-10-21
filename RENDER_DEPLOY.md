# Deploy no Render

O blueprint `render.yaml` publica somente o backend e o frontend. O banco
principal é o PostgreSQL do Supabase; o `recognition-service` fica fora do
deploy até que uma plataforma própria seja definida.

## Backend

- Serviço: `sistema-escolar-backend`
- Tipo: Docker Web Service
- Diretório: `backend_v2 (2)/backend_v2`
- Health check: `/api/health`
- O comando do Dockerfile executa `alembic upgrade head` antes de iniciar o
  Uvicorn.

Preencha no Render as variáveis marcadas como secret no blueprint. O backend
precisa do PostgreSQL do Supabase, Redis e `SECRET_KEY`. Sem o recognition-service, deixe
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

## Provedor de autenticação

Por padrão, o login usa a autenticação própria do backend, que é portátil entre
Supabase, AWS RDS e outros PostgreSQL:

```env
AUTH_PROVIDER=local
VITE_AUTH_PROVIDER=local
```

O Supabase Auth continua disponível como opção. Para ativá-lo, configure:

No backend:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`

E no frontend:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Use a URL do projeto e a chave pública `anon`. Nunca coloque a chave
`service_role` no frontend. O backend valida o access token no endpoint oficial
do Supabase e mantém as roles e permissões na tabela local `usuarios`.

Para usar o Supabase Auth, altere ambos os provedores para `supabase`:

```env
AUTH_PROVIDER=supabase
VITE_AUTH_PROVIDER=supabase
```

O banco continua sendo definido separadamente por `DATABASE_URL`.

No modo `local`, mantenha `SYNC_ADMIN_PASSWORD_ON_STARTUP=true`. O valor de
`ADMIN_PASSWORD` no Render é a fonte única da senha do administrador; a cada
deploy o registro local é sincronizado. Use uma senha com pelo menos 12
caracteres.