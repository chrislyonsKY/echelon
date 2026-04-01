"""
Sentinel-2 EO scene ingestion and change detection tasks.

Two-stage pipeline:
  1. trigger_scene_jobs (daily) — for each active AOI, searches STAC for
     recent + baseline scenes and queues process_scene tasks.
  2. process_scene (on demand) — downloads band windows from COGs,
     computes NBR delta, creates signal records if anomaly detected.

Heavy CPU tasks — always runs in Celery worker, never FastAPI.
Uses windowed COG reads — never loads full Sentinel-2 scenes into memory.
"""
import hashlib
import logging
from datetime import date, datetime, timedelta, timezone

import h3
import orjson
import redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.convergence_scorer import SIGNAL_WEIGHTS
from app.services.stac import STACService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
REDIS_LAST_RUN_KEY = "echelon:ingest:sentinel2:last_run"

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
    name="app.workers.tasks.ingest_sentinel2.trigger_scene_jobs",
    bind=True,
    max_retries=2,
    soft_time_limit=120,
    time_limit=180,
    acks_late=True,
)
def trigger_scene_jobs(self) -> dict:
    """For each active AOI, search STAC for scene pairs and queue processing tasks.

    Returns:
        Dict with 'aois_checked' and 'tasks_queued' counts.
    """
    if not settings.enable_eo_change_detection:
        return {"aois_checked": 0, "tasks_queued": 0, "skipped": "EO disabled"}

    import asyncio
    try:
        return asyncio.run(_trigger_jobs())
    except Exception as exc:
        logger.exception("Sentinel-2 trigger failed")
        raise self.retry(exc=exc)


