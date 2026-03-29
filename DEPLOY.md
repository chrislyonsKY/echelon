# Railway Deployment Guide

## Service Configuration

Each Docker Compose service deploys as a separate Railway service within one project.
All services share Railway's internal private network.

### Service: api
- Build: `./backend/Dockerfile`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`
- Health check: `GET /api/docs` → 200
- Environment: set all vars from `.env.example` in Railway dashboard

### Service: worker
- Build: `./backend/Dockerfile`
- Start command: `celery -A app.workers.celery_app worker --loglevel=info --concurrency=2`

### Service: beat
- Build: `./backend/Dockerfile`
- Start command: `celery -A app.workers.celery_app beat --loglevel=info --schedule=/tmp/celerybeat-schedule`

### Service: flower
- Build: `./backend/Dockerfile`
- Start command: `celery -A app.workers.celery_app flower --port=5555 --url-prefix=flower`
- Internal only — do not expose publicly

### Service: db
- Image: `postgis/postgis:16-3.4-alpine`
- Volume: Railway persistent volume → `/var/lib/postgresql/data`
- Environment: `POSTGRES_USER=echelon`, `POSTGRES_PASSWORD=<from env>`, `POSTGRES_DB=echelon`

### Service: redis
- Image: `redis:7.2-alpine`
- Start command: `redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru --appendonly yes`
- Volume: Railway persistent volume → `/data`

## First Deployment Checklist

1. Create Railway project, add all 6 services
2. Set all environment variables in Railway dashboard (from .env.example)
3. Deploy db and redis first — wait for healthy
4. Deploy api — run Alembic migrations:
   ```
   railway run python -m alembic upgrade head
   ```
5. Deploy worker, beat, flower
6. Deploy frontend to Render as static site (build command: `npm run build`, publish: `dist/`)

## Environment Variables (Railway)

Set these in the Railway dashboard for each service that needs them.
All backend services (api, worker, beat, flower) need the full set.
db and redis only need their own credentials.

See `.env.example` for the full list with descriptions.

DATABASE_URL is constructed by Railway automatically if using Railway PostgreSQL.
Override format: `postgresql+asyncpg://echelon:<password>@<internal-host>:5432/echelon`
