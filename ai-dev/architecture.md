# Echelon — Architecture

**Version:** 0.1.0
**Last Updated:** 2025-03-25
**Author:** Chris Lyons

---

## System Overview

Echelon is a multi-source GEOINT convergence dashboard. The core insight is that a single signal (one ACLED event, one AIS gap) is low-confidence noise. Multiple independent signals elevated simultaneously in the same location is analytically meaningful — a convergence. Echelon automates this fusion.

```
Open Data Sources
       │
       ▼
  Celery Beat (scheduled ingestion)
       │
       ▼
  Signal Ingestors (per source, async)
       │
       ▼
  PostGIS (signals table, H3 cells)
       │
       ▼
  Convergence Scorer (Z-score per H3 cell)
       │
       ▼
  h3_convergence_scores table (cached)
       │
  ┌────┴────────────────┐
  ▼                     ▼
FastAPI             Alert Engine
  │                 (Celery task)
  ▼                     │
MapLibre/Deck.gl      Resend
(frontend)           (email)
```

---

## Container Architecture

| Container | Image | Role | Exposed Port |
|-----------|-------|------|--------------|
| `nginx` | nginx:1.27-alpine | Reverse proxy, SSL termination, static serving | 80 (public) |
| `frontend` | Custom Vite build | Builds static assets into shared volume | none |
| `api` | Custom FastAPI | REST API, OAuth, copilot proxy | internal :8000 |
| `worker` | Same as api | Celery worker (ingestion, EO processing) | none |
| `beat` | Same as api | Celery beat scheduler | none |
| `flower` | Same as api | Celery task monitoring (internal only) | internal :5555 |
| `db` | postgis/postgis:16-3.4 | Primary data store | internal :5432 |
| `redis` | redis:7.2-alpine | Celery broker (db 1), API cache (db 0) | internal :6379 |

Nginx routes:
- `/api/*` → FastAPI (:8000)
- `/flower/*` → Flower (:5555) — basic auth protected
- `/*` → Static frontend from shared volume

---

## Data Model

### Core Tables

**`signals`** — All ingested events from all sources, unified schema
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
source          TEXT NOT NULL  -- 'acled' | 'gfw' | 'sentinel2' | 'osm' | 'gdelt' | 'newsdata'
signal_type     TEXT NOT NULL  -- e.g. 'battle', 'ais_gap', 'nbr_anomaly', 'military_construction'
h3_index_5      TEXT NOT NULL  -- H3 cell at resolution 5
h3_index_7      TEXT NOT NULL  -- H3 cell at resolution 7
h3_index_9      TEXT NOT NULL  -- H3 cell at resolution 9
location        GEOGRAPHY(Point, 4326) NOT NULL
occurred_at     TIMESTAMPTZ NOT NULL
ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
weight          FLOAT NOT NULL  -- signal type weight from scorer config
raw_payload     JSONB          -- original API response (full fidelity)
source_id       TEXT           -- original ID from source system
dedup_hash      TEXT UNIQUE    -- SHA256 of (source, source_id, occurred_at)
```

**`h3_cell_baseline`** — Rolling 365-day statistics per H3 cell per signal type
```sql
h3_index        TEXT NOT NULL
resolution      INT NOT NULL   -- 5, 7, or 9
signal_source   TEXT NOT NULL
window_days     INT NOT NULL DEFAULT 365
mu              FLOAT NOT NULL -- mean raw score
sigma           FLOAT NOT NULL -- standard deviation
observation_count INT NOT NULL
last_computed   TIMESTAMPTZ NOT NULL
low_confidence  BOOLEAN NOT NULL DEFAULT false  -- true if count < 30
PRIMARY KEY (h3_index, resolution, signal_source)
```

**`h3_convergence_scores`** — Pre-computed Z-scores per H3 cell (refreshed every 15min)
```sql
h3_index        TEXT NOT NULL
resolution      INT NOT NULL
z_score         FLOAT NOT NULL
raw_score       FLOAT NOT NULL
signal_breakdown JSONB         -- per-source contribution to raw_score
low_confidence  BOOLEAN NOT NULL DEFAULT false
computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
PRIMARY KEY (h3_index, resolution)
```

**`users`** — Authenticated users (GitHub OAuth)
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
github_id       BIGINT UNIQUE NOT NULL
github_username TEXT NOT NULL
email           TEXT
byok_key_enc    TEXT          -- AES-256 encrypted Anthropic key (opt-in only)
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now()
```

