# Staging Environment

**Last Updated:** 2026-03-29

This document describes how to set up and operate an isolated staging environment for Echelon that mirrors production while protecting live data and API quotas.

---

## Overview

The staging environment uses the same Docker Compose stack as production but with a separate configuration file, isolated database, and reduced ingestion cadence. Its purpose is to validate migrations, test new features, and perform smoke tests before promoting changes to production.

---

## Configuration

### 1. Create a Staging Environment File

Copy `.env.example` to `.env.staging` and configure it with staging-specific values:

```bash
cp .env.example .env.staging
```

Key differences from production `.env`:

| Variable | Production | Staging |
|----------|-----------|---------|
| `POSTGRES_PASSWORD` | Strong unique password | Different strong unique password |
| `SECRET_KEY` | Production secret | Different secret |
| `GITHUB_CLIENT_ID` | Production OAuth app | Separate OAuth app with staging callback URL |
| `GITHUB_CLIENT_SECRET` | Production secret | Staging OAuth app secret |
| `GFW_API_TOKEN` | Production key | Same key (or separate if quota is a concern) |
| `NEWSDATA_API_KEY` | Production key | Same key (monitor credit usage) |
| `GDELT_INGEST_INTERVAL_MINUTES` | `60` | `360` (reduced cadence) |
| `CONVERGENCE_ALERT_THRESHOLD` | `2.0` | `2.0` (keep consistent for testing) |
| `RESEND_API_KEY` | Production key | Omit or use test key (prevent real email sends) |
| `RESEND_FROM_EMAIL` | Production domain | `staging@yourdomain.com` or omit |

**Never reuse the production `POSTGRES_PASSWORD`, `SECRET_KEY`, or `BYOK_ENCRYPTION_KEY` in staging.**

### 2. Use docker-compose.override.yml

The `docker-compose.override.yml` file applies automatically when running `docker compose up`. For staging, create a dedicated override:

```bash
cp docker-compose.override.yml docker-compose.staging.yml
```

Key overrides for staging:

```yaml
services:
  api:
    env_file: .env.staging
    ports:
      - "8080:8000"  # Different port to avoid conflicts if running alongside prod

  worker:
    env_file: .env.staging
    command: celery -A app.workers.celery_app worker --loglevel=info --concurrency=1

  beat:
    env_file: .env.staging
    command: celery -A app.workers.celery_app beat --loglevel=info --schedule=/tmp/celerybeat-schedule

  db:
    container_name: echelon_db_staging
    environment:
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=echelon_staging
    volumes:
      - postgres_staging_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"  # Expose on different port for direct inspection

  redis:
    container_name: echelon_redis_staging
    volumes:
      - redis_staging_data:/data
    ports:
      - "6380:6379"

  nginx:
    ports:
      - "8081:80"  # Different external port

volumes:
  postgres_staging_data:
  redis_staging_data:
```

Run the staging stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml --env-file .env.staging up -d
```

### 3. Isolated Database

The staging database uses a separate volume (`postgres_staging_data`) and database name (`echelon_staging`). This guarantees:

- Migrations can be tested without risking production data
- Staging can be torn down and rebuilt without affecting production
- Schema drift between staging and production is detectable

To reset the staging database completely:

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml down -v
```

This removes the staging volumes. Production volumes are unaffected because they use different named volumes.

---

## Reduced Ingestion Cadence

Staging should not consume API quotas at production rates. Recommended schedule adjustments:

| Task | Production | Staging |
|------|-----------|---------|
| `ingest_gdelt` | Every 15 min | Every 6 hours |
| `ingest_gfw_events` | Every 12 hours | Every 24 hours |
| `ingest_newsdata` | Every 4 hours | Every 12 hours |
| `ingest_osm_changes` | Every 24 hours | Every 48 hours |
| `ingest_opensky` | Every 30 min | Every 6 hours |
| `ingest_osint_scrape` | Every 2 hours | Every 12 hours |
| `ingest_aisstream` | Every 30 min | Every 6 hours |
| `ingest_firms` | Every 6 hours | Every 24 hours |
| `trigger_sentinel2_jobs` | Every 24 hours | Manual only |
| `recompute_convergence` | Every 15 min | Every 1 hour |
| `check_aoi_alerts` | Every 15 min | Every 1 hour |

To adjust cadence, modify `backend/app/workers/beat_schedule.py` on the staging branch or use environment variables if the schedule supports them. Set `GDELT_INGEST_INTERVAL_MINUTES=360` in `.env.staging`.

---

## Testing Migrations Safely

### Before Running a Migration

1. Ensure the staging database is running and accessible:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.staging.yml exec db psql -U echelon -d echelon_staging -c "SELECT 1;"
   ```

2. Check the current migration state:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.staging.yml exec api alembic current
   ```

3. Review the migration script before applying:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.staging.yml exec api alembic upgrade head --sql
   ```
   This prints the SQL that would be executed without actually running it.

### Running the Migration

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml exec api alembic upgrade head
```

### Verifying the Migration

1. Check that the migration completed:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.staging.yml exec api alembic current
   ```

2. Verify the schema matches expectations:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.staging.yml exec db psql -U echelon -d echelon_staging -c "\dt"
   ```

3. Run a quick API health check (see smoke test below).

### Rolling Back

If a migration fails or produces unexpected results:

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml exec api alembic downgrade -1
```

If the migration is not reversible, reset the staging database from scratch and re-run all migrations from the baseline.

---

## Smoke Testing Before Production Promotion

Run the following checks on staging before deploying to production:

### 1. Health Check

```bash
curl http://localhost:8081/api/health
```

Expected response: `200 OK` with database and Redis connectivity confirmed.

### 2. Convergence Endpoint

```bash
curl "http://localhost:8081/api/convergence?resolution=5&bbox=-180,-90,180,90"
```

Verify: Returns a JSON array of H3 convergence scores (may be empty if ingestion has not run yet).

### 3. Signals Endpoint

```bash
curl "http://localhost:8081/api/signals?source=gdelt&limit=5"
```

Verify: Returns signal records if GDELT ingestion has run at least once.

### 4. Authentication Flow

1. Navigate to `http://localhost:8081` in a browser
2. Click "Sign In with GitHub" (requires the staging OAuth app to be configured)
3. Verify redirect to GitHub and successful callback
4. Verify session cookie is set and `/api/auth/me` returns user profile

### 5. Celery Worker Health

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml exec worker celery -A app.workers.celery_app inspect ping
```

Verify: Worker responds to ping.

### 6. Flower Dashboard

Navigate to `http://localhost:8081/flower/` and verify task history is visible.

### 7. Copilot (if BYOK key is available)

Send a test query through the copilot interface and verify that tool calls execute and return data from the staging database.

---

## Promoting to Production

Once all smoke tests pass on staging:

1. Tag the release commit (see `docs/release-process.md`)
2. Deploy the same Docker image to production
3. Run `alembic upgrade head` on the production database
4. Monitor the health endpoint and Flower dashboard for 15 minutes after deployment
5. Verify at least one convergence recomputation cycle completes successfully
