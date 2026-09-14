# 🏛️ DIAGRAMAS DE ARQUITETURA

> **Atualização:** os diagramas abaixo preservam a arquitetura histórica do MVP. A arquitetura implementada atualmente inclui um `recognition-service` separado, Redis/RQ, PostgreSQL com pgvector e webhook HMAC. Consulte [07_STATUS_ATUAL_2026.md](07_STATUS_ATUAL_2026.md) antes de usar estes diagramas para decisões de deploy.

**Público:** Arquitetos, Tech Leads, Decision Makers  
**Tempo de leitura:** 45 minutos  
**Total de Diagramas:** 12

---

## I. ARQUITETURA GERAL ATUAL (MVP)

### Diagrama 1: Stack Tecnológico Completo

```
┌────────────────────────────────────────────────────────────────┐
│                     CLIENTE (Browser)                          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  React + Vite (SPA)                                    │  │
│  │  - Pages: Alunos, Presencas, Admin, Reconhecimento   │  │
│  │  - Components: Forms, Cards, Tables                  │  │
│  │  - State: Context API + localStorage                │  │
│  └─────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              │
                    HTTPS (TLS 1.2+)
                              │
┌────────────────────────────────────────────────────────────────┐
│                      API GATEWAY                               │
│                    (localhost:8000)                            │
│  FastAPI + Pydantic + SQLAlchemy                              │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ ROUTES (5 blueprints)                                   │ │
│  │ - /auth (login, register, refresh, logout, me)         │ │
│  │ - /alunos (CRUD, turmas, search)                       │ │
│  │ - /presencas (manual, history)                         │ │
│  │ - /admin (users, stats, alunos)                        │ │
│  │ - /reconhecimento (facial recognition)                │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ SERVICES (8 classes)                                    │ │
│  │ - AuthService (JWT, tokens)                            │ │
│  │ - AlunoService (CRUD, filtering)                       │ │
│  │ - PresencaService (manual attendance)                  │ │
│  │ - ReconhecimentoService (orchestration)                │ │
│  │ - FaceRecognitionService (external API)                │ │
│  │ - AdminService (user management)                       │ │
│  │ - NotificationService (SMS/Email)                      │ │
│  │ - MediaService (Cloudinary)                            │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ REPOSITORIES (3 classes)                                │ │
│  │ - AlunoRepository                                       │ │
│  │ - UsuarioRepository                                     │ │
│  │ - PresencaRepository                                    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ MIDDLEWARE                                              │ │
│  │ - CORS (Frontend whitelist)                             │ │
│  │ - Logging (Console + File)                              │ │
│  │ - Error Handling (Exception handlers)                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ CORE                                                     │ │
│  │ - Config (Environment variables)                        │ │
│  │ - Security (JWT, bcrypt)                                │ │
│  │ - Database (SQLAlchemy engine, session)                 │ │
│  │ - Exceptions (Custom error classes)                     │ │
│  └─────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
                              │
                       SQL (tcp:5432)
                              │
┌────────────────────────────────────────────────────────────────┐
│                    POSTGRESQL 15                               │
│                                                                │
│  ├─ usuarios                                                  │
│  ├─ alunos                                                    │
│  ├─ responsaveis                                              │
│  ├─ aluno_responsaveis (junction)                             │
│  ├─ presencas (7M+ rows for scale)                            │
│  ├─ face_embeddings (vector storage)                          │
│  └─ refresh_tokens                                            │
└────────────────────────────────────────────────────────────────┘
                              │
                     Backup (S3)
                              │
┌────────────────────────────────────────────────────────────────┐
│          EXTERNAL INTEGRATIONS                                │
│                                                                │
│  ├─ Cloudinary (CDN for student photos)                       │
│  ├─ Face Recognition API (ML inference)                       │
│  ├─ Twilio (SMS notifications)                                │
│  └─ SendGrid (Email notifications)                            │
└────────────────────────────────────────────────────────────────┘
```

---

## II. FLUXO DE AUTENTICAÇÃO

### Diagrama 2: Login com JWT + Refresh Token

