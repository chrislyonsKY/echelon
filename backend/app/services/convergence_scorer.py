"""
Echelon Convergence Scoring Engine

Computes Z-score based convergence scores per H3 cell across all signal types.
This module is called by the recompute_convergence Celery task every 15 minutes.

Design:
    raw_score(cell, t) = Σ weight(signal_type) × recency_factor(age_hours) × deduped_count
    z_score(cell, t)   = (raw_score - μ) / max(σ, SIGMA_FLOOR)

See ai-dev/architecture.md for full formula documentation.
"""
import logging
import math
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# ── Signal weights ────────────────────────────────────────────────────────────
# Defined here as the single source of truth. Frontend advanced slider controls
# send multipliers that are applied on top of these defaults — never override here.
SIGNAL_WEIGHTS: dict[str, float] = {
    "gfw_ais_gap":           0.35,
    "gdelt_conflict":        0.30,
    "sentinel2_nbr_anomaly": 0.25,
    "gdelt_gkg_threat":      0.15,
    "newsdata_article":      0.12,
    "gfw_loitering":         0.10,
    "osm_change":            0.08,
}

# ── Scoring constants ──────────────────────────────────────────────────────────
RECENCY_DECAY_RATE: float = 0.05   # Exponential decay coefficient (per hour)
SIGMA_FLOOR: float = 0.001          # Prevents division by zero in quiet cells
LOW_CONFIDENCE_THRESHOLD: int = 30  # Minimum baseline observations for full confidence
SCORE_WINDOW_HOURS: int = 72        # How far back to look for active signals


def recency_factor(age_hours: float) -> float:
    """Compute the recency weight for a signal of a given age.

    Uses exponential decay: f(t) = exp(-DECAY_RATE × age_hours)
    Half-life ≈ 14 hours. Signal is near-zero weight after ~3 days.

    Args:
        age_hours: Hours since the signal occurred.

    Returns:
        Weight multiplier in (0, 1].
    """
    return math.exp(-RECENCY_DECAY_RATE * max(age_hours, 0.0))


def compute_raw_score(
    signals: list[dict],
    reference_time: datetime | None = None,
    user_weight_multipliers: dict[str, float] | None = None,
) -> float:
    """Compute the raw weighted convergence score for a set of signals.

    Formula per architecture.md:
        raw_score = Σ weight(signal_type) × recency_factor(age_hours)

    Each signal contributes its type weight decayed by age. Multiple signals
    of the same type accumulate additively (deduped by dedup_hash at ingest).

    Args:
        signals: List of signal dicts with keys: signal_type, occurred_at.
            occurred_at can be a datetime or ISO string.
        reference_time: Time to compute age against. Defaults to now (UTC).
        user_weight_multipliers: Optional per-signal-type multipliers from the
            advanced UI weight sliders. Applied on top of base SIGNAL_WEIGHTS.

    Returns:
        Raw convergence score (unnormalized).
    """
    if not signals:
        return 0.0

    if reference_time is None:
        reference_time = datetime.now(UTC)

    score = 0.0
    for signal in signals:
        signal_type = signal.get("signal_type", "")
        base_weight = SIGNAL_WEIGHTS.get(signal_type, 0.0)
        if base_weight == 0.0:
            continue

        # Apply user multiplier if provided
        if user_weight_multipliers and signal_type in user_weight_multipliers:
            base_weight *= user_weight_multipliers[signal_type]

        # Compute age in hours
        occurred_at = signal.get("occurred_at")
        if isinstance(occurred_at, str):
            occurred_at = datetime.fromisoformat(occurred_at)
        if occurred_at is None:
            continue

        # Ensure timezone-aware comparison
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)

        age_hours = (reference_time - occurred_at).total_seconds() / 3600.0
        score += base_weight * recency_factor(age_hours)

    return score


def compute_z_score(raw_score: float, mu: float, sigma: float) -> float:
    """Normalize a raw score against cell baseline statistics.

    Formula: z = (raw_score - μ) / max(σ, SIGMA_FLOOR)

    Args:
        raw_score: The current raw convergence score.
        mu: Historical mean raw score for this cell.
        sigma: Historical standard deviation for this cell.

    Returns:
        Z-score (standard deviations above baseline). Negative values indicate
        below-baseline activity.
    """
    return (raw_score - mu) / max(sigma, SIGMA_FLOOR)
