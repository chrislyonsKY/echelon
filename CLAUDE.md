# CLAUDE.md — Echelon
> Open-source GEOINT conflict and maritime activity monitoring dashboard
> Stack: Python 3.12 / FastAPI / PostgreSQL+PostGIS / Redis / Celery | TypeScript / React / Vite / MapLibre GL JS / Deck.gl

> **Note:** Do not include this file as indexable context. It is the entry point, not a reference doc.

Read this file completely before doing anything.
Then read `ai-dev/architecture.md` for full system context.
Then read `ai-dev/guardrails/` for hard constraints — these override all other instructions.


---

## Context Boundaries

This file is the AI entry point for this project.
Do NOT auto-scan or index the following:
- `ai-dev/`   (read specific files only when instructed)
- `CLAUDE.md` (this file — entry point only)

When a task requires architecture context: read `ai-dev/architecture.md` explicitly.
When a task requires data model context: read `ai-dev/field-schema.md` explicitly.
When a task requires constraints: read `ai-dev/guardrails/` explicitly.
When a task requires domain patterns: read `ai-dev/skills/geoint-data-skill.md` explicitly.

---

## Workflow Protocol

Before writing any code:
1. Read this file (CLAUDE.md)
2. Read `ai-dev/architecture.md`
3. Read `ai-dev/guardrails/` — constraints are non-negotiable
4. Read the relevant `ai-dev/agents/` file for your role
5. Check `ai-dev/decisions/` for prior decisions affecting your work
6. Check `ai-dev/skills/` for domain patterns specific to this project

**Plan first. Show the plan. Wait for confirmation before writing code.**

---

## Compatibility Matrix

| Component | Version |
|-----------|---------|
| Python | 3.12+ |
| FastAPI | 0.115+ |
| SQLAlchemy | 2.0+ (async) |
| Alembic | 1.13+ |
| Celery | 5.4+ |
| PostGIS | 3.4+ |
| PostgreSQL | 16+ |
| Redis | 7.2+ |
| Node.js | 20 LTS |
| React | 18+ |
| TypeScript | 5.4+ |
| MapLibre GL JS | 4.x |
| Deck.gl | 9.x |
| H3 (Python) | 3.7+ |

---

## Project Structure

```
echelon/
├── AGENTS.md                        # ← You are here
├── docker-compose.yml               # 8-service orchestration
├── docker-compose.override.yml      # Dev overrides (hot reload, ports)
├── .env.example                     # All required env vars documented
├── nginx/nginx.conf                 # Reverse proxy config
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/versions/            # DB migrations
│   └── app/
│       ├── main.py                  # FastAPI app factory
│       ├── config.py                # Settings via pydantic-settings
│       ├── database.py              # Async SQLAlchemy engine + session
│       ├── auth/                    # GitHub OAuth + session management
│       ├── routers/                 # API route handlers
│       │   ├── convergence.py       # H3 heatmap + Z-score endpoints
│       │   ├── signals.py           # Per-layer signal query endpoints
│       │   ├── copilot.py           # BYOK Anthropic copilot proxy
│       │   ├── alerts.py            # AOI alert management
│       │   └── auth.py              # OAuth callback + session
│       ├── services/                # External API clients
│       │   ├── acled.py             # ACLED REST API client
│       │   ├── gfw.py               # GlobalFishingWatch API client
│       │   ├── stac.py              # Element84 Earth Search STAC client
│       │   ├── overpass.py          # OSM Overpass API client
│       │   ├── newsdata.py          # NewsData.io API client
│       │   ├── gdelt.py             # GDELT bulk ingest client
│       │   └── convergence_scorer.py # Z-score computation engine
│       ├── models/                  # SQLAlchemy ORM models
│       └── workers/
│           ├── celery_app.py        # Celery + Redis broker config
│           ├── beat_schedule.py     # Periodic task schedule
│           └── tasks/               # Celery task modules
├── frontend/
│   ├── Dockerfile
│   ├── vite.config.ts
│   └── src/
│       ├── components/
│       │   ├── map/                 # MapLibre + Deck.gl map components
│       │   ├── sidebar/             # Tabbed investigation sidebar
│       │   ├── copilot/             # BYOK copilot chat panel
│       │   └── alerts/              # Notification bell + alert list
│       ├── hooks/                   # Data fetching + copilot hooks
│       ├── store/                   # Zustand global state
│       └── services/                # Typed API client (fetch wrapper)
└── ai-dev/                          # AI development infrastructure
    ├── architecture.md
    ├── spec.md
    ├── field-schema.md
    ├── patterns.md
    ├── prompt-templates.md
    ├── agents/
    ├── decisions/
    ├── skills/
    └── guardrails/
```