```
┌─────────────────────────────────────────────────────────────────┐
│ USER BROWSER                                                    │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ Input: email="mateus@escola.com", password="secret123"  │   │
│ └──────────────────┬───────────────────────────────────────┘   │
└────────────────────┼─────────────────────────────────────────────┘
                     │ POST /auth/login
                     ▼
        ┌──────────────────────────────────┐
        │  FastAPI Route Handler           │
        │  ─────────────────────           │
        │  1. Parse JSON input             │
        │  2. Validate schema (Pydantic)   │
        │  3. Call AuthService.login()     │
        └──────────────┬───────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────┐
        │  AuthService.login()             │
        │  ─────────────────────           │
        │  1. Query user by email          │
        │  2. Verify bcrypt password       │
        │  3. Generate JWT token (1h)      │
        │  4. Generate refresh token (30d) │
        │  5. Store refresh in DB          │
        └──────────────┬───────────────────┘
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
    ┌──────────────────┐  ┌──────────────────┐
    │  JWT Token       │  │  Refresh Token   │
    │  ──────────────  │  │  ──────────────  │
    │  Header: header  │  │  Random UUID     │
    │  Payload:        │  │  Stored in DB    │
    │  - user_id: 42   │  │  TTL: 30 days    │
    │  - email: ...    │  │  Revocable       │
    │  - exp: 1h       │  │                  │
    │  Signature: hmac │  │                  │
    └──────────────────┘  └──────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────┐
        │  HTTP 200 Response               │
        │  ─────────────────────           │
        │  {                               │
        │    "access_token": "eyJ0eX...",  │
        │    "refresh_token": "abc123...", │
        │    "token_type": "bearer",       │
        │    "expires_in": 3600            │
        │  }                               │
        └──────────────┬───────────────────┘
                       │
┌──────────────────────┴─────────────────────┐
│ USER BROWSER - LocalStorage                │
│ ┌──────────────────────────────────────┐  │
│ │ access_token: eyJ0eX...              │  │
│ │ refresh_token: abc123...             │  │
│ │ user: {id: 42, email: "mateus@..."}│  │
│ └──────────────────────────────────────┘  │
└──────────────────────────────────────────────┘

        ┌────────────────────────────────────┐
        │  Subsequent Requests                │
        │  ─────────────────────────          │
        │  Header: Authorization: Bearer ...  │
        │                                     │
        │  FastAPI extracts token             │
        │  Validates JWT signature            │
        │  Extracts user_id from claims       │
        │  Proceeds with request              │
        └────────────────────────────────────┘

        ┌────────────────────────────────────┐
        │  Token Expires (1 hour)             │
        │  ─────────────────────              │
        │  Client gets 401 Unauthorized       │
        │                                     │
        │  Client calls POST /auth/refresh    │
        │  with refresh_token                 │
        │                                     │
        │  Server validates refresh token     │
        │  Issues new access_token (1h)       │
        │  Optionally rotates refresh token   │
        └────────────────────────────────────┘
```

---

## III. FLUXO DE RECONHECIMENTO FACIAL

### Diagrama 3: Processo de Registrar Presença com IA

