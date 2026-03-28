"""
Event clustering task. Runs every 15 minutes after convergence scoring.

Groups spatiotemporally proximate signals into analyst-facing events
with corroboration metrics and confirmation status.
"""
import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.event_clusterer import cluster_signals
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.tasks.clustering.cluster_events",
    bind=True,
    max_retries=1,
    acks_late=True,
)
def cluster_events(self) -> dict:
    """Cluster recent signals into events.

    Idempotent — safe to re-run. Existing events are updated, not duplicated.

    Returns:
        Dict with count of events created/updated.
    """
    try:
        return asyncio.run(_cluster())
    except Exception as exc:
        logger.exception("Event clustering failed")
        raise self.retry(exc=exc)


async def _cluster() -> dict:
    """Async implementation of event clustering."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    try:
        async with session_factory() as session:
            count = await cluster_signals(session)
    finally:
        await engine.dispose()

    return {"events_upserted": count}
