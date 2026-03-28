"""
OSINT scraper ingestion task.

Ingests data from the OSINTScraperService, which aggregates results from
multiple open-source intelligence feeds. Each result with valid geolocation
is inserted as a signal of type "osint_scrape".

Task is idempotent — safe to retry on failure.
"""
import asyncio
import logging
from datetime import datetime, timezone

import h3
import orjson
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.convergence_scorer import SIGNAL_WEIGHTS
from app.services.osint_scraper import OSINTScraperService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_INSERT_SIGNAL_SQL = text("""
    INSERT INTO signals (
        source, signal_type, h3_index_5, h3_index_7, h3_index_9,
        location, occurred_at, ingested_at, weight,
        raw_payload, source_id, dedup_hash
    ) VALUES (
        :source, :signal_type, :h3_index_5, :h3_index_7, :h3_index_9,
        ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326),
        :occurred_at, NOW(), :weight,
        CAST(:raw_payload AS jsonb), :source_id, :dedup_hash
    )
    ON CONFLICT (dedup_hash) DO NOTHING
""")


@celery_app.task(
    name="app.workers.tasks.ingest_osint_scrape.run",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
    acks_late=True,
)
def run(self) -> dict:
    """Scrape and ingest the latest OSINT sources.

    Returns:
        Dict with inserted, skipped, and total_fetched counts.
    """
    try:
        return asyncio.run(_ingest())
    except Exception as exc:
        logger.exception("OSINT scrape ingestion failed")
        raise self.retry(exc=exc)


async def _ingest() -> dict:
    """Async implementation of the OSINT scrape ingestion pipeline."""
    service = OSINTScraperService()

    try:
        results = await service.scrape_all_sources()
    finally:
        await service.close()

    if not results:
        logger.info("OSINT scrape: no results returned")
        return {"inserted": 0, "skipped": 0, "total_fetched": 0}

    weight = SIGNAL_WEIGHTS.get("osint_scrape", 0.12)
    rows: list[dict] = []

    for item in results:
        lat = item.get("latitude")
        lon = item.get("longitude")
        if lat is None or lon is None:
            continue

        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            continue

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue

        published_at = item.get("published_at", "")
        try:
            occurred_at = datetime.fromisoformat(published_at).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            occurred_at = datetime.now(tz=timezone.utc)

        raw_payload = orjson.dumps({
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "url": item.get("url", ""),
            "source": item.get("source", ""),
        }).decode()

        rows.append({
            "source": "osint_scrape",
            "signal_type": "osint_scrape",
            "h3_index_5": h3.geo_to_h3(lat, lon, 5),
            "h3_index_7": h3.geo_to_h3(lat, lon, 7),
            "h3_index_9": h3.geo_to_h3(lat, lon, 9),
            "latitude": lat,
            "longitude": lon,
            "occurred_at": occurred_at,
            "weight": weight,
            "raw_payload": raw_payload,
            "source_id": item.get("url", ""),
            "dedup_hash": service.build_dedup_hash(item),
        })

    result = await _bulk_insert(rows)

    logger.info(
        "OSINT scrape ingestion complete — %d inserted/%d skipped out of %d fetched",
        result["inserted"], result["skipped"], len(results),
    )
    return {
        "inserted": result["inserted"],
        "skipped": result["skipped"],
        "total_fetched": len(results),
    }


async def _bulk_insert(rows: list[dict]) -> dict:
    """Insert signal rows with ON CONFLICT DO NOTHING.

    Args:
        rows: List of parameterized row dicts.

    Returns:
        Dict with 'inserted', 'skipped', 'total' counts.
    """
    if not rows:
        return {"inserted": 0, "skipped": 0, "total": 0}

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    inserted = 0
    skipped = 0

    try:
        async with session_factory() as session:
            for row in rows:
                result = await session.execute(_INSERT_SIGNAL_SQL, row)
                if result.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
            await session.commit()
    finally:
        await engine.dispose()

    return {"inserted": inserted, "skipped": skipped, "total": len(rows)}