```
┌─────────────────────────────┐
│  STUDENT TAKES PHOTO        │
│  (Câmera / Upload)          │
└──────────────┬──────────────┘
               │ Image Binary
               ▼
        ┌──────────────────────────┐
        │  Frontend Upload         │
        │  - Resize (max 2MB)      │
        │  - Convert to base64     │
        │  - Validate format       │
        └──────────┬───────────────┘
                   │ POST /reconhecimento
                   ▼
        ┌──────────────────────────────────────┐
        │  Backend - ReconhecimentoService     │
        │  ──────────────────────────────────  │
        │  1. Validate input (base64, size)    │
        │  2. Log request (audit trail)        │
        │  3. Call FaceRecognitionService      │
        └──────────┬───────────────────────────┘
                   │
        ┌──────────▼─────────────────┐
        │  FaceRecognitionService    │
        │  (External API)            │
        │  ──────────────────────────│
        │  - Endpoint: /extract      │
        │  - Timeout: 30 seconds ✅  │
        │  - Rate limit: 100 req/day │
        └──────────┬────────────────┘
                   │
            ┌──────▼──────┐
            │ ML Pipeline │
            │ ────────────│
            │ 1. Face det │
            │ 2. Extract  │
            │ 3. Embed(512D)
            │ 4. Quality  │
            └──────┬──────┘
                   │
        ┌──────────▼──────────────────────┐
        │  Response: 200 OK               │
        │  {                              │
        │    "embedding": [0.2, 0.5...],  │
        │    "confidence": 0.92           │
        │  }                              │
        └──────────┬──────────────────────┘
                   │
        ┌──────────▼──────────────────────────────┐
        │  Search Similar Embeddings              │
        │  ───────────────────────────────        │
        │  Query face_embeddings table            │
        │  Order by Euclidean distance < 0.6     │
        │  ⚠️  PROBLEMA: Sem índice vetorial!     │
        │  Performance: O(n) instead of O(log n)  │
        └──────────┬───────────────────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │  Top Match Found                │
        │  {                              │
        │    "aluno_id": 42,              │
        │    "distance": 0.41,  (< 0.6) ✅
        │    "confidence": 0.92  (> 0.7) │
        │  }                              │
        └──────────┬──────────────────────┘
                   │
        ┌──────────▼──────────────────────────┐
        │  Save Presenca                       │
        │  ────────────────────────────       │
        │  INSERT INTO presencas VALUES (     │
        │    aluno_id=42,                     │
        │    timestamp=NOW(),                 │
        │    origem='facial',                 │
        │    confianca=0.92,                  │
        │    status='confirmado'   ✅ Valid  │
        │  )                                  │
        │  ⚠️  PROBLEMA: Sem dedup check!     │
        └──────────┬───────────────────────┘
                   │
        ┌──────────▼──────────────────────────┐
        │  Async: Notify Guardian             │
        │  ────────────────────────────       │
        │  (Celery task)                      │
        │  - SMS: "Mateus registrou presença" │
        │  - Email: presenca@...             │
        │  - Push: App notification           │
        └────────────────────────────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │  HTTP 200 Response               │
        │  {                               │
        │    "aluno_id": 42,               │
        │    "nome": "Mateus Silva",       │
        │    "turma": "M1",                │
        │    "confianca": 0.92,            │
        │    "timestamp": "2026-04-18..."  │
        │  }                               │
        └─────────────────────────────────┘
```

---

## IV. FLUXO DE DADOS: LISTAGEM DE ALUNOS

### Diagrama 4: Query Path com Paginação

```
GET /alunos?page=2&limit=50

       ┌─────────────────────────────────┐
       │  Route Handler                  │
       │  ─────────────────────          │
       │  1. Extract: page=2, limit=50   │
       │  2. Validate: page >= 1, limit  │
       │  3. Calculate: skip = 50        │
       │  4. Call Service                │
       └──────────┬──────────────────────┘
                  │
       ┌──────────▼──────────────────────┐
       │  AlunoService                   │
       │  ──────────────────────────────│
       │  def listar_alunos(             │
       │    user_id=42,                  │
       │    skip=50,                     │
       │    limit=50                     │
       │  )                              │
       └──────────┬──────────────────────┘
                  │
       ┌──────────▼──────────────────────┐
       │  AlunoRepository                │
       │  ───────────────────────────    │
       │  1. Count total records         │
       │  2. Query with offset/limit     │
       └──────────┬──────────────────────┘
                  │
       ┌──────────▼──────────────────────┐
       │  SQLAlchemy ORM                 │
       │  ───────────────────────────    │
       │  SELECT * FROM alunos           │
       │  WHERE user_id = 42             │
       │  ORDER BY criado_em DESC        │
       │  LIMIT 50 OFFSET 50;            │
       └──────────┬──────────────────────┘
                  │
       ┌──────────▼──────────────────────┐
       │  PostgreSQL Query Execution     │
       │  ──────────────────────────────│
       │                                 │
       │  Index scan: (user_id)          │
       │  Filter: user_id = 42           │
       │  Sort: criado_em DESC           │
       │  Limit: 50 rows, offset 50      │
       │                                 │
       │  Time: ~50ms ✅                 │
       └──────────┬──────────────────────┘
                  │
       ┌──────────▼──────────────────────┐
       │  Return Aluno Objects (50 rows) │
       │  ──────────────────────────────│
       │  [                              │
       │    Aluno(id=75, nome=...),      │
       │    Aluno(id=74, nome=...),      │
       │    ...                          │
       │    Aluno(id=26, nome=...)       │
       │  ]                              │
       └──────────┬──────────────────────┘
                  │
       ┌──────────▼──────────────────────┐
       │  Pydantic Serialization         │
       │  ──────────────────────────────│
       │  Convert ORM → JSON             │
       │                                 │
       │  (Runs validation rules)        │
       └──────────┬──────────────────────┘
                  │
       ┌──────────▼──────────────────────┐
       │  HTTP 200 Response              │
       │  ──────────────────────────────│
       │  {                              │
       │    "data": [                    │
       │      {                          │
       │        "id": 75,                │
       │        "nome": "Aluno 1",       │
       │        "turma": "M1",           │
       │        "numero_inscricao": "..." │
       │      },                         │
       │      ...50 items total...       │
       │    ],                           │
       │    "paginacao": {               │
       │      "total": 250,              │
       │      "pagina": 2,               │
       │      "limite": 50,              │
       │      "proxima_pagina": 3,       │
       │      "paginas_totais": 5        │
       │    }                            │
       │  }                              │
       │                                 │
       │  Size: ~15KB                    │
       │  Time: 100ms total              │
       └─────────────────────────────────┘
```

