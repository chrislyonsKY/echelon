# Maintainer Runbook

## Purpose

This is the quick operational reference for routine Echelon maintenance, especially for Docker deployments on a VPS such as a DigitalOcean droplet.

## Common Tasks

### Pull and Deploy Latest Code

```bash
git pull
docker compose up -d --build --force-recreate
docker compose exec api alembic upgrade head
```

Then verify:

- app loads
- auth still works
- `/api/health`
- worker and beat containers are healthy

### Check Container Status

```bash
docker compose ps
docker compose logs api --tail=100
docker compose logs worker --tail=100
docker compose logs beat --tail=100
```

### Restart a Service

```bash
docker compose restart api
docker compose restart worker
docker compose restart beat
```

## Operational Checks

After deployments or source changes, verify:

- login and session behavior
- source-health timestamps update
- worker tasks are executing
- map overlays still load
- imagery search still works
- export routes still behave

## Secret Rotation

If rotating secrets:

1. update `.env`
2. rebuild or restart affected containers
3. invalidate sessions if session material may have been exposed
4. verify third-party integrations recover cleanly

High-priority secrets:

- `SECRET_KEY`
- `BYOK_ENCRYPTION_KEY`
- GitHub OAuth secret
- provider API tokens
- database credentials

## Incident Basics

If something looks compromised:

- contain first
- rotate secrets if exposure is plausible
- restrict public access to internal services
- preserve only the logs you need
- use [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md)

## Safe Defaults to Recheck

On the droplet, confirm periodically:

- Redis is not public
- Postgres is not public
- Flower is not public
- reverse proxy is terminating TLS correctly
- `.env` is not world-readable
- backups exist and can be restored

## Before Merging Source Additions

Check that the PR updated:

- [SOURCE_INTAKE_CHECKLIST.md](SOURCE_INTAKE_CHECKLIST.md)
- [ATTRIBUTION.md](ATTRIBUTION.md) if needed
- [DATA_PROVENANCE.md](DATA_PROVENANCE.md) if needed
- health telemetry if the source is operational

## Minimum Local Validation

```bash
python3 -m compileall backend/app
cd frontend && npm run type-check
cd frontend && npm run lint
```