async def _trigger_jobs() -> dict:
    """Search STAC for each AOI and queue scene processing tasks."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    stac = STACService()

    aois_checked = 0
    tasks_queued = 0

    try:
        # Fetch AOIs with their geometry bboxes
        async with session_factory() as session:
            result = await session.execute(text("""
                SELECT id, name,
                       ST_XMin(geometry::geometry) as west,
                       ST_YMin(geometry::geometry) as south,
                       ST_XMax(geometry::geometry) as east,
                       ST_YMax(geometry::geometry) as north
                FROM aois
            """))
            aois = result.fetchall()

        if not aois:
            logger.info("Sentinel-2: no AOIs to process")
            _set_redis_last_run(datetime.now(timezone.utc).isoformat())
            return {"aois_checked": 0, "tasks_queued": 0}

        today = date.today()
        week_ago = today - timedelta(days=7)

        for aoi in aois:
            aois_checked += 1
            bbox = (aoi.west, aoi.south, aoi.east, aoi.north)

            # Search for recent scenes (past 7 days, cloud < 20%)
            current_scenes = stac.search_scenes(
                bbox=bbox, date_from=week_ago, date_to=today,
                cloud_cover_max=20.0, max_items=3,
            )

            if not current_scenes:
                logger.info("Sentinel-2: no recent scenes for AOI '%s'", aoi.name)
                continue

            # Search for baseline scenes (same week, 12 months prior)
            baseline_from = week_ago - timedelta(days=365)
            baseline_to = today - timedelta(days=365)
            baseline_scenes = stac.search_scenes(
                bbox=bbox, date_from=baseline_from, date_to=baseline_to,
                cloud_cover_max=20.0, max_items=3,
            )

            if not baseline_scenes:
                logger.info("Sentinel-2: no baseline scenes for AOI '%s'", aoi.name)
                continue

            # Queue a process task for the best scene pair
            process_scene.delay(
                aoi_id=str(aoi.id),
                current_scene=current_scenes[0],
                baseline_scene=baseline_scenes[0],
                bbox=list(bbox),
            )
            tasks_queued += 1
            logger.info("Sentinel-2: queued scene pair for AOI '%s'", aoi.name)

    finally:
        await engine.dispose()

    _set_redis_last_run(datetime.now(timezone.utc).isoformat())
    return {"aois_checked": aois_checked, "tasks_queued": tasks_queued}


@celery_app.task(
    name="app.workers.tasks.ingest_sentinel2.process_scene",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
    soft_time_limit=300,
    time_limit=600,
    acks_late=True,
)
def process_scene(
    self,
    aoi_id: str,
    current_scene: dict,
    baseline_scene: dict,
    bbox: list[float],
) -> dict:
    """Compute NBR delta for a scene pair and create signal records if anomaly detected.

    Heavy CPU task — always runs in Celery worker, never FastAPI.
    Uses windowed COG reads — never loads full Sentinel-2 scenes into memory.

    Args:
        aoi_id: AOI UUID.
        current_scene: Current period STAC item dict.
        baseline_scene: Prior year STAC item dict.
        bbox: [west, south, east, north].

    Returns:
        Dict with computation results.
    """
    try:
        stac = STACService()
        bbox_tuple = (bbox[0], bbox[1], bbox[2], bbox[3])

        result = stac.compute_nbr_delta(current_scene, baseline_scene, bbox_tuple)

        if result is None:
            return {"status": "failed", "reason": "computation_error"}

        if not result["is_anomaly"]:
            return {
                "status": "no_anomaly",
                "mean_delta": result["mean_delta"],
                "max_delta": result["max_delta"],
            }

        # Anomaly detected — create signal records
        import asyncio
        count = asyncio.run(_create_anomaly_signals(
            aoi_id=aoi_id,
            bbox_tuple=bbox_tuple,
            current_scene=current_scene,
            result=result,
        ))

        return {
            "status": "anomaly_detected",
            "signals_created": count,
            "mean_delta": result["mean_delta"],
            "max_delta": result["max_delta"],
            "anomaly_fraction": result["anomaly_fraction"],
        }

    except Exception as exc:
        logger.exception("Sentinel-2 scene processing failed for AOI %s", aoi_id)
        raise self.retry(exc=exc)


async def _create_anomaly_signals(
    aoi_id: str,
    bbox_tuple: tuple[float, float, float, float],
    current_scene: dict,
    result: dict,
) -> int:
    """Create sentinel2_nbr_anomaly signal records for the AOI centroid.

    Args:
        aoi_id: AOI UUID.
        bbox_tuple: (west, south, east, north).
        current_scene: Scene metadata.
        result: NBR computation result.

    Returns:
        Number of signals inserted.
    """
    weight = SIGNAL_WEIGHTS.get("sentinel2_nbr_anomaly", 0.25)
    west, south, east, north = bbox_tuple

    # Use AOI centroid as the signal location
    lat = (south + north) / 2
    lon = (west + east) / 2

    scene_date_str = current_scene.get("datetime", "")
    try:
        occurred_at = datetime.fromisoformat(scene_date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        occurred_at = datetime.now(timezone.utc)

    dedup_key = f"sentinel2:{current_scene.get('id', '')}:{aoi_id}"
    dedup_hash = hashlib.sha256(dedup_key.encode()).hexdigest()

    row = {
        "source": "sentinel2",
        "signal_type": "sentinel2_nbr_anomaly",
        "h3_index_5": h3.geo_to_h3(lat, lon, 5),
        "h3_index_7": h3.geo_to_h3(lat, lon, 7),
        "h3_index_9": h3.geo_to_h3(lat, lon, 9),
        "latitude": lat,
        "longitude": lon,
        "occurred_at": occurred_at,
        "weight": weight,
        "raw_payload": orjson.dumps({
            "scene_id": current_scene.get("id"),
            "mean_delta_nbr": round(result["mean_delta"], 4),
            "max_delta_nbr": round(result["max_delta"], 4),
            "anomaly_fraction": round(result["anomaly_fraction"], 4),
            "anomaly_pixels": result["anomaly_pixels"],
            "total_pixels": result["total_pixels"],
            "aoi_id": aoi_id,
        }).decode(),
        "source_id": current_scene.get("id", ""),
        "dedup_hash": dedup_hash,
        "provenance_family": "official_sensor",
        "confirmation_policy": "verified",
    }

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    inserted = 0
    try:
        async with session_factory() as session:
            r = await session.execute(_INSERT_SIGNAL_SQL, row)
            if r.rowcount > 0:
                inserted = 1
            await session.commit()
    finally:
        await engine.dispose()

    return inserted


def _set_redis_last_run(value: str) -> None:
    """Record successful task execution for source-health telemetry."""
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        client.set(REDIS_LAST_RUN_KEY, value)
    finally:
        client.close()