---

## V. ESCALABILIDADE FUTURA (Mês 3-4)

### Diagrama 5: Arquitetura Escalada com Load Balancer

```
┌──────────────────────────────────────────────────────────┐
│  CLIENT (Browser)                                        │
│  ┌────────────────────────────────────────────────────┐ │
│  │  React SPA (Vite build)                            │ │
│  │  Hosted on: S3 + CloudFront CDN                   │ │
│  │  Assets cached: 30 days                            │ │
│  │  Performance: < 2s initial load                    │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
                         │
          HTTPS + TLS 1.2 (Global CDN)
                         │
┌──────────────────────────────────────────────────────────┐
│  API GATEWAY (Load Balancer)                             │
│  ┌────────────────────────────────────────────────────┐ │
│  │  nginx / AWS ALB                                  │ │
│  │  - SSL termination                                │ │
│  │  - Request routing                                │ │
│  │  - Rate limiting (5 req/s per IP)                │ │
│  │  - Compression (gzip)                             │ │
│  │  - Health checks (backend instances)             │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
          │                  │                │
    ┌─────▼──────┐   ┌──────▼────┐   ┌──────▼──────┐
    │ FastAPI 1  │   │ FastAPI 2  │   │ FastAPI 3   │
    │ (Port 8001)│   │ (Port 8002)│   │ (Port 8003) │
    │ 4 workers  │   │ 4 workers  │   │ 4 workers   │
    │ 4 threads  │   │ 4 threads  │   │ 4 threads   │
    └─────┬──────┘   └──────┬────┘   └──────┬──────┘
          │                 │               │
          └─────────────────┼───────────────┘
                            │
          ┌─────────────────▼─────────────────┐
          │  Redis Cache Layer               │
          │  ┌─────────────────────────────┐ │
          │  │ Session cache (TTL: 1h)     │ │
          │  │ Query cache (TTL: 5min)     │ │
          │  │ User cache (TTL: 15min)     │ │
          │  │ Rate limit counters         │ │
          │  │ Size: 6GB (1M users)        │ │
          │  └─────────────────────────────┘ │
          └─────────────────┬─────────────────┘
                            │
          ┌─────────────────▼──────────────────┐
          │  PostgreSQL Cluster                │
          │  ┌──────────────────────────────┐ │
          │  │ Primary (Write)              │ │
          │  │ - SSDs 500GB                 │ │
          │  │ - RAM 64GB                   │ │
          │  │ - Connections: 200           │ │
          │  └──────────────────────────────┘ │
          │                                   │
          │  ┌──────────────────────────────┐ │
          │  │ Replica 1 (Read)             │ │
          │  │ - SSDs 500GB                 │ │
          │  │ - Replication lag: < 1s      │ │
          │  └──────────────────────────────┘ │
          │                                   │
          │  ┌──────────────────────────────┐ │
          │  │ Replica 2 (Read)             │ │
          │  │ - SSDs 500GB                 │ │
          │  │ - For analytics              │ │
          │  └──────────────────────────────┘ │
          │                                   │
          │  ┌──────────────────────────────┐ │
          │  │ Backups                      │ │
          │  │ - Daily snapshots (30-day)   │ │
          │  │ - AWS S3 (cross-region)      │ │
          │  │ - Recovery time: 1 hour      │ │
          │  └──────────────────────────────┘ │
          └─────────────────────────────────┘

┌──────────────────────────────────────────┐
│  EXTERNAL INTEGRATIONS                   │
│  ├─ Cloudinary CDN (Photos, videos)      │
│  ├─ Face Recognition API (ML Inference)  │
│  ├─ Twilio (SMS)                         │
│  ├─ SendGrid (Email)                     │
│  └─ AWS CloudWatch (Monitoring)          │
└──────────────────────────────────────────┘

PERFORMANCE TARGETS:
- Latency P50: 50ms
- Latency P99: 500ms
- Throughput: 1000 req/s
- Uptime: 99.9%
- Concurrent users: 10,000
```

