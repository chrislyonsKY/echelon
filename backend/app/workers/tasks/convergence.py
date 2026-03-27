"""
Convergence score recomputation task. Runs every 15 minutes.

Queries all signals within the scoring window (72h), groups by H3 cell,
computes raw convergence scores with recency decay, normalizes against
rolling baselines, and upserts results into h3_convergence_scores.
"""
import asyncio
import logging
import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.convergence_scorer import (
    LOW_CONFIDENCE_THRESHOLD,
    SCORE_WINDOW_HOURS,
    SIGMA_FLOOR,
    SIGNAL_WEIGHTS,
    compute_raw_score,
    compute_z_score,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# H3 column name per resolution
_H3_COL = {5: "h3_index_5", 7: "h3_index_7", 9: "h3_index_9"}

# Query active signals within the scoring window, grouped by H3 cell
_SIGNALS_BY_CELL_SQL = """
    SELECT {h3_col} AS h3_index, signal_type, occurred_at, weight
    FROM signals
    WHERE occurred_at >= :cutoff
    ORDER BY {h3_col}
"""

_UPSERT_SCORE_SQL = text("""
    INSERT INTO h3_convergence_scores (h3_index, resolution, z_score, raw_score, signal_breakdown, low_confidence, computed_at)
    VALUES (:h3_index, :resolution, :z_score, :raw_score, CAST(:signal_breakdown AS jsonb), :low_confidence, NOW())
    ON CONFLICT (h3_index, resolution)
    DO UPDATE SET
        z_score = EXCLUDED.z_score,
        raw_score = EXCLUDED.raw_score,
        signal_breakdown = EXCLUDED.signal_breakdown,
        low_confidence = EXCLUDED.low_confidence,
        computed_at = EXCLUDED.computed_at
""")

_GET_BASELINE_SQL = text("""
    SELECT mu, sigma, observation_count
    FROM h3_cell_baseline
    WHERE h3_index = :h3_index AND resolution = :resolution AND signal_source = :signal_source
""")

_UPSERT_BASELINE_SQL = text("""
    INSERT INTO h3_cell_baseline (h3_index, resolution, signal_source, mu, sigma, observation_count, last_computed, low_confidence)
    VALUES (:h3_index, :resolution, :signal_source, :mu, :sigma, :count, NOW(), :low_confidence)
    ON CONFLICT (h3_index, resolution, signal_source)
    DO UPDATE SET
        mu = EXCLUDED.mu,
        sigma = EXCLUDED.sigma,
        observation_count = EXCLUDED.observation_count,
        last_computed = EXCLUDED.last_computed,
        low_confidence = EXCLUDED.low_confidence
""")


@celery_app.task(
    name="app.workers.tasks.convergence.recompute_all",
    bind=True,
    max_retries=1,
    acks_late=True,
)
def recompute_all(self) -> dict:
    """Recompute Z-score convergence scores for all active H3 cells at all three resolutions.

    Returns:
        Dict with cell counts per resolution.
    """
    try:
        return asyncio.run(_recompute())
    except Exception as exc:
        logger.exception("Convergence recomputation failed")
        raise self.retry(exc=exc)


async def _recompute() -> dict:
    """Async implementation of convergence score recomputation."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=SCORE_WINDOW_HOURS)
    results: dict[str, int] = {}

    try:
        for resolution, h3_col in _H3_COL.items():
            cell_count = await _recompute_resolution(
                session_factory, resolution, h3_col, cutoff, now,
            )
            results[f"res_{resolution}"] = cell_count
            logger.info("Convergence res %d: scored %d cells", resolution, cell_count)
    finally:
        await engine.dispose()

    logger.info("Convergence recomputation complete: %s", results)
    return results


async def _recompute_resolution(
    session_factory: async_sessionmaker[AsyncSession],
    resolution: int,
    h3_col: str,
    cutoff: datetime,
    now: datetime,
) -> int:
    """Recompute scores for a single H3 resolution.

    Args:
        session_factory: Async session factory.
        resolution: H3 resolution (5, 7, or 9).
        h3_col: Column name for this resolution (e.g. 'h3_index_5').
        cutoff: Earliest signal timestamp to include.
        now: Reference time for recency decay.

    Returns:
        Number of cells scored.
    """
    # Fetch all recent signals grouped by cell
    async with session_factory() as session:
        query = text(_SIGNALS_BY_CELL_SQL.format(h3_col=h3_col))
        result = await session.execute(query, {"cutoff": cutoff})
        rows = result.fetchall()

    if not rows:
        return 0

    # Group signals by H3 cell
    cells: dict[str, list[dict]] = {}
    for row in rows:
        h3_index, signal_type, occurred_at, weight = row
        cells.setdefault(h3_index, []).append({
            "signal_type": signal_type,
            "occurred_at": occurred_at,
            "weight": weight,
        })

    # Score each cell
    score_rows: list[dict] = []
    baseline_updates: list[dict] = []

    for h3_index, signals in cells.items():
        raw_score = compute_raw_score(signals, reference_time=now)

        # Compute per-source breakdown
        source_scores: dict[str, float] = {}
        for sig in signals:
            st = sig["signal_type"]
            source_scores.setdefault(st, 0.0)
            w = SIGNAL_WEIGHTS.get(st, 0.0)
            occurred = sig["occurred_at"]
            if occurred.tzinfo is None:
                occurred = occurred.replace(tzinfo=UTC)
            age_h = (now - occurred).total_seconds() / 3600.0
            from app.services.convergence_scorer import recency_factor
            source_scores[st] += w * recency_factor(age_h)

        # Look up or initialize baseline
        async with session_factory() as session:
            bl_result = await session.execute(_GET_BASELINE_SQL, {
                "h3_index": h3_index,
                "resolution": resolution,
                "signal_source": "convergence",
            })
            baseline = bl_result.fetchone()

        if baseline:
            mu, sigma, obs_count = baseline
            # Incremental baseline update (exponential moving average)
            new_count = obs_count + 1
            new_mu = mu + (raw_score - mu) / new_count
            new_sigma = math.sqrt(
                (sigma ** 2 * (obs_count - 1) + (raw_score - mu) * (raw_score - new_mu))
                / max(new_count - 1, 1)
            ) if new_count > 1 else 0.0
        else:
            # Cold start — no baseline yet
            mu, sigma, obs_count = 0.0, 0.0, 0
            new_count = 1
            new_mu = raw_score
            new_sigma = 0.0

        low_confidence = new_count < LOW_CONFIDENCE_THRESHOLD
        z_score = compute_z_score(raw_score, mu, sigma)

        score_rows.append({
            "h3_index": h3_index,
            "resolution": resolution,
            "z_score": z_score,
            "raw_score": raw_score,
            "signal_breakdown": __import__("orjson").dumps(
                {k: round(v, 4) for k, v in source_scores.items()}
            ).decode(),
            "low_confidence": low_confidence,
        })

        baseline_updates.append({
            "h3_index": h3_index,
            "resolution": resolution,
            "signal_source": "convergence",
            "mu": new_mu,
            "sigma": new_sigma,
            "count": new_count,
            "low_confidence": low_confidence,
        })

    # Batch upsert scores and baselines
    async with session_factory() as session:
        for row in score_rows:
            await session.execute(_UPSERT_SCORE_SQL, row)
        for row in baseline_updates:
            await session.execute(_UPSERT_BASELINE_SQL, row)
        await session.commit()

    return len(score_rows)
