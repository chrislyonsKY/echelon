# Echelon

![License](https://img.shields.io/badge/license-Apache%202.0-blue)
![Python](https://img.shields.io/badge/python-3.12-informational)
![TypeScript](https://img.shields.io/badge/typescript-5.4-informational)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![MapLibre](https://img.shields.io/badge/MapLibre%20GL%20JS-4.x-396CB2)
![PostGIS](https://img.shields.io/badge/PostGIS-3.4-336791?logo=postgresql)
![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker)
![Status](https://img.shields.io/badge/status-active-brightgreen)

> Open-source GEOINT conflict and maritime activity monitoring dashboard powered by multi-source signal convergence.

## Overview

Echelon fuses five independent open-data signal streams — ACLED conflict events, Global Fishing Watch vessel anomalies, Sentinel-2 EO change detection, OSM infrastructure overlays, and GDELT/news feeds — into a single convergence heatmap. Rather than showing one data layer at a time, Echelon computes a Z-score per H3 cell against a 365-day rolling baseline, surfacing locations where multiple independent signals are simultaneously elevated. A BYOK Anthropic copilot agent can query all data sources via natural language and control the map directly.

Designed for OSINT researchers, journalists, policy analysts, and the public. No account required to use the map.

## Data Sources

| Source | Signal Type | Access |
|--------|------------|--------|
| [ACLED](https://acleddata.com) | Conflict events | Free (registration required) |
| [Global Fishing Watch](https://globalfishingwatch.org) | Vessel anomalies / AIS gaps | Free (non-commercial) |
| [Sentinel-2 / Element84](https://earth-search.aws.element84.com) | EO change detection (NBR) | Free / open STAC |
| [OSM Overpass](https://overpass-api.de) | Military / infrastructure | Free / open |
| [GDELT](https://gdeltproject.org) | News / event coding | Free / open |
| [NewsData.io](https://newsdata.io) | Human-readable news feed | Free tier |
| [NGA LandScan](https://landscan.ornl.gov) | Population density context | Free |

## Getting Started

### Prerequisites

- Docker Desktop 4.x+
- Docker Compose v2.x+
- 8GB RAM recommended (PostGIS + EO processing)
- API keys: ACLED, GFW, NewsData.io, Anthropic (BYOK, user-supplied)
- GitHub OAuth App credentials (for auth)

### Installation

```bash
git clone https://github.com/chrislyonsKY/echelon.git
cd echelon
cp .env.example .env
# Edit .env with your API keys
docker compose up --build
```

The app will be available at `http://localhost:80`.

### Bootstrap (first run)

After containers are healthy, run the historical data backfill to seed the Z-score baseline:

```bash
docker compose exec worker python -m app.workers.tasks.bootstrap_baseline
```

This pulls 365 days of ACLED history and seeds the H3 cell baseline table. Takes 15–30 minutes depending on ACLED access tier.

## Usage

- **Convergence heatmap** — The primary view. H3 cells colored by Z-score (standard deviations above baseline). Click any cell to open the investigation sidebar.
- **Investigation sidebar** — Three tabs: Layer Panel (toggle individual signal feeds), Event Timeline (chronological signal feed for selected AOI), Signal Cards (sourced evidence cards per event).
- **Copilot** — Enter your Anthropic API key in Settings to enable. Ask questions like *"Show me unusual vessel behavior near the Strait of Hormuz this week"* or *"What's driving the convergence spike in eastern Ukraine?"*
- **Alerts** — Create an account (GitHub OAuth) to save AOIs and receive email alerts when Z-scores cross thresholds.

## Architecture

8-container Docker Compose stack:

```
Nginx (reverse proxy)
├── Frontend (Vite/React/MapLibre/Deck.gl)
└── FastAPI (API + copilot proxy)
    ├── PostgreSQL + PostGIS (H3 cells, signals, users, AOIs)
    ├── Redis (Celery broker + API response cache)
    ├── Celery Worker (EO processing, ingestion)
    ├── Celery Beat (scheduled ingestion jobs)
    └── Flower (Celery monitoring, internal only)
```

Full architecture documentation in `ai-dev/architecture.md`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities. **Never report API key exposure through public Issues.**

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.

---

*Built by [Chris Lyons](https://github.com/chrislyonsKY)*