---

## VI. DEPLOYMENT ARCHITECTURE

### Diagrama 6: CI/CD Pipeline & Infrastructure

```
┌──────────────────────────────────────────────────────────────┐
│  GITHUB REPOSITORY                                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ main branch                                            │ │
│  │ ├─ app/                                                │ │
│  │ ├─ tests/                                              │ │
│  │ ├─ Dockerfile                                          │ │
│  │ ├─ docker-compose.yml                                 │ │
│  │ └─ .github/workflows/                                 │ │
│  │    ├─ ci-test.yml      (Run tests)                    │ │
│  │    ├─ ci-build.yml     (Build Docker image)          │ │
│  │    └─ cd-deploy.yml    (Deploy to production)        │ │
│  └─────────────────┬──────────────────────────────────────┘ │
└────────────────────┼──────────────────────────────────────────┘
                     │ git push
                     ▼
        ┌──────────────────────────────────┐
        │  GITHUB ACTIONS                  │
        │  ─────────────────────────────   │
        │  Trigger: On push to main        │
        └──────────────────────────────────┘
                     │
        ┌────────────▼──────────────┐
        │  Job 1: Lint & Test       │
        │  ────────────────────────│
        │  - Run: pytest (24 tests) │
        │  - Coverage: > 80%        │
        │  - Lint: flake8           │
        │  - Duration: 5 min        │
        │  Status: ✅ Pass/❌ Fail  │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────────────┐
        │  Job 2: Build Docker Image       │
        │  ───────────────────────────────│
        │  - FROM python:3.11              │
        │  - COPY app/                     │
        │  - RUN pip install -r req.txt    │
        │  - CMD ["uvicorn", "main:app"]   │
        │  - Tag: v1.2.3                   │
        │  Duration: 3 min                 │
        └────────────┬──────────────────────┘
                     │
        ┌────────────▼──────────────────────┐
        │  Job 3: Push to Registry         │
        │  ───────────────────────────────│
        │  - Push to AWS ECR               │
        │  - Tag: latest, v1.2.3           │
        │  - Size: 250MB (gzip: 80MB)      │
        └────────────┬──────────────────────┘
                     │
        ┌────────────▼────────────────────────────┐
        │  Job 4: Deploy to Production           │
        │  ──────────────────────────────────────│
        │  - Update K8s deployment manifest      │
        │  - Image: aws-account.ecr.../app:v1.2.3
        │  - kubectl apply -f deployment.yaml    │
        │  - Wait for health checks              │
        │  Duration: 5 min                       │
        └────────────┬────────────────────────────┘
                     │
        ┌────────────▼──────────────────────┐
        │  AWS ECS / Kubernetes             │
        │  ──────────────────────────────  │
        │                                   │
        │  Deployment Strategy:             │
        │  - Rolling deployment             │
        │  - Max surge: 25%                 │
        │  - Max unavailable: 0%            │
        │                                   │
        │  Pod 1 (running v1.2.2) ──►      │
        │         (killed, draining)        │
        │         (started v1.2.3)          │
        │                                   │
        │  Pod 2 (running v1.2.2) ──►      │
        │         (killed, draining)        │
        │         (started v1.2.3)          │
        │                                   │
        │  Pod 3 (running v1.2.3) ✅       │
        │                                   │
        │  Result: 0 downtime ✅            │
        └────────────┬──────────────────────┘
                     │
        ┌────────────▼──────────────────────┐
        │  Smoke Tests                      │
        │  ──────────────────────────────  │
        │  - Health check: /health          │
        │  - Login test                     │
        │  - Database connectivity          │
        │  Status: ✅ All green             │
        └─────────────────────────────────┘
```

