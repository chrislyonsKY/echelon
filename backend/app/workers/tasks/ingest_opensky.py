"""
OpenSky Network military aircraft ingestion task.

Polls OpenSky /states/all for airborne military aircraft across known
conflict zone bounding boxes. Filters for likely military traffic using
callsign patterns and ICAO24 hex ranges, then inserts as signals at
H3 resolutions 5, 7, and 9.

Rate limit: 10s sleep between bbox queries (anonymous: 10 req / 10s).
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
from app.services.opensky import OpenSkyService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

REDIS_LAST_RUN_KEY = "echelon:ingest:opensky:last_run"

# Pre-defined conflict zone bounding boxes (west, south, east, north)
# Aligned with ingest_osm.py conflict zones + Taiwan Strait
CONFLICT_ZONES: list[dict] = [
    {"name": "Ukraine", "bbox": (22.0, 44.0, 40.5, 52.5)},
    {"name": "Eastern Mediterranean", "bbox": (34.0, 29.0, 37.0, 34.0)},
    {"name": "Yemen/Horn of Africa", "bbox": (41.0, 10.0, 54.0, 19.0)},
    {"name": "Persian Gulf", "bbox": (47.0, 23.0, 57.0, 30.5)},
    {"name": "South China Sea", "bbox": (105.0, 5.0, 122.0, 22.0)},
    {"name": "Korean Peninsula", "bbox": (124.0, 33.0, 132.0, 43.0)},
    {"name": "Taiwan Strait", "bbox": (117.0, 21.5, 123.0, 26.0)},
]

_INSERT_SIGNAL_SQL = text("""
    INSERT INTO signals (
        source, signal_type, h3_index_5, h3_index_7, h3_index_9,
        location, occurred_at, ingested_at, weight,
        raw_payload, source_id, dedup_hash,
        provenance_family, confirmation_policy
    ) VALUES (
        :source, :signal_type, :h3_index_5, :h3_index_7, :h3_index_9,
        ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326),
        :occurred_at, NOW(), :weight,
        CAST(:raw_payload AS jsonb), :source_id, :dedup_hash,
        :provenance_family, :confirmation_policy
    )
    ON CONFLICT (dedup_hash) DO NOTHING
""")


@celery_app.task(
    name="app.workers.tasks.ingest_opensky.run",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=120,
    time_limit=180,
    acks_late=True,
)
def run(self) -> dict:
    """Poll OpenSky for military aircraft across conflict zones.

    Returns:
        Dict with per-zone and total insertion counts.
    """
    try:
        return asyncio.run(_ingest())
    except Exception as exc:
        logger.exception("OpenSky ingestion failed")
        raise self.retry(exc=exc)


async def _ingest() -> dict:
    """Async implementation of the OpenSky military aircraft ingestion pipeline."""
    service = OpenSkyService()
    weight = SIGNAL_WEIGHTS.get("opensky_military", 0.20)
    now = datetime.now(timezone.utc)

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    total_inserted = 0
    total_skipped = 0
    zone_results: dict[str, dict] = {}

    try:
        for zone in CONFLICT_ZONES:
            zone_name = zone["name"]
            bbox = zone["bbox"]

            try:
                aircraft = await service.fetch_military_aircraft(bbox)
            except Exception:
                logger.warning(
                    "OpenSky query failed for %s, skipping",
                    zone_name,
                    exc_info=True,
                )
                zone_results[zone_name] = {"error": "query_failed"}
                # Still sleep to respect rate limits even on failure
                await asyncio.sleep(10)
                continue

            if not aircraft:
                zone_results[zone_name] = {"inserted": 0, "skipped": 0, "total": 0}
                await asyncio.sleep(10)
                continue

            # Build signal rows
            rows: list[dict] = []
            for ac in aircraft:
                lat = ac["latitude"]
                lon = ac["longitude"]

                rows.append({
                    "source": "opensky",
                    "signal_type": "opensky_military",
                    "h3_index_5": h3.geo_to_h3(lat, lon, 5),
                    "h3_index_7": h3.geo_to_h3(lat, lon, 7),
                    "h3_index_9": h3.geo_to_h3(lat, lon, 9),
                    "latitude": lat,
                    "longitude": lon,
                    "occurred_at": now,
                    "weight": weight,
                    "raw_payload": orjson.dumps({
                        "icao24": ac["icao24"],
                        "callsign": ac["callsign"],
                        "origin_country": ac["origin_country"],
                        "velocity": ac["velocity"],
                        "heading": ac["heading"],
                        "altitude": ac["baro_altitude"],
                    }).decode(),
                    "source_id": ac["icao24"],
                    "dedup_hash": service.build_dedup_hash(ac),
                    "provenance_family": "official_sensor",
                    "confirmation_policy": "verified",
                })

            # Bulk insert with deduplication
            inserted = 0
            skipped = 0
            async with session_factory() as session:
                for row in rows:
                    result = await session.execute(_INSERT_SIGNAL_SQL, row)
                    if result.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                await session.commit()

            total_inserted += inserted
            total_skipped += skipped
            zone_results[zone_name] = {
                "inserted": inserted,
                "skipped": skipped,
                "total": len(aircraft),
            }
            logger.info(
                "OpenSky %s: %d inserted, %d skipped, %d total",
                zone_name, inserted, skipped, len(aircraft),
            )

            # Rate limit: 10s between bbox queries (OpenSky anonymous limit)
            await asyncio.sleep(10)

    finally:
        await service.close()
        await engine.dispose()

    # Record last run timestamp in Redis
    _set_redis_last_run(now.isoformat())

    logger.info(
        "OpenSky ingestion complete: %d inserted, %d skipped",
        total_inserted, total_skipped,
    )
    return {
        "total_inserted": total_inserted,
        "total_skipped": total_skipped,
        "zones": zone_results,
    }


def _set_redis_last_run(value: str) -> None:
    """Record the last successful run timestamp in Redis."""
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        client.set(REDIS_LAST_RUN_KEY, value)
    finally:
        client.close()
