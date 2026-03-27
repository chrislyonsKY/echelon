"""
GFW vessel anomaly ingestion task.

Fetches AIS gap and loitering events from GlobalFishingWatch.
Runs every 12 hours. ~24h data lag from GFW processing pipeline.
Task is idempotent — safe to retry on failure.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

import h3
import orjson
import redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.convergence_scorer import SIGNAL_WEIGHTS
from app.services.gfw import GFWService, GFW_EVENT_TYPE_MAP
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

REDIS_LAST_RUN_KEY = "echelon:ingest:gfw:last_run"
DEFAULT_LOOKBACK_DAYS = 5

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
    name="app.workers.tasks.ingest_gfw.run",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
)
def run(self) -> dict:
    """Ingest GFW vessel anomaly events (AIS gaps, loitering).

    Returns:
        Dict with 'inserted', 'skipped', and 'total_fetched' counts.
    """
    try:
        return asyncio.run(_ingest())
    except Exception as exc:
        logger.exception("GFW ingestion failed")
        raise self.retry(exc=exc)


async def _ingest() -> dict:
    """Async implementation of the GFW ingestion pipeline."""
    # Determine date window
    redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        last_run_str = redis_client.get(REDIS_LAST_RUN_KEY)
    finally:
        redis_client.close()

    if last_run_str:
        date_from = date.fromisoformat(last_run_str)
    else:
        date_from = date.today() - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    date_to = date.today()

    logger.info("GFW ingestion: fetching events from %s to %s", date_from, date_to)

    service = GFWService()
    try:
        events = await service.fetch_events(date_from=date_from, date_to=date_to)
    finally:
        await service.close()

    if not events:
        logger.info("GFW ingestion: no new events found")
        return {"inserted": 0, "skipped": 0, "total_fetched": 0}

    # Build signal rows
    rows = _build_signal_rows(events, service)
    total_fetched = len(events)

    # Bulk insert
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

    # Update last-run marker
    redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        redis_client.set(REDIS_LAST_RUN_KEY, date_to.isoformat())
    finally:
        redis_client.close()

    logger.info(
        "GFW ingestion complete: %d inserted, %d skipped, %d total fetched",
        inserted, skipped, total_fetched,
    )
    return {"inserted": inserted, "skipped": skipped, "total_fetched": total_fetched}


def _build_signal_rows(
    events: list[dict],
    service: GFWService,
) -> list[dict]:
    """Transform GFW events into signal table rows.

    Args:
        events: Raw GFW event dicts.
        service: GFWService instance (for dedup hash).

    Returns:
        List of dicts ready for parameterized INSERT.
    """
    rows: list[dict] = []

    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue

        # Extract position
        position = event.get("position", {})
        lat = position.get("lat")
        lon = position.get("lon")
        if lat is None or lon is None:
            continue

        # Map event type
        echelon_type = event.get("_echelon_event_type", event.get("type", ""))
        signal_type = GFW_EVENT_TYPE_MAP.get(echelon_type, "gfw_loitering")
        weight = SIGNAL_WEIGHTS.get(signal_type, 0.10)

        # Parse start timestamp
        start_str = event.get("start", "")
        try:
            occurred_at = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        # Compute H3 indexes
        h3_5 = h3.geo_to_h3(lat, lon, 5)
        h3_7 = h3.geo_to_h3(lat, lon, 7)
        h3_9 = h3.geo_to_h3(lat, lon, 9)

        # Build payload (strip _echelon_event_type)
        payload = {k: v for k, v in event.items() if k != "_echelon_event_type"}

        rows.append({
            "source": "gfw",
            "signal_type": signal_type,
            "h3_index_5": h3_5,
            "h3_index_7": h3_7,
            "h3_index_9": h3_9,
            "latitude": lat,
            "longitude": lon,
            "occurred_at": occurred_at,
            "weight": weight,
            "raw_payload": orjson.dumps(payload, default=str).decode(),
            "source_id": str(event_id),
            "dedup_hash": service.build_dedup_hash(event),
        })

    return rows
