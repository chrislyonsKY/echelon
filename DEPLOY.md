# Deployment Guide

> **Frontend:** Cloudflare Pages  
> **Backend:** DigitalOcean Droplet (Docker Compose)

---

## Frontend — Cloudflare Pages

The frontend is a static Vite/React build deployed to Cloudflare Pages.

| Setting | Value |
|---------|-------|
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | `frontend` |
| Node version | 20 |

Cloudflare Pages auto-deploys on push to `main`. SPA routing is handled by Cloudflare's automatic `/* → /index.html` rewrite.

Set the `VITE_API_BASE_URL` environment variable in the Cloudflare Pages dashboard to point at your DigitalOcean backend (e.g. `https://api.echelon-geoint.org`).

---

## Backend — DigitalOcean (Docker Compose)

The entire backend stack runs as a single Docker Compose deployment on a DigitalOcean Droplet.

### Services

| Service | Image / Build | Exposed Port | Health Check |
|---------|--------------|-------------|-------------|
| nginx | `nginx:1.27-alpine` | 80 | — |
| api | `backend/Dockerfile` | 8000 (internal) | `/api/health/live` |
| worker | `backend/Dockerfile` | — | — |
| beat | `backend/Dockerfile` | — | — |
| flower | `backend/Dockerfile` | 5555 (internal) | — |
| db | `postgis/postgis:16-3.4-alpine` | 5432 (internal) | `pg_isready` |
| redis | `redis:7.2-alpine` | 6379 (internal) | `redis-cli ping` |
| ollama | `ollama/ollama:latest` | 11434 (internal) | — |

### First Deployment

```bash
# 1. SSH into your Droplet
ssh root@<droplet-ip>

# 2. Clone the repo
git clone https://github.com/chrislyonsKY/echelon.git
cd echelon

# 3. Create .env from example and fill in all values
cp .env.example .env
nano .env   # set SECRET_KEY (≥32 chars), POSTGRES_PASSWORD, REDIS_PASSWORD, API keys, etc.

# 4. Start the stack (db + redis come up first via depends_on healthchecks)
docker compose up -d

# 5. Run database migrations
docker compose exec api python -m alembic upgrade head

# 6. Verify
docker compose ps
curl -s http://localhost/api/health/ready | jq .
```

### Redeployment (after push to main)

```bash
ssh root@<droplet-ip>
cd echelon
git pull origin main
docker compose build --no-cache api
docker compose up -d
docker compose exec api python -m alembic upgrade head
```

### Rollback

```bash
# Revert to previous image
docker compose up -d --no-build   # uses cached images

# Or revert to a specific commit
git checkout <previous-sha>
docker compose build api
docker compose up -d
docker compose exec api python -m alembic downgrade -1
```

---

## Environment Variables

All backend services share the same `.env` file. See `.env.example` for the full list.

**Required:**
- `SECRET_KEY` — session signing key (≥ 32 characters)
- `POSTGRES_PASSWORD` — PostgreSQL password
- `REDIS_PASSWORD` — Redis auth password
- `DATABASE_URL` — `postgresql+asyncpg://echelon:<password>@db:5432/echelon`
- `REDIS_URL` — `redis://:<password>@redis:6379/0`
- `CELERY_BROKER_URL` — `redis://:<password>@redis:6379/1`

**Optional (features disabled if unset):**
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` — GitHub OAuth
- `GFW_API_TOKEN` — Global Fishing Watch ingestion
- `NEWSDATA_API_KEY` — NewsData.io ingestion
- `FIRMS_MAP_KEY` — NASA FIRMS thermal anomalies
- `AISSTREAM_API_KEY` — AIS vessel tracking
- `RESEND_API_KEY` / `RESEND_FROM_EMAIL` — email alerts
- `BYOK_ENCRYPTION_KEY` — server-side BYOK key storage

---

## DNS (Cloudflare)

| Record | Name | Value |
|--------|------|-------|
| A | `api.echelon-geoint.org` | `<droplet-ip>` (proxied) |
| CNAME | `echelon-geoint.org` | Cloudflare Pages URL (auto) |

Cloudflare handles TLS termination for both frontend and the API proxy.