**`aois`** — Saved areas of interest
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id         UUID REFERENCES users(id) ON DELETE CASCADE
name            TEXT NOT NULL
geometry        GEOGRAPHY(Polygon, 4326) NOT NULL
alert_threshold FLOAT NOT NULL DEFAULT 2.0
alert_email     BOOLEAN NOT NULL DEFAULT false
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```

**`alerts`** — Fired alert events (in-app + email)
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
aoi_id          UUID REFERENCES aois(id) ON DELETE CASCADE
trigger_type    TEXT NOT NULL  -- 'zscore_threshold' | 'new_event_type' | 'ais_gap' | 'news_spike'
trigger_detail  JSONB NOT NULL
h3_index        TEXT NOT NULL
z_score         FLOAT
fired_at        TIMESTAMPTZ NOT NULL DEFAULT now()
email_sent      BOOLEAN NOT NULL DEFAULT false
read_at         TIMESTAMPTZ
```

---

## Convergence Scoring Engine

### Signal Weights (default, configurable via advanced UI)

```python
SIGNAL_WEIGHTS = {
    "gfw_ais_gap":              0.35,  # AIS disabling event — highest specificity
    "acled_battle":             0.30,  # ACLED battle/explosion — human-coded ground truth
    "acled_explosion":          0.30,
    "sentinel2_nbr_anomaly":    0.25,  # EO change — objective sensor data
    "acled_other":              0.15,  # ACLED other event types
    "gdelt_conflict":           0.12,  # GDELT conflict-coded article
    "newsdata_article":         0.12,
    "gfw_loitering":            0.10,  # Vessel loitering near infrastructure
    "osm_change":               0.08,  # OSM infrastructure change
}
```

### Z-Score Formula

```
raw_score(cell, t) = Σ signal_weight(s) × recency_factor(age_hours) × deduped_count(s, cell, t)

recency_factor(age_hours) = exp(-0.05 × age_hours)
  # Half-life ≈ 14 hours — recent signals decay slowly, old signals near-zero after ~3 days

z_score(cell, t) = (raw_score(cell, t) - μ(cell)) / max(σ(cell), 0.001)
  # σ floor prevents division by zero in quiet cells

low_confidence = baseline_observations < 30
```

### H3 Resolution Breakpoints

| Map Zoom | H3 Resolution | Approx Cell Size | Use |
|----------|--------------|-----------------|-----|
| < 5 | res 5 | ~252 km² | Global overview heatmap |
| 5–9 | res 7 | ~5.2 km² | Regional investigation |
| > 9 | res 9 | ~0.1 km² | Tactical detail |

Convergence scores are pre-computed and cached at all three resolutions. The frontend requests the appropriate resolution based on current zoom level.

---

## Ingestion Schedule (Celery Beat)

| Task | Frequency | Source | Notes |
|------|-----------|--------|-------|
| `ingest_acled` | Every 6 hours | ACLED API | Rate-limited; fetches new events since last run |
| `ingest_gfw_events` | Every 12 hours | GFW Events API | AIS gaps, loitering, port avoidance |
| `ingest_gdelt` | Every 1 hour | GDELT bulk files | Conflict-coded events only (CAMEO 19x, 20x) |
| `ingest_newsdata` | Every 4 hours | NewsData.io API | Conflict keywords, stored for UI sidebar |
| `ingest_osm_changes` | Every 24 hours | Overpass API | Military/infrastructure tag changes |
| `trigger_sentinel2_jobs` | Every 24 hours | Element84 STAC | Queues scene-fetch tasks per active AOI |
| `process_sentinel2_scene` | On demand (queued) | Element84 COG | NBR delta computation, heavy CPU |
| `recompute_convergence` | Every 15 minutes | PostGIS | Refreshes h3_convergence_scores at all resolutions |
| `check_aoi_alerts` | Every 15 minutes | PostGIS | Compares scores against AOI thresholds, fires alerts |
| `trim_old_signals` | Every 24 hours | PostGIS | Deletes signals older than 365 days (baseline window) |

---

## BYOK Copilot Architecture

The copilot is a full Claude agent with 6 tool functions. All tool calls that hit live APIs are proxied through the FastAPI `/api/copilot/chat` endpoint.

### Tool Manifest

