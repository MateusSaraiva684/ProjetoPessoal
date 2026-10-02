# URLs oficiais dos serviços

Estas são as URLs públicas e internas que devem ser usadas em produção.
Substitua os domínios de exemplo pelos domínios atribuídos pelo Render e
mantenha os valores também no secret manager.

| Serviço | URL oficial | Uso |
|---|---|---|
| Frontend | `https://app.seu-dominio.tld` | Interface web |
| Backend | `https://api.seu-dominio.tld` | API FastAPI |
| Health do backend | `https://api.seu-dominio.tld/api/health` | Readiness público |
| Recognition-service | `https://recognition.seu-dominio.tld` | API facial |
| Health do recognition-service | `https://recognition.seu-dominio.tld/api/health` | Readiness do reconhecimento |

## Endpoints internos

Use a URL interna do Render para o PostgreSQL quando o backend estiver no
mesmo workspace. Para Redis externo, use uma URL TLS e não exponha o serviço
publicamente.

## Regras de configuração

- `FRONTEND_URL` deve conter somente a origem HTTPS do frontend.
- `RECOGNITION_SERVICE_URL` deve apontar para a origem do recognition-service,
  sem duplicar `/api`.
- O frontend deve usar `VITE_API_URL=https://api.seu-dominio.tld`.
- O health oficial do backend é `/api/health`, não `/health`.
- Configure `APP_VERSION` e `GIT_COMMIT` em cada deploy; o backend e o
  recognition-service retornam esses valores no health.
- URLs reais devem ser atualizadas neste arquivo após o provisionamento e
  revisadas junto com cada deploy.
