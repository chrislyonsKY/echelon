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

> Open-source GEOINT convergence dashboard for conflict and maritime monitoring. 20+ live data sources fused into a single intelligence picture.

**Live: [echelon-geoint.org](https://echelon-geoint.org)**

## What It Does

Echelon fuses **20 independent open-data signal streams** into a single convergence heatmap. Instead of showing one data layer at a time, it computes a Z-score per H3 hexagonal cell, surfacing locations where multiple independent signals are simultaneously elevated above their historical baseline.

An AI copilot (BYOK — bring your own key) can query all data sources via natural language and fly the map to areas of interest.

## Data Sources

### Conflict & Events
| Source | Signal | Weight | Schedule |
|--------|--------|--------|----------|
| [GDELT](https://gdeltproject.org) Export | CAMEO conflict codes | 0.30 | 15 min |
| [GDELT](https://gdeltproject.org) GKG | Threat-themed articles | 0.15 | 15 min |

### Maritime
| Source | Signal | Weight | Schedule |
|--------|--------|--------|----------|
| [Global Fishing Watch](https://globalfishingwatch.org) | AIS gaps (dark vessels) | 0.35 | 12h |
| [Global Fishing Watch](https://globalfishingwatch.org) | Vessel loitering | 0.10 | 12h |
| [AISStream](https://aisstream.io) | Real-time AIS positions | 0.08 | 30 min |

### Aviation
| Source | Signal | Weight | Schedule |
|--------|--------|--------|----------|
| [OpenSky Network](https://opensky-network.org) | Military ADS-B | 0.20 | 30 min |

### Earth Observation
| Source | Signal | Weight | Schedule |
|--------|--------|--------|----------|
| [Sentinel-2 / Element84](https://earth-search.aws.element84.com) | NBR change detection | 0.25 | Daily |

### Infrastructure
| Source | Signal | Weight | Schedule |
|--------|--------|--------|----------|
| [OSM via ohsome](https://ohsome.org) | Military tag change detection | 0.08 | Daily |

### News (3 APIs)
| Source | Signal | Weight | Schedule |
|--------|--------|--------|----------|
| [NewsData](https://newsdata.io) / [NewsAPI](https://newsapi.org) / [GNews](https://gnews.io) | Conflict articles | 0.12 | 4h |

### OSINT Scraper (9 sources)
| Source | Signal | Weight | Schedule |
|--------|--------|--------|----------|
| RSS (Bellingcat, Crisis Group, RUSI, War on the Rocks, Janes) | Conflict reporting | 0.12 | 2h |
| Telegram public channels | Real-time conflict posts | 0.12 | 2h |
| Reddit (r/OSINT, r/geopolitics, r/CredibleDefense) | Community intelligence | 0.12 | 2h |
| YouTube | Conflict video search | 0.12 | 2h |
| Mastodon | OSINT community posts | 0.12 | 2h |
| Bluesky | OSINT/conflict posts | 0.12 | 2h |
| Nitter/X | Twitter conflict content | 0.12 | 2h |
| UN ReliefWeb | Humanitarian reports | 0.12 | 2h |
| RansomWatch | Dark web monitoring (clearnet) | 0.12 | 2h |

### Reference Data (loaded at startup)
| Source | Records | Purpose |
|--------|---------|---------|
| [GeoNames](https://geonames.org) | 33,442 cities + country/admin codes | City-level geocoding with context weighting |
| [OurAirports](https://ourairports.com) | 474 military airfields | Infrastructure enrichment |
| [geoBoundaries](https://geoboundaries.org) | ADM1 polygons (global) | AOI normalization and boundary lookups |

> Data attribution: GDELT Project (gdeltproject.org), Global Fishing Watch (globalfishingwatch.org), OpenStreetMap contributors.

## Features

- **Convergence heatmap** — H3 hexagonal cells colored by Z-score. Click any cell to investigate.
- **Investigation sidebar** — narrative summary of signals in a cell, grouped by source with event details.
- **Location search** — type a place name, fly there instantly (Nominatim geocoder).
- **Live event feed** — scrolling feed of latest signals globally. Click to fly to location.
- **AI copilot** — BYOK with 4 providers (Anthropic Claude, OpenAI GPT-4o, Google Gemini, self-hosted Ollama). 7 tool functions query live data. Hardened guardrails prevent off-topic use.
- **GitHub OAuth** — sign in to save AOIs and receive email alerts.
- **Email alerts** — threshold-based alerts via Resend when Z-scores spike in saved areas.
- **Multi-layer map** — toggle conflict events (red), vessel activity (blue), news/OSINT (amber), infrastructure (green), military aviation (cyan).

## Getting Started

### Prerequisites

- Docker & Docker Compose v2
- 4GB RAM minimum (8GB recommended)
- API keys: GFW, NewsData, NewsAPI, GNews (all free tiers)
- Optional: AISStream, YouTube Data API, OpenSky (all free)
- GitHub OAuth App for user authentication

### Local Development

```bash
git clone https://github.com/chrislyonsKY/echelon.git
cd echelon
cp .env.example .env
# Edit .env with your API keys
docker compose up --build
# After containers are healthy:
docker compose exec api alembic upgrade head
```

Open `http://localhost` in your browser.

## Deployment

Two deployment paths are supported:

- Managed deployment: Railway for the backend stack plus Render for the static frontend. See [DEPLOY.md](DEPLOY.md).
- Self-hosted deployment: Docker Compose on a VPS such as DigitalOcean, Hetzner, or similar.

### Self-Hosted Production Deploy

```bash
# On the VPS:
apt update && apt install -y docker.io docker-compose-v2 git
git clone https://github.com/chrislyonsKY/echelon.git
cd echelon
cp .env.example .env && nano .env  # Fill in API keys
docker compose up -d --build
docker compose exec api alembic upgrade head
```

If you front the stack with Cloudflare or another CDN, use HTTPS end to end and set the GitHub OAuth callback to your public `/api/auth/callback` URL.

### Updating

```bash
cd echelon && git pull
docker compose up -d --build --force-recreate
```

## Architecture

```
User Browser
  │
  ├── Static frontend (Vite / React / MapLibre GL JS / Deck.gl)
  └── FastAPI (REST API + copilot proxy)
      ├── PostgreSQL + PostGIS (signals, H3 cells, users, AOIs)
      ├── Redis (Celery broker + cache)
      ├── Celery Worker (ingestion, EO processing)
      ├── Celery Beat (scheduled jobs)
      └── Flower (task monitoring)
```

## Convergence Scoring

```
raw_score(cell) = Σ weight(signal) × exp(-0.05 × age_hours)
z_score(cell)   = (raw_score - μ) / max(σ, 0.001)
```

- **H3 resolutions:** 5 (global ~252km²) → 7 (regional ~5km²) → 9 (tactical ~0.1km²)
- **Baseline:** warm-start incremental — μ and σ are updated with each scoring cycle. Z-scores become meaningful after ~30 observations per cell (typically 1–2 weeks of ingestion). Cells below this threshold are flagged `low_confidence`.
- **Recomputed** every 15 minutes
- **Data retention:** signals older than 365 days are trimmed daily; baseline statistics are preserved independently

## Security

- BYOK API keys: sent per request only, never logged, and not persisted by the current UI flow
- Session cookies: HttpOnly, SameSite=Lax, Secure
- Copilot guardrails: input pattern blocklist, injection detection, GEOINT-only system prompt
- All SQL parameterized — no string interpolation
- See [SECURITY.md](SECURITY.md) for vulnerability reporting

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Disclaimer

Echelon is an OSINT research tool provided "as is" without warranty. It is **not a substitute for professional intelligence analysis**. Data may be incomplete, delayed, or inaccurate. AI copilot outputs may contain errors or hallucinations. Convergence scores are statistical indicators, not confirmed events.

This tool must not be used for targeting individuals, surveillance, offensive operations, or any unlawful purpose. Users are responsible for compliance with all applicable laws. Echelon is not affiliated with any government or intelligence agency.

All data comes from publicly available open sources. See [DISCLAIMER.md](DISCLAIMER.md) for the full legal disclaimer.

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*Built by [Chris Lyons](https://github.com/chrislyonsKY)*
