"""Maintenance tasks — data retention, cleanup."""
import logging
from app.workers.celery_app import celery_app
logger = logging.getLogger(__name__)

@celery_app.task(name="app.workers.tasks.maintenance.trim_old_signals", bind=True, max_retries=1, acks_late=True)
def trim_old_signals(self) -> dict:
    """Delete signal records older than CONVERGENCE_BASELINE_DAYS (365 days).

    Preserves h3_cell_baseline statistics — only trims raw signal events.
    """
    # TODO: DELETE FROM signals WHERE occurred_at < NOW() - INTERVAL '365 days'
    raise NotImplementedError

@celery_app.task(name="app.workers.tasks.maintenance.bootstrap_baseline", bind=True, max_retries=1, acks_late=True)
def bootstrap_baseline(self) -> dict:
    """One-time task: backfill 365 days of ACLED history to seed Z-score baseline.

    Run manually on first deployment:
      docker compose exec worker python -m app.workers.tasks.bootstrap_baseline
    """
    # TODO: iterate month-by-month for past 365 days, fetch ACLED, insert, compute baseline stats
    raise NotImplementedError
