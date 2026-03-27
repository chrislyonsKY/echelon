# Echelon

![License](https://img.shields.io/badge/license-Apache%202.0-blue)
![Python](https://img.shields.io/badge/python-3.12-informational)
![TypeScript](https://img.shields.io/badge/typescript-5.4-informational)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![MapLibre](https://img.shields.io/badge/MapLibre%20GL%20JS-4.x-396CB2)
![PostGIS](https://img.shields.io/badge/PostGIS-3.4-336791?logo=postgresql)
![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker)
![DigitalOcean](https://img.shields.io/badge/DigitalOcean-0080FF?logo=digitalocean&logoColor=white)
![Cloudflare](https://img.shields.io/badge/Cloudflare-F38020?logo=cloudflare&logoColor=white)
![Status](https://img.shields.io/badge/status-active-brightgreen)

> Open-source GEOINT conflict and maritime activity monitoring dashboard powered by multi-source signal convergence.

## Overview

Echelon fuses five independent open-data signal streams — GDELT conflict events and GKG threat articles, Global Fishing Watch vessel anomalies, Sentinel-2 EO change detection, OSM infrastructure overlays, and multi-source news feeds — into a single convergence heatmap. Rather than showing one data layer at a time, Echelon computes a Z-score per H3 cell against a 365-day rolling baseline, surfacing locations where multiple independent signals are simultaneously elevated. A BYOK Anthropic copilot agent can query all data sources via natural language and control the map directly.

Designed for OSINT researchers, journalists, policy analysts, and the public. No account required to use the map.

## Data Sources

| Source | Signal Type | Weight | Access |
|--------|------------|--------|--------|
| [Global Fishing Watch](https://globalfishingwatch.org) | AIS gap (dark vessel) | 0.35 | Free (non-commercial) |
| [GDELT Events](https://gdeltproject.org) | CAMEO conflict codes | 0.30 | Free / open |
| [Sentinel-2 / Element84](https://earth-search.aws.element84.com) | EO change detection (NBR) | 0.25 | Free / open STAC |
| [GDELT GKG](https://gdeltproject.org) | Threat-themed articles | 0.15 | Free / open |
| [NewsData](https://newsdata.io) / [NewsAPI](https://newsapi.org) / [GNews](https://gnews.io) | Conflict news articles | 0.12 | Free tiers |
| [GFW](https://globalfishingwatch.org) | Vessel loitering | 0.10 | Free (non-commercial) |
| [OSM Overpass](https://overpass-api.de) | Military / infrastructure | 0.08 | Free / open |

> Data sourced from ACLED (acleddata.com), Global Fishing Watch (globalfishingwatch.org), GDELT Project (gdeltproject.org).

## Getting Started

### Prerequisites

- Docker & Docker Compose v2
- 4GB RAM minimum (8GB recommended for EO processing)
- API keys: GFW, NewsData, NewsAPI, GNews (all free tiers)
- GitHub OAuth App credentials (for user auth)
- Anthropic API key (BYOK, user-supplied in browser)

### Local Development

```bash
git clone https://github.com/chrislyonsKY/echelon.git
cd echelon
cp .env.example .env
# Edit .env with your API keys
docker compose up --build
```

The app will be available at `http://localhost`.

After containers are healthy, run the initial migration:

```bash
docker compose exec api alembic upgrade head
```

## Deployment

### Infrastructure

| Component | Provider | Purpose |
|-----------|----------|---------|
| **Backend** | [DigitalOcean](https://digitalocean.com) Droplet | Docker Compose (API, workers, PostGIS, Redis) |
| **CDN / SSL** | [Cloudflare](https://cloudflare.com) | DNS, SSL termination, DDoS protection, edge caching |

### Production Deploy (DigitalOcean + Cloudflare)

**1. Droplet Setup**

```bash
# SSH into your Droplet
ssh -i ~/.ssh/id_echelon root@<DROPLET_IP>

# Install Docker
apt update && apt install -y docker.io docker-compose-v2 git

# Clone and configure
git clone https://github.com/chrislyonsKY/echelon.git
cd echelon
cp .env.example .env
nano .env  # Fill in all API keys and secrets

# Launch
docker compose up -d --build

# Run migration
docker compose exec api alembic upgrade head
```

**2. Cloudflare DNS**

- `A` record: `echelon-geoint.org` -> Droplet IP (Proxied, orange cloud)
- SSL mode: **Full (strict)**
- Cloudflare handles SSL termination, caching, and DDoS protection

**3. GitHub OAuth**

Set the callback URL in your GitHub OAuth App settings:
```
https://echelon-geoint.org/api/auth/callback
```

### Updating

```bash
ssh -i ~/.ssh/id_echelon root@<DROPLET_IP>
cd echelon
git pull
docker compose up -d --build
```

## Usage

- **Convergence heatmap** -- The primary view. H3 cells colored by Z-score (standard deviations above baseline). Click any cell to open the investigation sidebar.
- **Investigation sidebar** -- Three tabs: Layer Panel (toggle individual signal feeds), Event Timeline (chronological signal feed for selected cell), Signal Cards (sourced evidence cards per event).
- **Copilot** -- Enter your Anthropic API key to enable. Ask questions like *"Show me unusual vessel behavior near the Strait of Hormuz this week"* or *"What's driving the convergence spike in eastern Ukraine?"*
- **Alerts** -- Sign in with GitHub to save AOIs and receive email alerts when Z-scores cross thresholds.

## Architecture

8-container Docker Compose stack:

```
Cloudflare (CDN + SSL)
  |
DigitalOcean Droplet
  |
  Nginx (reverse proxy)
  +-- Frontend (Vite/React/MapLibre/Deck.gl)
  +-- FastAPI (API + copilot proxy)
      +-- PostgreSQL + PostGIS (H3 cells, signals, users, AOIs)
      +-- Redis (Celery broker + API response cache)
      +-- Celery Worker (ingestion, EO processing)
      +-- Celery Beat (scheduled jobs every 15min)
      +-- Flower (task monitoring, internal)
```

Full architecture documentation in `ai-dev/architecture.md`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities. **Never report API key exposure through public Issues.**

## License

Apache 2.0 -- see [LICENSE](LICENSE) for details.

---

*Built by [Chris Lyons](https://github.com/chrislyonsKY)*
