# ADR-0001: H3 Hexagonal Grid for Spatial Indexing

**Status:** Accepted
**Date:** 2024-12-15

## Context

Echelon computes multi-source convergence scores across the globe. We need a hierarchical spatial indexing system that:

- Supports multiple zoom-level resolutions (global overview down to tactical)
- Provides uniform cell shapes so neighbor relationships and area comparisons are consistent
- Has strong library support in both Python (backend scoring) and JavaScript (frontend rendering)
- Integrates cleanly with PostGIS for spatial queries

The main candidates evaluated were:

| System | Cell Shape | Hierarchical | Uniform Neighbors | Python/JS Libraries |
|--------|-----------|-------------|-------------------|-------------------|
| H3 (Uber) | Hexagon | 16 resolutions | Yes (6 neighbors) | Excellent |
| S2 (Google) | Quad (spherical) | 30 levels | No (variable) | Limited JS support |
| Geohash | Rectangle | Arbitrary prefix | No (variable size at edges) | Good |

## Decision

We will use **H3 (Uber's Hexagonal Hierarchical Spatial Index)** as the spatial indexing system for all convergence scoring, heatmap rendering, and alert AOI definitions.

Resolution breakpoints:

| Zoom Level | H3 Resolution | Use Case |
|-----------|--------------|----------|
| < 5 | res 5 | Global overview (~253 km edge) |
| 5 -- 9 | res 7 | Regional analysis (~1.2 km edge) |
| > 9 | res 9 | Tactical detail (~174 m edge) |

## Rationale

- **Uniform neighbors:** Every hexagon has exactly 6 neighbors at the same resolution. This eliminates the edge effects and variable-area problems that geohash rectangles suffer from at high latitudes.
- **Hierarchical aggregation:** Parent-child relationships between resolutions allow efficient drill-down without recomputing scores from scratch.
- **Library maturity:** The `h3` Python package (v3.7+) and `h3-js` npm package are well-maintained, performant, and widely adopted in the geospatial community.
- **Consistent area:** Hexagonal cells at a given resolution have nearly uniform area across the globe (slight variation at pentagons, which are rare -- 12 per resolution).

## Consequences

- **Locked to H3 library:** All spatial indexing depends on the `h3` Python and JS libraries. A breaking change in the library would require coordinated updates across backend and frontend.
- **Resolution breakpoints are hardcoded:** The res 5/7/9 breakpoints are baked into the convergence scorer and frontend tile logic. Changing them requires re-running the full baseline computation.
- **Pentagon cells:** H3 has 12 pentagonal cells per resolution. These are handled gracefully by the library but have 5 neighbors instead of 6. In practice, none fall in areas of interest for this application.
- **No native PostGIS type:** H3 indexes are stored as `BIGINT` columns in PostgreSQL, not as native geometry. Spatial joins require converting between H3 and PostGIS geometries via `h3_to_geo_boundary()`.