---

## VII. DATABASE SCHEMA

### Diagrama 7: Tabelas e Relacionamentos

```
┌─────────────────────────┐
│     USUARIOS            │
├─────────────────────────┤
│ id (PK)                 │
│ nome (VARCHAR)          │
│ email (VARCHAR UNIQUE)  │◄──┐
│ senha (TEXT bcrypt)     │   │
│ is_superuser (BOOL)     │   │
│ ativo (BOOL)            │   │
│ criado_em (TIMESTAMP)   │   │
└─────────────────────────┘   │
           ▲                    │
           │ 1:N (owns)        │
           │                   │
┌──────────┴──────────────┐    │
│     ALUNOS              │    │
├─────────────────────────┤    │
│ id (PK)                 │    │
│ nome (VARCHAR)          │    │
│ numero_inscricao (UNIQUE)   │
│ telefone (VARCHAR)      │    │
│ turma (VARCHAR)         │    │
│ foto (VARCHAR)          │    │
│ user_id (FK) ───────────┘    │
│ criado_em (TIMESTAMP)   │    │
└─────────┬───────────────┘    │
          │ 1:N (attends)      │
          │                    │
┌─────────▼──────────────────┐ │
│     PRESENCAS            │ │
├──────────────────────────┤ │
│ id (PK)                  │ │
│ aluno_id (FK) ───────────┤ │
│ timestamp (TIMESTAMP)    │ │
│ origem (VARCHAR)         │ │
│   - 'facial'             │ │
│   - 'manual'             │ │
│ confianca (FLOAT [0-1])  │ │
│ status (VARCHAR)         │ │
│   - 'confirmado'         │ │
│   - 'pendente'           │ │
└──────────────────────────┘ │
                             │
┌──────────────────────────┐ │
│  FACE_EMBEDDINGS         │ │
├──────────────────────────┤ │
│ id (PK)                  │ │
│ aluno_id (FK) ───────────┤ │
│ embedding (VECTOR(512))  │ │
│ criado_em (TIMESTAMP)    │ │
└──────────────────────────┘ │
           ▲                 │
           │                 │
        Índice:              │
    HNSW (pgvector)         │
    ❌ NÃO EXISTE           │
                            │
      ┌──────────────────────┤
      │                      │
┌─────▼──────────────────┐   │
│  RESPONSAVEIS          │   │
├────────────────────────┤   │
│ id (PK)                │   │
│ nome (VARCHAR)         │   │
│ telefone (VARCHAR)     │   │
│ email (VARCHAR)        │   │
└────────────────────────┘   │
           ▲                  │
           │ M:N (junction)   │
           │                  │
┌──────────┴───────────────┐  │
│ ALUNO_RESPONSAVEIS (J)  │  │
├────────────────────────┤  │
│ aluno_id (FK) ─────────┼──┘
│ responsavel_id (FK)    │
│ PK: (aluno_id, resp_id)│
└────────────────────────┘

┌────────────────────────────────┐
│  REFRESH_TOKENS                │
├────────────────────────────────┤
│ id (PK)                        │
│ token (VARCHAR UNIQUE)         │
│ user_id (FK → usuarios)        │
│ criado_em (TIMESTAMP)          │
│ expira_em (TIMESTAMP)          │
│ valido (BOOL)                  │
│ revogado (BOOL)                │
└────────────────────────────────┘

INDEXES NECESSÁRIOS:
┌────────────────────────────────────────┐
│ Atual:                                 │
│ ✅ usuarios (email)                    │
│ ✅ alunos (numero_inscricao)           │
│ ✅ alunos (user_id)                    │
│ ✅ presencas (aluno_id)                │
│ ✅ face_embeddings (aluno_id)          │
│                                        │
│ Faltando (CRÍTICO):                    │
│ ❌ presencas (timestamp DESC)          │
│ ❌ alunos (user_id, turma)             │
│ ❌ face_embeddings (HNSW vector)       │
│ ❌ refresh_tokens (user_id, valido)    │
└────────────────────────────────────────┘
```

---

## VIII. FLUXO DE NOTIFICAÇÕES

### Diagrama 8: Sistema de Notificações Async com Celery

