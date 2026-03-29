"""
AISStream real-time AIS vessel position ingestion task.

Connects to the AISStream.io WebSocket API, listens for position reports
in known conflict zones for 60 seconds, and stores them as convergence signals.
Signal type: ais_position.

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
from app.services.aisstream import AISStreamService
from app.services.convergence_scorer import SIGNAL_WEIGHTS
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
REDIS_LAST_RUN_KEY = "echelon:ingest:aisstream:last_run"

# Pre-defined conflict zone bounding boxes (west, south, east, north)
# Maritime-focused regions where vessel tracking is analytically meaningful
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
    name="app.workers.tasks.ingest_aisstream.run",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def run(self) -> dict:
    """Collect real-time AIS position reports from conflict zone waters.

    Connects to AISStream WebSocket for 60 seconds, collects vessel
    positions, and inserts them as convergence signals.

    Returns:
        Dict with inserted/skipped counts and total positions collected.
    """
    if not settings.aisstream_api_key:
        logger.info("AISStream: no API key configured, skipping ingestion")
        return {"skipped": "no_api_key"}

    try:
        return asyncio.run(_ingest())
    except Exception as exc:
        logger.exception("AISStream ingestion failed")
        raise self.retry(exc=exc)


async def _ingest() -> dict:
    """Async implementation of the AISStream ingestion pipeline."""
    service = AISStreamService()
    weight = SIGNAL_WEIGHTS.get("ais_position", 0.08)

    # Collect all conflict zone bboxes into a single subscription
    all_bboxes = [zone["bbox"] for zone in CONFLICT_ZONES]

    positions = await service.collect_positions(all_bboxes, duration_seconds=60)

    if not positions:
        logger.info("AISStream: no positions collected")
        _set_redis_last_run(datetime.now(timezone.utc).isoformat())
        return {"inserted": 0, "skipped": 0, "total": 0}

    # Build signal rows
    rows: list[dict] = []
    for pos in positions:
        lat = pos["latitude"]
        lon = pos["longitude"]
        occurred_at = pos["timestamp"]

        if not isinstance(occurred_at, datetime):
            occurred_at = datetime.now(timezone.utc)

        rows.append({
            "source": "aisstream",
            "signal_type": "ais_position",
            "h3_index_5": h3.geo_to_h3(lat, lon, 5),
            "h3_index_7": h3.geo_to_h3(lat, lon, 7),
            "h3_index_9": h3.geo_to_h3(lat, lon, 9),
            "latitude": lat,
            "longitude": lon,
            "occurred_at": occurred_at,
            "weight": weight,
            "raw_payload": orjson.dumps({
                "mmsi": pos["mmsi"],
                "ship_name": pos["ship_name"],
                "speed": pos["speed"],
                "course": pos["course"],
                "heading": pos["heading"],
            }).decode(),
            "source_id": str(pos["mmsi"]),
            "dedup_hash": service.build_dedup_hash(pos),
            "provenance_family": "crowd_sourced",
            "confirmation_policy": "unverified",
        })

    # Bulk insert with deduplication
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

    logger.info(
        "AISStream ingestion complete: %d inserted, %d skipped, %d total positions",
        inserted, skipped, len(positions),
    )
    _set_redis_last_run(datetime.now(timezone.utc).isoformat())
    return {"inserted": inserted, "skipped": skipped, "total": len(positions)}


def _set_redis_last_run(value: str) -> None:
    """Record successful task execution for source-health telemetry."""
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        client.set(REDIS_LAST_RUN_KEY, value)
    finally:
        client.close()
