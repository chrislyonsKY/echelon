# DL-005: Railway (Backend) + Render (Frontend) Deployment Split

**Date:** 2025-03-25
**Status:** Accepted
**Author:** Chris Lyons

## Context

Echelon has an 8-container Docker Compose stack. Render.com supports Docker but not multi-service Compose natively. Railway natively supports multi-service projects with private networking and usage-based pricing.

## Decision

- **Backend stack** (FastAPI, Celery worker, beat, flower, PostGIS, Redis): Railway — each container as a separate Railway service within one project, sharing a private Railway network.
- **Frontend** (Vite static build): Render static site — free tier, CDN delivery, auto-deploys from GitHub.

## Alternatives Considered

- **Single Render service** — Rejected: Render can't run multi-container Compose natively.
- **VPS (DigitalOcean/Hetzner)** — Valid alternative: full Docker Compose control, but requires more ops work (SSL, updates, monitoring). Suitable if Railway costs grow.
- **Full Railway** — Frontend as Railway service: unnecessary, Render static site is free and better for CDN delivery.

## Consequences

- Railway usage-based pricing; estimated $20–35/month at steady state.
- PostGIS and Redis need Railway persistent volume mounts — configure before first deploy.
- The `frontend_dist` shared Docker volume used in local dev is replaced by Render static build in production.
- Flower is internal only — accessible behind Nginx basic auth, not exposed to public internet on Railway.