```
┌──────────────────────────────────────┐
│  Presença Registrada Evento          │
│  ┌──────────────────────────────────┐│
│  │ aluno_id: 42                     ││
│  │ timestamp: 2026-04-18 10:30:15   ││
│  │ origem: facial                   ││
│  └──────────────────────────────────┘│
└──────────────────┬───────────────────┘
                   │ Trigger async task
                   ▼
        ┌──────────────────────────────┐
        │  Celery Task Queue           │
        │  ──────────────────────────  │
        │  (Redis backend)             │
        │                              │
        │  tasks/reconhecimento.py:    │
        │  @celery.task               │
        │  def notificar_responsavel() │
        └──────────┬───────────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │  Task Worker (Background)       │
        │  ────────────────────────────   │
        │  - Dequeue task from Redis      │
        │  - Get aluno details            │
        │  - Get responsavel contacts     │
        │  - Format message               │
        └──────────┬──────────────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │  Notification Service           │
        │  ────────────────────────────   │
        │  def send_notifications():      │
        │    - SMS via Twilio             │
        │    - Email via SendGrid         │
        │    - Push via FCM (future)      │
        └──────────┬──────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌─────────┐   ┌────────┐   ┌──────────┐
│  SMS    │   │ Email  │   │  Push    │
│ Twilio  │   │SendGrid│   │  (TODO)  │
└──────┬──┘   └───┬────┘   └──────────┘
       │          │
       ▼          ▼
   📱          📧
   
Message:
"Mateus registrou presença 
 às 10:30. Turma M1."

Result:
✅ Delivered / ❌ Failed
   (Logged & Retried)
```

---

## IX. ESCALABILIDADE VERTICAL vs HORIZONTAL

### Diagrama 9: Strategies de Scaling

```
VERTICAL SCALING (Single Instance)
┌────────────────────────────────────┐
│  Computador Maior                  │
│                                    │
│  RAM: 8GB → 16GB → 32GB → 64GB     │
│  CPU: 2 cores → 4 → 8 → 16         │
│  Disk: 100GB → 500GB → 1TB         │
│                                    │
│  Limitações:                       │
│  ❌ Custo exponencial              │
│  ❌ Sem redundância (downtime)     │
│  ❌ Single point of failure        │
│  ❌ Max ~10k concurrent users      │
└────────────────────────────────────┘
                │
                │ TETO DE ESCALABILIDADE
                ▼
          (Diminishing returns)

HORIZONTAL SCALING (Multiple Instances)
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  Instance 1    │  │  Instance 2    │  │  Instance 3    │
│  ┌──────────┐  │  │  ┌──────────┐  │  │  ┌──────────┐  │
│  │ FastAPI  │  │  │  │ FastAPI  │  │  │  │ FastAPI  │  │
│  │ 4 workers│  │  │  │ 4 workers│  │  │  │ 4 workers│  │
│  │ 2GB RAM  │  │  │  │ 2GB RAM  │  │  │  │ 2GB RAM  │  │
│  │ 2 CPUs   │  │  │  │ 2 CPUs   │  │  │  │ 2 CPUs   │  │
│  └──────────┘  │  │  └──────────┘  │  │  └──────────┘  │
└────────────────┘  └────────────────┘  └────────────────┘
         ▲                 ▲                      ▲
         │                 │                      │
         └─────────────────┼──────────────────────┘
                    ┌──────▼──────┐
                    │Load Balancer│
                    │   (nginx)   │
                    └─────────────┘
                          │
                    Vantagens:
                    ✅ Linear scaling
                    ✅ High availability
                    ✅ Easy to add/remove
                    ✅ Suporta 100k+ users
```

---

## X. MONITORAMENTO & OBSERVABILIDADE

### Diagrama 10: Monitoring Stack

