# DL-002: Z-Score Against Rolling Baseline for Convergence

**Date:** 2025-03-25
**Status:** Accepted
**Author:** Chris Lyons

## Context

The heatmap needs to surface "unusual" activity, not just dense activity. A cell in eastern Ukraine with 40 ACLED events is unremarkable. A cell in the Norwegian Sea with 2 ACLED events is highly anomalous. A raw event count renders the former red and the latter invisible — the opposite of what we want.

## Decision

Normalize raw weighted signal scores against a 365-day rolling per-cell baseline using Z-scores: `(raw_score - μ) / σ`. Cells with fewer than 30 baseline observations are flagged `low_confidence=True` and rendered with a distinct UI treatment. Cells with σ < 0.001 use a σ floor to prevent division by zero.

## Alternatives Considered

- **Raw event count** — Rejected: renders endemic conflict zones as permanently red, obscuring genuine anomalies.
- **Percentile rank** — Considered as a secondary display mode (included as a toggle in F-01), but Z-score is the primary because it preserves magnitude information above the threshold.
- **30-day baseline** — Rejected: too short to capture seasonal patterns in conflict cycles. 90 days considered; 365 chosen to capture annual patterns despite requiring a year of history to be fully meaningful.

## Consequences

- The baseline must be bootstrapped with 365 days of historical data before the scorer produces meaningful results.
- New deployments will have low-confidence cells for up to a year until sufficient baseline accumulates.
- The `recompute_convergence` Celery task runs every 15 minutes and is the most database-intensive regular operation.