```python
COPILOT_TOOLS = [
    {
        "name": "query_acled",
        "description": "Query live ACLED conflict event data for a bounding box and date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                "date_from": {"type": "string", "format": "date"},
                "date_to": {"type": "string", "format": "date"},
                "event_types": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["bbox", "date_from", "date_to"]
        }
    },
    {
        "name": "query_stac",
        "description": "Search for Sentinel-2 scenes via Element84 Earth Search STAC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                "date_from": {"type": "string", "format": "date"},
                "date_to": {"type": "string", "format": "date"},
                "cloud_cover_max": {"type": "number", "minimum": 0, "maximum": 100}
            },
            "required": ["bbox", "date_from", "date_to"]
        }
    },
    {
        "name": "query_overpass",
        "description": "Query OpenStreetMap Overpass API for infrastructure features in a bounding box.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "OSM tag filters e.g. ['military', 'aeroway=aerodrome']"}
            },
            "required": ["bbox", "tags"]
        }
    },
    {
        "name": "query_vessels",
        "description": "Query GlobalFishingWatch for vessel events and anomalies in a bounding box.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                "date_from": {"type": "string", "format": "date"},
                "date_to": {"type": "string", "format": "date"},
                "event_types": {"type": "array", "items": {"type": "string"}, "description": "GFW event types: ais_gap, loitering, port_visit, encounter"}
            },
            "required": ["bbox", "date_from", "date_to"]
        }
    },
    {
        "name": "get_convergence_score",
        "description": "Retrieve the pre-computed convergence Z-score for a bounding box from the PostGIS cache.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                "resolution": {"type": "integer", "enum": [5, 7, 9]}
            },
            "required": ["bbox"]
        }
    },
    {
        "name": "get_news",
        "description": "Search for news articles relevant to a geographic area and keywords.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "date_from": {"type": "string", "format": "date"},
                "date_to": {"type": "string", "format": "date"}
            },
            "required": ["bbox"]
        }
    }
]
```

### Map Control Protocol

When the copilot determines that the map should respond to a query (e.g., "show me unusual vessel behavior near Crimea"), it returns a structured `map_action` object alongside its text response:

```json
{
  "text": "I found 3 AIS gap events near the Kerch Strait in the past week...",
  "map_action": {
    "type": "fly_to",
    "center": [36.6, 45.3],
    "zoom": 8,
    "highlight_cells": ["851f91bfffffff", "851f91c7fffffff"],
    "active_layers": ["gfw_events", "acled"]
  }
}
```

The frontend Zustand store handles `map_action` dispatch independently of the chat message rendering.

---

## Authentication Flow

```
User clicks "Sign In with GitHub"
    │
    ▼
GET /api/auth/login
    → Redirect to GitHub OAuth authorize URL
    │
    ▼
GitHub redirects to /api/auth/callback?code=xxx
    │
    ▼
FastAPI exchanges code for access token
    → Fetches GitHub user profile
    → Upserts user record in PostGIS
    → Sets HttpOnly session cookie (signed, 7-day expiry)
    │
    ▼
Frontend reads /api/auth/me — gets user profile
```

Anonymous users: all read endpoints work without cookie. Write endpoints (save AOI, create alert) return 401 if unauthenticated.

---

## EO Change Detection Pipeline

1. **Celery Beat** triggers `trigger_sentinel2_jobs` daily
2. For each active AOI, queries Element84 Earth Search STAC for:
   - Scenes from the past 7 days (cloud cover < 20%)
   - Scenes from same week 12 months prior (baseline)
3. Queues `process_sentinel2_scene` task per scene pair
4. Worker downloads B08 (NIR) and B11 (SWIR) bands as COG windows
5. Computes NBR = (NIR - SWIR) / (NIR + SWIR) for both scenes
6. Delta NBR > 0.1 threshold → creates `sentinel2_nbr_anomaly` signal record
7. NDVI delta (B08, B04) computed as secondary signal for vegetation destruction

All raster work uses `rasterio` with windowed reading — never loads full scenes into memory.

---

## Deployment (Production)

- **Frontend:** Render static site (free tier) — Vite build output
- **Backend stack:** Railway — Docker Compose services
  - FastAPI, worker, beat, flower, db (PostGIS), redis
  - Railway usage-based pricing; estimated ~$20–35/month at steady state
- **Environment variables:** Set in Railway dashboard, never in committed files
- **Persistent volumes:** Railway volume mounts for PostGIS data and Redis AOF