```
┌──────────────────────────────────────────────────────┐
│  APPLICATION (FastAPI)                               │
│  ├─ Metrics: Request count, latency, errors          │
│  ├─ Logs: JSON formatted, structured                 │
│  ├─ Traces: Distributed tracing (Jaeger)            │
│  └─ Health: /health endpoint                         │
└──────────┬───────────────────────────────────────────┘
           │
    ┌──────┴──────┐─────────┬────────────┐
    ▼             ▼         ▼            ▼
┌────────┐  ┌─────────┐ ┌─────────┐ ┌──────────┐
│Metrics │  │  Logs   │ │ Traces  │ │Profiling │
│Prometheus│ │ Loki   │ │ Jaeger  │ │ pyprof  │
└────┬───┘  └────┬────┘ └────┬────┘ └────┬─────┘
     │           │          │           │
     └───────────┼──────────┼───────────┘
                 ▼
        ┌──────────────────────┐
        │  AGGREGATION LAYER   │
        │  (DataDog / NewRelic)│
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │  VISUALIZATION       │
        │  (Dashboards)        │
        │                      │
        │  - Request rate      │
        │  - P50/P95/P99 lat   │
        │  - Error rate        │
        │  - DB connections    │
        │  - Cache hit rate    │
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │  ALERTING            │
        │  (PagerDuty)         │
        │                      │
        │  - P99 > 1000ms      │
        │  - Error rate > 1%   │
        │  - Downtime          │
        │  - DB lag            │
        └──────────────────────┘
```

---

## XI. DISASTER RECOVERY PLAN

### Diagrama 11: Backup & Recovery Strategy

```
┌────────────────────────────────────────────────────┐
│  DATABASE (PostgreSQL)                             │
│  ┌──────────────────────────────────────────────┐ │
│  │ Live data                                    │ │
│  │ (500GB)                                      │ │
│  └──────────────────────────────────────────────┘ │
└──────────────┬─────────────────────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
    
DAILY SNAPSHOT (Automated)
- Time: 02:00 AM UTC (off-peak)
- Duration: 30 min
- Size: 150GB (compressed)
- Retention: 30 days
- Destination: AWS S3
- Versioning: Enabled
- Encryption: AES-256

    ├─ Day 1: Full backup
    ├─ Day 2: Incremental
    ├─ Day 3: Incremental
    │ ...
    └─ Day 30: Delete oldest

POINT-IN-TIME RECOVERY (PITR)
- WAL (Write-Ahead Log) archival
- Every transaction logged
- Recovery granularity: 1 second
- Retention: 14 days
- Cost: ~$100/month

TESTING (Quarterly)
- Restore to staging
- Verify data integrity
- Measure recovery time
- Document procedures

METRICS:
- RPO (Recovery Point Objective): < 1 hour
- RTO (Recovery Time Objective): < 2 hours
- Backup success rate: > 99.9%
```

---

## XII. ROADMAP DE CRESCIMENTO

### Diagrama 12: Feature Roadmap 12 Meses

```
MESES      1-2           3-4          5-8           9-12
FASE      STABILIZE     OPTIMIZE     SCALE        MONETIZE

Core      ┌─────────┐   ┌────────┐   ┌──────────┐  ┌─────────┐
Fixes     │ Pagiação│   │ Cache  │   │Multi-Ten │  │ White  │
          │ Rate-L. │   │ WebSock│   │ LDAP/SSO │  │ Label  │
          │ Backup  │   │ Analytics│ │ Analytics│  │ Mobile │
          └─────────┘   └────────┘   └──────────┘  └─────────┘
                │             │             │           │
Users       10-25        50-100        200-500      1000+
Features    ████░░░░░░  ██████░░░░    ████████░░   ██████████
Quality     ███░░░░░░░  ████████░░    ██████████   ██████████
Scale       ██░░░░░░░░  ████░░░░░░    ███████░░░   ██████████

CRITICAL PATH (Do-or-Die):
M1: ✅ Paginação + Rate Limiting
M1: ✅ Backup automático
M2: Redis cache (80% query cache)
M3: WebSockets (real-time notifications)
M4: Analytics dashboard
M5: Multi-tenant support
M6: White-label capability
M12: Mobile app
```

---

## RESUMO VISUAL

```
┌─────────────────────────────────────┐
│  SISTEMA ESCOLAR v2.0               │
│  ────────────────────────────────   │
│  Status: MVP ✅ Funcional           │
│  Escalabilidade: 🟡 Precisa work    │
│  Segurança: 🟡 70% implementada     │
│  Testes: 🟢 60% cobertura           │
│  Produção: 🔴 NÃO PRONTO (yet)      │
└─────────────────────────────────────┘

Next: Implementar críticos em 30 dias!
```

---

*Diagramas de Arquitetura | Sistema Escolar v2.0 | 18/04/2026*
