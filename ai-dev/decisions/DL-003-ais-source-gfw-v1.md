# DL-003: GlobalFishingWatch as Primary AIS Source (v1)

**Date:** 2025-03-25
**Status:** Accepted
**Author:** Chris Lyons

## Context

Echelon requires vessel anomaly data (AIS gaps, loitering, unusual behavior) for the maritime signal layer. Real-time AIS positional feeds require either: (a) operating a physical AIS receiver and contributing to AISHub, or (b) paying a commercial provider (€199–679/month for Datalastic, $500+ for MarineTraffic/Kpler).

## Decision

Use GlobalFishingWatch Events API as the primary AIS source for v1. GFW provides pre-computed vessel anomaly events (AIS-disabling gaps, loitering, port avoidance, vessel encounters) via a free non-commercial API. This covers the analytically meaningful signal without requiring real-time positional data or commercial API spend.

The Celery ingestion interface (`IngestGFWTask`) is designed with a clean abstraction so that a commercial AIS provider (Datalastic or equivalent) can be swapped in as a drop-in replacement in v2 by implementing the same interface.

## Alternatives Considered

- **AISHub** — Rejected: requires contributing an AIS receiver feed; no paid tier available.
- **Datalastic** — Deferred to v2: €199/month Starter plan is viable but adds ongoing cost for a personal portfolio project. Architecture is designed to accommodate it.
- **MarineTraffic/Kpler** — Rejected: enterprise pricing ($500+/month), quote-only, not appropriate for open-source personal project.

## Consequences

- GFW data is ~24 hours delayed due to processing pipeline.
- Real-time vessel positions are not available in v1.
- The vessel layer shows event-based anomalies, not live tracks. This is clearly communicated in the UI.
- AIS gap events from GFW are the highest-weight signal (0.35) because they represent operationally specific, hard-to-fabricate behavior.
