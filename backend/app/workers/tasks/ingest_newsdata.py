"""
News ingestion task.

Pulls conflict articles from three sources (NewsData, NewsAPI, GNews),
geocodes them, and stores as signals for convergence scoring + UI sidebar.
Runs every 4 hours. Task is idempotent — safe to retry on failure.
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
from app.services.language_support import build_multilingual_text_fields
from app.services.newsdata import NewsService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

REDIS_LAST_RUN_KEY = "echelon:ingest:newsdata:last_run"

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
    name="app.workers.tasks.ingest_newsdata.run",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    soft_time_limit=120,
    time_limit=180,
    acks_late=True,
)
def run(self) -> dict:
    """Fetch conflict news from NewsData + NewsAPI + GNews.

    Returns:
        Dict with 'inserted', 'skipped', and 'total_fetched' counts.
    """
    try:
        return asyncio.run(_ingest())
    except Exception as exc:
        logger.exception("News ingestion failed")
        raise self.retry(exc=exc)


async def _ingest() -> dict:
    """Async implementation of the multi-source news ingestion pipeline."""
    service = NewsService()
    try:
        articles = await service.fetch_all_sources()
    finally:
        await service.close()

    if not articles:
        logger.info("News ingestion: no articles found")
        return {"inserted": 0, "skipped": 0, "total_fetched": 0}

    weight = SIGNAL_WEIGHTS.get("newsdata_article", 0.12)
    rows: list[dict] = []

    for article in articles:
        lat = article["latitude"]
        lon = article["longitude"]
        text_fields = build_multilingual_text_fields(
            title=article.get("title"),
            description=article.get("description"),
            language_hint=article.get("language"),
        )

        # Parse pubDate (various formats across providers)
        pub_date = article.get("pubDate", "")
        occurred_at = _parse_date(pub_date)

        rows.append({
            "source": "newsdata",
            "signal_type": "newsdata_article",
            "h3_index_5": h3.geo_to_h3(lat, lon, 5),
            "h3_index_7": h3.geo_to_h3(lat, lon, 7),
            "h3_index_9": h3.geo_to_h3(lat, lon, 9),
            "latitude": lat,
            "longitude": lon,
            "occurred_at": occurred_at,
            "weight": weight,
            "raw_payload": orjson.dumps({
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "url": article.get("url", ""),
                "source": article.get("source_name", ""),
                "provider": article.get("provider", ""),
                **text_fields.as_dict(),
            }).decode(),
            "source_id": article.get("article_id", ""),
            "dedup_hash": service.build_dedup_hash(article),
            "provenance_family": "news_media",
            "confirmation_policy": "unverified",
        })

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
        redis_client.set(REDIS_LAST_RUN_KEY, datetime.now(timezone.utc).isoformat())
    finally:
        redis_client.close()

    logger.info(
        "News ingestion complete: %d inserted, %d skipped, %d total",
        inserted, skipped, len(articles),
    )
    return {"inserted": inserted, "skipped": skipped, "total_fetched": len(articles)}


def _parse_date(date_str: str) -> datetime:
    """Parse date string from various news API formats.

    Args:
        date_str: Date string (ISO 8601, or 'YYYY-MM-DD HH:MM:SS').

    Returns:
        Timezone-aware datetime, defaults to now if unparseable.
    """
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            continue
    return datetime.now(timezone.utc)
