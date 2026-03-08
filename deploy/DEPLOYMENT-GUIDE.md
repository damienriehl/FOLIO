# FOLIO Ecosystem — Railway Deployment Guide

This guide covers deploying the FOLIO ecosystem services on [Railway](https://railway.app).

## Why Railway?

- **Git-push deploys**: Connect a GitHub repo → automatic builds and deploys
- **Native Docker support**: Detects Dockerfiles automatically
- **Managed databases**: One-click PostgreSQL and Redis add-ons
- **Private networking**: Services in the same project communicate over internal network
- **Usage-based pricing**: Pay for CPU/RAM consumed; idle services cost very little
- **Sleep on idle**: Demo/staging services can sleep when unused

## Cost Estimate

| Scenario | Estimated Monthly Cost |
|----------|----------------------|
| 2-3 light services (sleep on idle) | $5–15 |
| 5-10 services (mix of always-on and sleeping) | $20–50 |
| Full OntoKit stack (API + worker + web + Postgres + Redis) | $25–45 |
| Everything combined | $40–80 |

Railway's Hobby plan is $5/mo and includes $5 of usage credit. The Pro plan ($20/mo) removes sleep limits and adds team features.

---

## Architecture Overview

```
Railway Project: "OntoKit"
├── ontokit-api        (FastAPI, Dockerfile.prod, port 8000)
├── ontokit-worker     (arq worker, same repo, no port)
├── ontokit-web        (Next.js, Dockerfile, port 3000)
├── PostgreSQL         (managed plugin)
├── Redis              (managed plugin)
└── Zitadel            (Docker image or Zitadel Cloud)

Railway Project: "FOLIO Tools"
├── folio-enrich       (FastAPI, Dockerfile, port 8000)
├── folio-mapper-api   (FastAPI, Nixpacks, port 8000)
└── folio-mapper-web   (Vite/React static, port 3000)

Railway Project: "Other Services"
├── caritas-ai, homilia-ai, etc.
```

External services:
- **Cloudflare R2** — S3-compatible object storage (replaces MinIO, 10 GB free)
- **Zitadel Cloud** — Managed OIDC provider (free tier available, or self-host on Railway)

---

## Setup Instructions

### Prerequisites

1. [Railway account](https://railway.app) (GitHub login recommended)
2. [Railway CLI](https://docs.railway.app/guides/cli) (optional but helpful):
   ```bash
   npm install -g @railway/cli
   railway login
   ```
3. [Cloudflare account](https://dash.cloudflare.com) for R2 storage (if deploying OntoKit)

### Step 1: Deploy folio-enrich (simplest service)

This is a good starting point — single FastAPI service, no databases.

1. In the Railway dashboard, click **New Project → Deploy from GitHub repo**
2. Select `alea-institute/folio-enrich`
3. Railway will detect `backend/Dockerfile` automatically
4. Copy the `railway.toml` from `deploy/folio-enrich/railway.toml` into the repo root
5. Set environment variables (see `deploy/folio-enrich/env.example`):
   - `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`
6. Deploy. Railway will build and serve on a `*.up.railway.app` domain.

### Step 2: Deploy folio-mapper (monorepo: backend + frontend)

This requires two Railway services from the same repo.

**Backend service:**
1. In your Railway project, click **New Service → GitHub Repo → alea-institute/folio-mapper**
2. Copy `deploy/folio-mapper/railway.toml` to the repo root as `railway.toml`
3. Set env vars from `deploy/folio-mapper/env.example`

**Frontend service:**
1. Add another service from the same repo
2. Set the **Root Directory** to `/` (repo root)
3. Use the build/start commands from `deploy/folio-mapper/railway-web.toml`
4. Set `VITE_API_URL` to the backend's Railway URL

### Step 3: Deploy OntoKit (full stack)

This is the most complex deployment — 5+ services.

#### 3a. Create the Railway project

1. **New Project** → name it "OntoKit"

#### 3b. Add managed services

1. **+ New Service → Database → PostgreSQL** (one-click)
2. **+ New Service → Database → Redis** (one-click)

Railway will auto-create `DATABASE_URL` and `REDIS_URL` variables.

#### 3c. Set up Cloudflare R2 (replaces MinIO)

1. In Cloudflare dashboard → R2 → **Create Bucket** → name it `ontokit-files`
2. Create an **API Token** with read/write access to the bucket
3. Note: endpoint URL is `https://<account-id>.r2.cloudflarestorage.com`

#### 3d. Deploy ontokit-api

1. **+ New Service → GitHub Repo → CatholicOS/ontokit-api**
2. Copy `deploy/ontokit-api/railway.toml` to the repo root
3. Set env vars from `deploy/ontokit-api/env.example`:
   - `DATABASE_URL` → use Railway variable reference: `${{Postgres.DATABASE_URL}}`
   - `REDIS_URL` → use Railway variable reference: `${{Redis.REDIS_URL}}`
   - R2 credentials from step 3c
   - Zitadel credentials (see 3f)
4. **Add a volume**: mount path `/data/repos` for git repository storage
5. Run database migrations: use Railway CLI:
   ```bash
   railway run alembic upgrade head
   ```

#### 3e. Deploy ontokit-worker

1. **+ New Service → GitHub Repo → CatholicOS/ontokit-api** (same repo)
2. Name it "ontokit-worker"
3. Set **Start Command** to: `python -m arq ontokit.worker.WorkerSettings`
4. Copy the same env vars as ontokit-api
5. No port or health check needed (it's a background worker)

#### 3f. Deploy ontokit-web

1. **+ New Service → GitHub Repo → CatholicOS/ontokit-web**
2. Copy `deploy/ontokit-web/railway.toml` to the repo root
3. Set env vars from `deploy/ontokit-web/env.example`
4. Set build args for the API URL (Railway will substitute at build time)

#### 3g. Authentication (Zitadel)

**Option A: Zitadel Cloud (recommended for simplicity)**
- Sign up at [zitadel.cloud](https://zitadel.cloud) (free tier available)
- Create a project and OIDC application
- Use the issuer URL and client credentials in both ontokit-api and ontokit-web

**Option B: Self-host on Railway**
- Add a service using the Docker image `ghcr.io/zitadel/zitadel:latest`
- Requires its own PostgreSQL database (can share the existing one with a separate schema)
- More complex; recommended only if you need full control

---

## Deploying Additional Services

For any Python/FastAPI service, the pattern is:

1. Add a `railway.toml` to the repo:
   ```toml
   [build]
   dockerfilePath = "Dockerfile"  # or builder = "nixpacks"

   [deploy]
   healthcheckPath = "/health"
   startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"

   [service]
   internalPort = 8000
   ```

2. Connect the GitHub repo in Railway
3. Set environment variables
4. Deploy

For Next.js / static frontends:
```toml
[build]
builder = "nixpacks"

[deploy]
healthcheckPath = "/"

[service]
internalPort = 3000
```

---

## Tips

### Private networking
Services in the same Railway project can communicate using internal hostnames:
```
http://ontokit-api.railway.internal:8000
```
This avoids public internet round-trips and is free (no egress charges).

### Custom domains
Railway provides `*.up.railway.app` domains by default. To add a custom domain:
1. Go to service settings → **Networking → Custom Domain**
2. Add a CNAME record in your DNS pointing to Railway

### Environment variable references
Railway supports variable references across services:
```
DATABASE_URL=${{Postgres.DATABASE_URL}}
API_URL=https://${{ontokit-api.RAILWAY_PUBLIC_DOMAIN}}
```

### Sleep on idle (Hobby plan)
Hobby plan services sleep after 10 minutes of no inbound traffic. This is ideal for demo/staging services. Pro plan services stay always-on.

### Monitoring
Railway provides built-in logs, metrics (CPU/RAM/network), and deployment history. No external monitoring needed for demo/staging.

---

## Cloudflare R2 Setup (replacing MinIO)

Cloudflare R2 is S3-compatible and works as a drop-in replacement for MinIO:

| MinIO Config | R2 Equivalent |
|---|---|
| `MINIO_ENDPOINT` | `https://<account-id>.r2.cloudflarestorage.com` |
| `MINIO_ACCESS_KEY` | R2 API Token access key |
| `MINIO_SECRET_KEY` | R2 API Token secret key |
| `MINIO_BUCKET` | R2 bucket name |
| `MINIO_REGION` | `auto` |

The ontokit-api code uses the `minio` Python client, which is S3-compatible and works with R2 with no code changes — just point the endpoint URL to R2.

**R2 Free Tier**: 10 GB storage, 10 million reads/mo, 1 million writes/mo, zero egress fees.

---

## Migration Checklist

- [ ] Sign up for Railway (Hobby plan, $5/mo)
- [ ] Sign up for Cloudflare (free, for R2 storage)
- [ ] Deploy folio-enrich (test the workflow)
- [ ] Deploy folio-mapper (backend + frontend)
- [ ] Set up Zitadel Cloud (free tier)
- [ ] Create R2 bucket for OntoKit
- [ ] Deploy OntoKit stack (API + worker + web + Postgres + Redis)
- [ ] Set up custom domains (optional)
- [ ] Configure DNS records (optional)