---

## Critical Conventions

### Backend
- All database access uses **async SQLAlchemy 2.0** with `AsyncSession`. Never use sync sessions.
- All PostGIS geometry columns use **Geography(Point, 4326)** — not Geometry. This gives correct spherical distance calculations.
- All H3 operations use the **`h3` Python library** (Uber). Never implement H3 math manually.
- All Celery tasks must be **idempotent** — safe to re-run on retry.
- All external API calls go through service classes in `app/services/`. Routers never call external APIs directly.
- All config/secrets come from `app/config.py` (pydantic-settings). Never hardcode keys.
- Background jobs that process Sentinel-2 COGs must run in the **Celery worker container**, not FastAPI. EO processing is CPU/memory heavy.

### Convergence Scoring
- The Z-score formula is: `(raw_score - cell_μ) / cell_σ` where μ and σ are computed over the **365-day rolling baseline** per H3 cell.
- Signal weights are defined in `app/services/convergence_scorer.py` as a named constant dict. Never hardcode weights inline.
- H3 resolution breakpoints: **res 5** (global, zoom < 5) → **res 7** (regional, zoom 5–9) → **res 9** (tactical, zoom > 9).
- Cells with fewer than 30 baseline observations are marked `low_confidence=True` and rendered differently in the UI.

### BYOK Copilot
- The user's Anthropic API key is **never logged** and **never stored server-side** unless the user explicitly opts into encrypted server-side storage.
- The copilot router receives the key in the `X-Anthropic-Key` request header. It is held in memory for the duration of the request only.
- The copilot has access to 6 tool functions. See `ai-dev/field-schema.md` for the full tool manifest.
- All copilot tool calls that make live API requests (ACLED, STAC, Overpass, GFW) must enforce **rate limiting** to prevent abuse.

### Frontend
- Global state lives in **Zustand** (`src/store/echelonStore.ts`). No prop drilling beyond 2 levels.
- Map state (viewport, active layers, selected cell) is part of the Zustand store — not local component state.
- All API calls go through `src/services/api.ts`. Components never call `fetch()` directly.
- MapLibre and Deck.gl are initialized once in `EchelonMap.tsx`. Child components add/remove layers via the store.

### Auth
- Anonymous users: full read access to convergence map and copilot (BYOK key in browser localStorage).
- Authenticated users (GitHub OAuth): saved AOIs, alert subscriptions, optional server-side BYOK key storage.
- Session tokens are **HttpOnly cookies** — never exposed to JavaScript.

---

## Architecture Summary

Echelon is a multi-source GEOINT convergence dashboard. The core value proposition is automated signal fusion: rather than showing one data layer at a time, it computes a Z-score per H3 cell across five independent signal types (ACLED conflict events, GFW vessel anomalies, Sentinel-2 EO change detection, OSM infrastructure, news/GDELT) and renders the result as a convergence heatmap. High-Z cells represent locations where multiple independent signals are elevated above their historical baseline simultaneously.

Full architecture: see `ai-dev/architecture.md`.

---

## Hard Constraints

Read `ai-dev/guardrails/` before writing ANY code. Guardrails override all other instructions.

Key non-negotiables:
- Never log API keys, session tokens, or user email addresses
- Never call external APIs from FastAPI route handlers — use service classes
- Never store BYOK keys server-side without explicit user opt-in
- Never block the Celery worker event loop — EO tasks must use `asyncio.run()` or be synchronous
- All SQL uses parameterized queries — no string interpolation

---

## What NOT To Do

- Do not implement H3 cell math from scratch — use the `h3` library
- Do not put business logic in route handlers — it belongs in service classes
- Do not use `requests` (sync) in async FastAPI context — use `httpx` (async)
- Do not skip Alembic migrations — never use `Base.metadata.create_all()` in production
- Do not render raw H3 polygon GeoJSON for the global view — it will kill the browser; use server-side aggregation
- Do not call the Anthropic API from the frontend — route all copilot calls through the FastAPI `/copilot` router
- Do not put the convergence scorer in a route handler — it runs as a Celery beat task
