"""
Source health router — telemetry for all ingestion sources.

Queries Redis for last-run timestamps and the signals table for
recent counts and error rates per source.
"""
import logging
from datetime import datetime, timezone

import redis
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter()

# All known ingestor source keys (must match Redis key pattern)
SOURCES = [
    {"key": "gfw", "name": "Global Fishing Watch", "schedule": "12h"},
    {"key": "gdelt", "name": "GDELT", "schedule": "15m"},
    {"key": "newsdata", "name": "News (3 APIs)", "schedule": "4h"},
    {"key": "osm", "name": "OSM (ohsome)", "schedule": "daily"},
    {"key": "opensky", "name": "OpenSky ADS-B", "schedule": "30m"},
    {"key": "osint_scrape", "name": "OSINT Scraper", "schedule": "2h"},
    {"key": "aisstream", "name": "AISStream", "schedule": "30m"},
    {"key": "firms", "name": "NASA FIRMS", "schedule": "6h"},
    {"key": "sentinel2", "name": "Sentinel-2 EO", "schedule": "daily"},
    {"key": "convergence", "name": "Convergence Scorer", "schedule": "15m"},
]


def _get_redis():
    """Get a sync Redis client for reading telemetry keys."""
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _get_last_run(r: redis.Redis, key: str) -> datetime | None:
    """Resolve the last successful execution time for one logical source."""
    candidate_keys = [f"echelon:ingest:{key}:last_run"]
    if key == "newsdata":
        candidate_keys.append("echelon:ingest:news:last_run")

    for candidate in candidate_keys:
        raw = r.get(candidate)
        if not raw:
            continue
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            continue
    return None


@router.get("/sources")
async def get_source_health(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return health status for all ingestion sources.

    Includes last run time, signal counts (24h / 7d), and status indicator.
    """
    r = _get_redis()

    # Get signal counts per source from DB
    # Aggregate OSINT sub-sources (western_wire, aggregator, etc.) under osint_scrape
    count_result = await session.execute(text("""
        SELECT
            CASE
                WHEN source IN ('western_wire', 'iranian_state_media', 'aggregator',
                                'social_unofficial', 'html_rusi', 'html_janes')
                THEN 'osint_scrape'
                ELSE source
            END AS source_key,
            COUNT(*) FILTER (WHERE occurred_at >= NOW() - INTERVAL '24 hours') AS count_24h,
            COUNT(*) FILTER (WHERE occurred_at >= NOW() - INTERVAL '7 days') AS count_7d,
            MAX(occurred_at) AS last_signal_at
        FROM signals
        GROUP BY source_key
    """))
    db_stats = {row.source_key: row for row in count_result.fetchall()}

    sources = []
    for src in SOURCES:
        key = src["key"]

        # Read last_run from Redis
        last_run = _get_last_run(r, key)

        # DB stats
        stats = db_stats.get(key)
        count_24h = stats.count_24h if stats else 0
        count_7d = stats.count_7d if stats else 0
        last_signal = stats.last_signal_at if stats else None

        # Determine status
        if last_run and (datetime.now(timezone.utc) - last_run.replace(tzinfo=timezone.utc)).total_seconds() < 86400:
            status = "healthy" if count_24h > 0 else "degraded"
        elif count_7d > 0:
            status = "degraded"
        else:
            status = "inactive"

        sources.append({
            "key": key,
            "name": src["name"],
            "schedule": src["schedule"],
            "status": status,
            "lastRunAt": last_run.isoformat() if last_run else None,
            "lastSignalAt": last_signal.isoformat() if last_signal else None,
            "count24h": count_24h,
            "count7d": count_7d,
        })

    r.close()
    return sources


@router.get("/summary")
async def get_health_summary(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return overall system health summary."""
    result = await session.execute(text("""
        SELECT
            COUNT(*) AS total_signals,
            COUNT(*) FILTER (WHERE occurred_at >= NOW() - INTERVAL '24 hours') AS signals_24h,
            COUNT(DISTINCT source) AS active_sources,
            COUNT(DISTINCT h3_index_7) AS active_cells_7
        FROM signals
        WHERE occurred_at >= NOW() - INTERVAL '7 days'
    """))
    row = result.fetchone()

    score_result = await session.execute(text("""
        SELECT COUNT(*) AS scored_cells,
               AVG(z_score) AS avg_z_score,
               MAX(z_score) AS max_z_score
        FROM h3_convergence_scores
        WHERE raw_score > 0.01
    """))
    scores = score_result.fetchone()

    return {
        "totalSignals7d": row.total_signals if row else 0,
        "signals24h": row.signals_24h if row else 0,
        "activeSources": row.active_sources if row else 0,
        "activeCells": row.active_cells_7 if row else 0,
        "scoredCells": scores.scored_cells if scores else 0,
        "avgZScore": round(scores.avg_z_score or 0, 4),
        "maxZScore": round(scores.max_z_score or 0, 4),
    }
