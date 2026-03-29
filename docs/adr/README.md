# Architecture Decision Records

This directory contains the Architecture Decision Records (ADRs) for Echelon.

| ADR | Title | Status | Summary |
|-----|-------|--------|---------|
| [0001](0001-h3-hexagonal-grid.md) | H3 Hexagonal Grid | Accepted | Use H3 over S2/geohash for spatial indexing -- uniform hexagonal tessellation with 16 resolutions |
| [0002](0002-celery-for-ingestion.md) | Celery for Ingestion | Accepted | Use Celery + Redis over asyncio tasks/Dramatiq/Temporal for reliable periodic data ingestion |
| [0003](0003-byok-copilot.md) | BYOK Copilot | Accepted | Users provide their own Anthropic API key -- zero project cost, no key liability |
| [0004](0004-convergence-z-score.md) | Convergence Z-Score | Accepted | Z-score normalization per H3 cell over 365-day rolling window instead of raw weighted sums |

## Format

Each ADR follows the standard format:

- **Title** -- short descriptive name
- **Status** -- Proposed, Accepted, Deprecated, or Superseded
- **Context** -- what prompted the decision
- **Decision** -- what we chose and how it works
- **Consequences** -- tradeoffs and downstream effects

## Adding a New ADR

1. Create `NNNN-short-title.md` using the next available number
2. Follow the format above
3. Update this README table
