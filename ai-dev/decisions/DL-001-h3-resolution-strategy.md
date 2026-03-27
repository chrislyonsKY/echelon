# DL-001: H3 Hexagonal Grid for Convergence Scoring

**Date:** 2025-03-25
**Status:** Accepted
**Author:** Chris Lyons

## Context

Echelon needs a spatial indexing system that supports: (1) multi-resolution rendering without re-projecting data, (2) fast PostGIS aggregation queries across millions of signal records, (3) consistent cell area at each zoom level, and (4) compatibility with Deck.gl's H3HexagonLayer.

## Decision

Use Uber H3 at three fixed resolutions: 5 (global), 7 (regional), 9 (tactical). All signals are indexed at all three resolutions at ingest time (stored as `h3_index_5`, `h3_index_7`, `h3_index_9` on the signals table). Convergence scores are pre-computed and cached at all three resolutions.

## Alternatives Considered

- **S2 geometry** — Rejected: less frontend library support, Deck.gl H3HexagonLayer is a first-class component.
- **Quadtree tiles (MVT)** — Rejected: variable tile density makes Z-score baseline comparison unreliable across zoom levels.
- **Single resolution** — Rejected: res 9 globally would generate ~5.5 billion cells; res 5 globally loses tactical precision.

## Consequences

- All signal ingest code must compute three H3 indexes per point at write time (cheap with the h3 library).
- The `h3_convergence_scores` table is triple the size (three rows per active cell).
- Deck.gl frontend uses `H3HexagonLayer` with `getHexagon` mapped to the resolution-appropriate index column.
