# DL-005: Cloudflare Pages (Frontend) + DigitalOcean (Backend) Deployment

**Date:** 2025-03-25 (revised 2026-04-01)
**Status:** Accepted (supersedes Railway + Render)
**Author:** Chris Lyons

## Context

Echelon has a 9-container Docker Compose stack. The original plan used Railway (backend) + Render (frontend), but the project moved to Cloudflare Pages + DigitalOcean for simpler ops and lower cost.

## Decision

- **Backend stack** (nginx, FastAPI, Celery worker, beat, flower, PostGIS, Redis, Ollama): Single DigitalOcean Droplet running Docker Compose.
- **Frontend** (Vite static build): Cloudflare Pages — auto-deploys from GitHub on push to `main`.

## Alternatives Considered

- **Railway + Render** — Previously used; migrated away due to Railway pricing and operational complexity of splitting services across two platforms.
- **Single VPS for everything** — Rejected: frontend benefits from Cloudflare's CDN and edge caching.

## Consequences

- DigitalOcean Droplet requires manual ops (SSH, `docker compose up`, Alembic migrations).
- Cloudflare terminates TLS upstream; HSTS enforcement via nginx `Strict-Transport-Security` header.
- Docker named volumes for PostGIS data and Redis AOF persistence.
- Flower is internal only — accessible behind nginx basic auth.
