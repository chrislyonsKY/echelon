# ADR-0004: Z-Score Normalization for Convergence Scoring

**Status:** Accepted
**Date:** 2024-12-20

## Context

Echelon fuses five independent signal types into a single convergence score per H3 cell:

1. ACLED conflict events (weighted)
2. GFW vessel anomalies
3. Sentinel-2 EO change detection
4. OSM infrastructure density
5. News/GDELT event mentions

The naive approach is a raw weighted sum: `score = w1*s1 + w2*s2 + ... + w5*s5`. However, this produces scores that are not comparable across cells because:

- A cell in a conflict zone (e.g., eastern Ukraine) has a high baseline across all signals. A raw score of 50 there might be normal, while the same score in rural Norway would be extraordinary.
- Signal magnitudes vary wildly. A single ACLED fatality event might score 10, while a Sentinel-2 NDVI anomaly scores 0.3. Weights alone cannot normalize this.
- Seasonal patterns (agricultural burns, fishing seasons) create cyclical baselines that raw scores ignore.

We need a normalization approach that answers: "Is this cell's current activity unusual relative to its own history?"

## Decision

We will normalize convergence scores using **Z-score standardization per H3 cell** over a **365-day rolling baseline window**:

```
z_score = (raw_score - cell_mean) / cell_sigma
```

Where:

- `raw_score` is the current weighted sum for the cell
- `cell_mean` (mu) is the mean of all raw scores for that specific cell over the past 365 days
- `cell_sigma` (sigma) is the standard deviation over the same window

Implementation details:

- Baseline statistics (mu, sigma, observation count) are stored per cell in the `convergence_baselines` table
- Baselines are recomputed daily by a Celery Beat task
- A **sigma floor of 0.1** prevents division-by-zero and extreme Z-scores in low-variance cells
- Z-scores are **capped at +/- 10.0** to prevent outliers from dominating the color scale
- Cells with fewer than **30 baseline observations** are flagged `low_confidence=True`

## Rationale

- **Self-normalizing:** Each cell is compared only to its own history. A score of Z=3.0 means "3 standard deviations above this cell's normal" regardless of the cell's absolute activity level.
- **Cross-cell comparability:** Z-scores are dimensionless and comparable across cells. A Z=3.0 in Kyiv and a Z=3.0 in Lagos both represent the same degree of anomaly relative to their respective baselines.
- **Seasonal awareness:** The 365-day window captures annual cycles (agricultural patterns, fishing seasons, monsoon effects) so they don't produce false positives.
- **Statistical foundation:** Z-scores are well-understood, easy to explain to analysts, and map naturally to significance thresholds (Z > 2.0 is roughly the 97.5th percentile).

## Consequences

- **Cold-start problem:** New cells (or cells with sparse data) have fewer than 30 observations, producing unreliable statistics. These are flagged `low_confidence=True` and rendered with a distinct visual style (dashed border, muted color) in the frontend.
- **Sigma floor needed:** Cells with near-zero variance (e.g., open ocean with no historical activity) would produce extreme Z-scores from any signal. The sigma floor of 0.1 caps the maximum Z-score contribution from low-variance cells.
- **Storage overhead:** Maintaining per-cell baseline statistics requires a dedicated table (~500K rows at res 7 globally). The daily recomputation Celery task takes approximately 2-5 minutes.
- **365-day assumption:** The rolling window assumes yearly cyclicality. Events with longer cycles (e.g., El Nino effects on fishing) may not be fully captured. This is an acceptable tradeoff for the v1 implementation.
- **Z-score cap at +/- 10.0:** Prevents extreme outliers from skewing the visualization color scale, but means truly unprecedented events are clamped at the same visual intensity as moderately extreme ones.
