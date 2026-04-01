"""
NASA FIRMS thermal anomaly ingestion task.

Fetches active fire / thermal anomaly detections from VIIRS SNPP via the
FIRMS CSV API across conflict zone bounding boxes. Each detection is stored
as a signal of type "firms_thermal".

Task is idempotent — safe to retry on failure.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

import h3
import orjson
import redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.convergence_scorer import SIGNAL_WEIGHTS
from app.services.firms import CONFLICT_ZONES, FIRMSService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
REDIS_LAST_RUN_KEY = "echelon:ingest:firms:last_run"

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
    name="app.workers.tasks.ingest_firms.run",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
    soft_time_limit=120,
    time_limit=180,
    acks_late=True,
)
def run(self) -> dict:
    """Fetch and ingest FIRMS thermal anomaly detections.

    Returns:
        Dict with ingestion counts or skip reason.
    """
    if not settings.firms_map_key:
        logger.info("FIRMS: no API key configured — skipping")
        return {"skipped": "no_api_key"}

    try:
        return asyncio.run(_ingest())
    except Exception as exc:
        logger.exception("FIRMS ingestion failed")
        raise self.retry(exc=exc)


async def _ingest() -> dict:
    """Async implementation of the FIRMS ingestion pipeline.

    Iterates over conflict zone bounding boxes with a 5-second sleep
    between each to avoid rate limiting. Each zone is fetched independently
    so a single failure does not block the rest.
    """
    service = FIRMSService(settings.firms_map_key)

    try:
        all_anomalies: list[dict] = []

        for idx, (zone_name, bbox) in enumerate(CONFLICT_ZONES):
            if idx > 0:
                await asyncio.sleep(5)

            try:
                anomalies = await service.fetch_thermal_anomalies(
                    [(zone_name, bbox)], days=2,
                )
                all_anomalies.extend(anomalies)
            except Exception:
                logger.exception("FIRMS: failed zone %s — continuing", zone_name)

        if not all_anomalies:
            logger.info("FIRMS: no anomalies found across all zones")
            _set_redis_last_run(datetime.now(timezone.utc).isoformat())
            return {"inserted": 0, "skipped": 0, "total": 0}

        result = await _insert_anomalies(all_anomalies, service)

    finally:
        await service.close()

    logger.info(
        "FIRMS ingestion complete — %d inserted / %d skipped / %d total",
        result["inserted"], result["skipped"], result["total"],
    )
    _set_redis_last_run(datetime.now(timezone.utc).isoformat())
    return result


async def _insert_anomalies(
    anomalies: list[dict],
    service: FIRMSService,
) -> dict:
    """Build and insert signal rows from FIRMS thermal anomaly detections.

    Args:
        anomalies: List of parsed anomaly dicts from FIRMSService.
        service: FIRMSService instance (for dedup hash computation).

    Returns:
        Dict with 'inserted', 'skipped', 'total' counts.
    """
    weight = SIGNAL_WEIGHTS.get("firms_thermal", 0.22)
    rows: list[dict] = []

    for anomaly in anomalies:
        lat = anomaly["latitude"]
        lon = anomaly["longitude"]
        acq_date = anomaly.get("acq_date", "")
        acq_time = anomaly.get("acq_time", "").zfill(4)  # Ensure HHMM format

        try:
            occurred_at = datetime.strptime(
                f"{acq_date} {acq_time}", "%Y-%m-%d %H%M",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            logger.debug("FIRMS: skipping row with bad date %s %s", acq_date, acq_time)
            continue

        source_id = f"{lat},{lon},{acq_date},{acq_time}"

        rows.append({
            "source": "firms",
            "signal_type": "firms_thermal",
            "h3_index_5": h3.geo_to_h3(lat, lon, 5),
            "h3_index_7": h3.geo_to_h3(lat, lon, 7),
            "h3_index_9": h3.geo_to_h3(lat, lon, 9),
            "latitude": lat,
            "longitude": lon,
            "occurred_at": occurred_at,
            "weight": weight,
            "raw_payload": orjson.dumps({
                "brightness": anomaly.get("brightness"),
                "frp": anomaly.get("frp"),
                "confidence": anomaly.get("confidence"),
                "satellite": anomaly.get("satellite"),
                "daynight": anomaly.get("daynight"),
            }).decode(),
            "source_id": source_id,
            "dedup_hash": service.build_dedup_hash(anomaly),
            "provenance_family": "official_sensor",
            "confirmation_policy": "verified",
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


def _set_redis_last_run(value: str) -> None:
    """Record successful task execution for source-health telemetry."""
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        client.set(REDIS_LAST_RUN_KEY, value)
    finally:
        client.close()
