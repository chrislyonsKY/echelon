"""
Maintenance tasks — data retention and cleanup.

Runs daily at 4am UTC via Celery Beat.
Task is idempotent — safe to retry on failure.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_DELETE_OLD_SIGNALS_SQL = text("""
    DELETE FROM signals
    WHERE occurred_at < NOW() - INTERVAL '1 day' * :retention_days
""")

_COUNT_OLD_SIGNALS_SQL = text("""
    SELECT COUNT(*) FROM signals
    WHERE occurred_at < NOW() - INTERVAL '1 day' * :retention_days
""")


@celery_app.task(
    name="app.workers.tasks.maintenance.trim_old_signals",
    bind=True,
    max_retries=1,
    default_retry_delay=3600,
    soft_time_limit=300,
    time_limit=600,
    acks_late=True,
)
def trim_old_signals(self) -> dict:
    """Delete signal records older than the baseline window (default 365 days).

    Preserves h3_cell_baseline statistics — only trims raw signal events.
    The baseline table retains computed μ/σ/obs_count independently.
    """
    try:
        return asyncio.run(_trim())
    except Exception as exc:
        logger.exception("Signal trimming failed")
        raise self.retry(exc=exc)


async def _trim() -> dict:
    """Async implementation of signal trimming."""
    retention_days = settings.convergence_baseline_days  # default 365
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    try:
        async with session_factory() as session:
            # Count first for logging
            count_result = await session.execute(
                _COUNT_OLD_SIGNALS_SQL,
                {"retention_days": retention_days},
            )
            stale_count = count_result.scalar() or 0

            if stale_count == 0:
                logger.info("Maintenance: no signals older than %d days to trim", retention_days)
                return {"deleted": 0, "retention_days": retention_days}

            # Delete in batches to avoid long locks
            total_deleted = 0
            while True:
                result = await session.execute(
                    text("""
                        DELETE FROM signals
                        WHERE id IN (
                            SELECT id FROM signals
                            WHERE occurred_at < NOW() - INTERVAL '1 day' * :retention_days
                            LIMIT 5000
                        )
                    """),
                    {"retention_days": retention_days},
                )
                batch_deleted = result.rowcount
                total_deleted += batch_deleted
                await session.commit()

                if batch_deleted < 5000:
                    break

            logger.info(
                "Maintenance: trimmed %d signals older than %d days",
                total_deleted,
                retention_days,
            )
            return {"deleted": total_deleted, "retention_days": retention_days}
    finally:
        await engine.dispose()
