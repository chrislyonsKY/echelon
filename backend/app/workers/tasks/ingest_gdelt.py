"""
GDELT bulk event ingestion task.

Two parallel ingest streams per run:
1. Event export — CAMEO conflict-coded events → signal type: gdelt_conflict
2. GKG — negative-tone threat-themed articles → signal type: gdelt_gkg_threat

Task is idempotent — safe to retry on failure.
"""
import asyncio
import logging
from datetime import datetime, timezone

import h3
import orjson
import redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.convergence_scorer import SIGNAL_WEIGHTS
from app.services.gdelt import GDELTService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

REDIS_LAST_EXPORT_KEY = "echelon:ingest:gdelt:last_export"
REDIS_LAST_GKG_KEY = "echelon:ingest:gdelt:last_gkg"

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
    name="app.workers.tasks.ingest_gdelt.run",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def run(self) -> dict:
    """Download and ingest the latest GDELT export and GKG files.

    Returns:
        Dict with counts for both export and GKG ingestion.
    """
    try:
        return asyncio.run(_ingest())
    except Exception as exc:
        logger.exception("GDELT ingestion failed")
        raise self.retry(exc=exc)


async def _ingest() -> dict:
    """Async implementation of the full GDELT ingestion pipeline."""
    service = GDELTService()

    try:
        urls = await service._get_lastupdate()
        export_url = urls.get("export", "")
        gkg_url = urls.get("gkg", "")

        redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            last_export = redis_client.get(REDIS_LAST_EXPORT_KEY)
            last_gkg = redis_client.get(REDIS_LAST_GKG_KEY)
        finally:
            redis_client.close()

        export_result = {"inserted": 0, "skipped": 0, "total": 0}
        gkg_result = {"inserted": 0, "skipped": 0, "total": 0}

        # Ingest event export
        if export_url and last_export != export_url:
            events = await service.fetch_latest_conflict_events()
            if events:
                export_result = await _insert_export_events(events, service)
            _set_redis_key(REDIS_LAST_EXPORT_KEY, export_url)
        else:
            logger.info("GDELT export: already ingested %s", export_url)

        # Ingest GKG threats
        if gkg_url and last_gkg != gkg_url:
            threats = await service.fetch_latest_gkg_threats()
            if threats:
                gkg_result = await _insert_gkg_threats(threats, service)
            _set_redis_key(REDIS_LAST_GKG_KEY, gkg_url)
        else:
            logger.info("GDELT GKG: already ingested %s", gkg_url)

    finally:
        await service.close()

    logger.info(
        "GDELT ingestion complete — export: %d inserted/%d skipped, "
        "GKG: %d inserted/%d skipped",
        export_result["inserted"], export_result["skipped"],
        gkg_result["inserted"], gkg_result["skipped"],
    )
    return {
        "export": export_result,
        "gkg": gkg_result,
        "export_url": export_url,
        "gkg_url": gkg_url,
    }


async def _insert_export_events(
    events: list[dict],
    service: GDELTService,
) -> dict:
    """Build and insert signal rows from GDELT export events.

    Returns:
        Dict with 'inserted', 'skipped', 'total' counts.
    """
    weight = SIGNAL_WEIGHTS.get("gdelt_conflict", 0.30)
    rows: list[dict] = []

    for event in events:
        lat = event["latitude"]
        lon = event["longitude"]
        sqldate = event.get("SQLDATE", "")
        try:
            occurred_at = datetime.strptime(sqldate, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        rows.append({
            "source": "gdelt",
            "signal_type": "gdelt_conflict",
            "h3_index_5": h3.geo_to_h3(lat, lon, 5),
            "h3_index_7": h3.geo_to_h3(lat, lon, 7),
            "h3_index_9": h3.geo_to_h3(lat, lon, 9),
            "latitude": lat,
            "longitude": lon,
            "occurred_at": occurred_at,
            "weight": weight,
            "raw_payload": orjson.dumps(event).decode(),
            "source_id": str(event.get("GlobalEventID", "")),
            "dedup_hash": service.build_dedup_hash(event),
        })

    return await _bulk_insert(rows)


async def _insert_gkg_threats(
    threats: list[dict],
    service: GDELTService,
) -> dict:
    """Build and insert signal rows from GKG threat records.

    Returns:
        Dict with 'inserted', 'skipped', 'total' counts.
    """
    weight = SIGNAL_WEIGHTS.get("gdelt_gkg_threat", 0.15)
    rows: list[dict] = []

    for event in threats:
        lat = event["latitude"]
        lon = event["longitude"]
        date_str = event.get("DATE", "")
        try:
            occurred_at = datetime.strptime(date_str[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        rows.append({
            "source": "gdelt",
            "signal_type": "gdelt_gkg_threat",
            "h3_index_5": h3.geo_to_h3(lat, lon, 5),
            "h3_index_7": h3.geo_to_h3(lat, lon, 7),
            "h3_index_9": h3.geo_to_h3(lat, lon, 9),
            "latitude": lat,
            "longitude": lon,
            "occurred_at": occurred_at,
            "weight": weight,
            "raw_payload": orjson.dumps(event).decode(),
            "source_id": event.get("GKGRecordID", ""),
            "dedup_hash": service.build_gkg_dedup_hash(event),
        })

    return await _bulk_insert(rows)


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


def _set_redis_key(key: str, value: str) -> None:
    """Set a Redis key for tracking last-ingested file URL."""
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        client.set(key, value)
    finally:
        client.close()
