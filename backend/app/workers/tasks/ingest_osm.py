"""
OSM military-tag change ingestion task.

Queries the ohsome full-history API for recent military-tag changes in known
conflict zones. New changes are stored as signals; repeated task runs are
deduplicated by OSM element id plus change timestamp.

Task is idempotent and safe to retry on failure.
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
from app.services.ohsome import OhsomeService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Pre-defined conflict zone bounding boxes (west, south, east, north)
# Focused on regions where infrastructure monitoring is analytically meaningful
CONFLICT_ZONES: list[dict] = [
    {"name": "Ukraine", "bbox": (22.0, 44.0, 40.5, 52.5)},
    {"name": "Eastern Mediterranean", "bbox": (34.0, 29.0, 37.0, 34.0)},
    {"name": "Yemen/Horn of Africa", "bbox": (41.0, 10.0, 54.0, 19.0)},
    {"name": "Persian Gulf", "bbox": (47.0, 23.0, 57.0, 30.5)},
    {"name": "South China Sea", "bbox": (105.0, 5.0, 122.0, 22.0)},
    {"name": "Korean Peninsula", "bbox": (124.0, 33.0, 132.0, 43.0)},
    {"name": "Sahel", "bbox": (-5.0, 10.0, 16.0, 25.0)},
    {"name": "Myanmar", "bbox": (92.0, 9.5, 101.5, 28.5)},
    {"name": "Taiwan Strait", "bbox": (117.0, 21.5, 123.0, 26.0)},
    {"name": "Libya", "bbox": (9.0, 19.0, 25.5, 34.0)},
]

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
    name="app.workers.tasks.ingest_osm.run",
    bind=True,
    max_retries=2,
    default_retry_delay=3600,
    acks_late=True,
)
def run(self) -> dict:
    """Query ohsome for recent military-tag changes in conflict zones.

    Returns:
        Dict with per-zone and total counts.
    """
    try:
        return asyncio.run(_ingest())
    except Exception as exc:
        logger.exception("OSM ingestion failed")
        raise self.retry(exc=exc)


async def _ingest() -> dict:
    """Async implementation of the OSM ingestion pipeline."""
    service = OhsomeService()
    weight = SIGNAL_WEIGHTS.get("osm_change", 0.08)

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
                elements = await service.query_military_changes(bbox)
            except Exception:
                logger.warning("ohsome query failed for %s, skipping", zone_name, exc_info=True)
                zone_results[zone_name] = {"error": "query_failed"}
                continue

            if not elements:
                zone_results[zone_name] = {"inserted": 0, "skipped": 0, "total": 0}
                await asyncio.sleep(2)
                continue

            # Build signal rows
            rows: list[dict] = []
            for el in elements:
                lat = el["latitude"]
                lon = el["longitude"]
                occurred_at = _parse_occurred_at(el.get("change_timestamp"))
                osm_ref = str(el.get("osm_ref") or f"{el['osm_type']}/{el['osm_id']}")

                rows.append({
                    "source": "osm",
                    "signal_type": "osm_change",
                    "h3_index_5": h3.geo_to_h3(lat, lon, 5),
                    "h3_index_7": h3.geo_to_h3(lat, lon, 7),
                    "h3_index_9": h3.geo_to_h3(lat, lon, 9),
                    "latitude": lat,
                    "longitude": lon,
                    "occurred_at": occurred_at,
                    "weight": weight,
                    "raw_payload": orjson.dumps({
                        "osm_type": el["osm_type"],
                        "osm_id": el["osm_id"],
                        "osm_ref": el.get("osm_ref", ""),
                        "name": el["name"],
                        "infra_type": el["infra_type"],
                        "change_type": el.get("change_type", ""),
                        "change_timestamp": el.get("change_timestamp", ""),
                        "valid_from": el.get("valid_from", ""),
                        "valid_to": el.get("valid_to", ""),
                        "versions_count": el.get("versions_count", 0),
                        "tags": el["tags"],
                    }).decode(),
                    "source_id": f"{osm_ref}@{el.get('change_timestamp', '')}",
                    "dedup_hash": service.build_dedup_hash(el),
                })

            # Bulk insert
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
                "total": len(elements),
            }
            logger.info("OSM %s: %d inserted, %d skipped, %d total", zone_name, inserted, skipped, len(elements))

            await asyncio.sleep(2)

    finally:
        await service.close()
        await engine.dispose()

    logger.info("OSM ingestion complete: %d inserted, %d skipped", total_inserted, total_skipped)
    return {
        "total_inserted": total_inserted,
        "total_skipped": total_skipped,
        "zones": zone_results,
    }


def _parse_occurred_at(value: str | None) -> datetime:
    """Parse an ISO-8601 change timestamp, falling back to now."""
    if not value:
        return datetime.now(timezone.utc)

    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)
