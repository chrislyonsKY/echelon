# Agent Library — Echelon

All agents read CLAUDE.md first, then architecture.md, then guardrails/.

| Agent | File | Use When |
|-------|------|----------|
| Architect | `architect.md` | System design, module interfaces, structural review, PostGIS schema |
| GEOINT Data Expert | `geoint_data_expert.md` | Implementing service clients, parsing API responses, EO processing |
| Data & Database Expert | `data_expert.md` | SQL queries, Alembic migrations, convergence scoring aggregations |
| Frontend Expert | `frontend_expert.md` | React components, MapLibre/Deck.gl layers, Zustand store, accessibility |
| DevOps Expert | `devops_expert.md` | Docker Compose, Cloudflare Pages + DigitalOcean deployment, Celery monitoring |
| QA Reviewer | `qa_reviewer.md` | Pre-PR review, testing strategy, security checklist |
