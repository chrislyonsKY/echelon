# Data Provenance

## Purpose

Echelon combines multiple source families with different reliability, latency, coverage, and legal constraints. This document explains how source provenance should be understood and represented in code, APIs, and the analyst UI.

The core rule is simple:

- a signal is not the same thing as a verified event

## Provenance Model

Each signal should carry or derive, directly or indirectly:

- source name
- source family
- collection method
- confirmation policy
- original timestamp if available
- ingest timestamp
- licensing or attribution constraints where relevant

Signals may contribute to convergence scoring without being independently verified. Verification and convergence are different concepts.

## Source Families

The project currently uses source families such as:

- `official_sensor`
- `commercial_provider`
- `crowd_sourced`
- `news_media`
- `osint_aggregator`
- `reference_data`

These labels should be treated as provenance categories, not truth guarantees.

## Confirmation Policies

Recommended confirmation labels:

- `verified`: source is treated as directly observed or operationally trusted for the given signal type
- `partially_verified`: source is useful but may require analyst review or context
- `unverified`: signal is informative but should not be treated as confirmed on its own
- `context_only`: signal is supporting context and should not be mistaken for event confirmation

## Current Source Matrix

| Source | Family | Typical Policy | Notes |
|--------|--------|----------------|------|
| GDELT Export / GKG | `news_media` / `osint_aggregator` | `partially_verified` | Large-scale event/news signal, not ground truth |
| Global Fishing Watch | `commercial_provider` / `official_sensor` context | `partially_verified` | Strong maritime context, still requires interpretation |
| AISStream | `crowd_sourced` | `unverified` | Position data is useful but noisy and incomplete |
| OpenSky | `crowd_sourced` | `partially_verified` | Useful for flight awareness, not full authoritative tracks |
| Sentinel-2 via Earth Search | `commercial_provider` / `official_sensor` context | `verified` for image-derived pixel stats, not analyst conclusion | The pixel math may be valid while the interpretation still needs review |
| Capella Open Data | `commercial_provider` | `partially_verified` | High-value SAR source; interpretation still requires context |
| Maxar Open Data | `commercial_provider` | `partially_verified` | Strong event imagery context, activation-driven |
| OSM / ohsome | `crowd_sourced` | `context_only` | Infrastructure context, not event confirmation |
| News APIs | `news_media` | `unverified` or `partially_verified` | Depends on source quality and corroboration |
| OSINT scraper feeds | `osint_aggregator` / `news_media` / `crowd_sourced` | `unverified` | Must be clearly labeled in UI and exports |
| GeoNames / OurAirports / geoBoundaries | `reference_data` | `context_only` | Context and enrichment only |

## How Provenance Should Be Used

### In the UI

The UI should:

- show source and provenance family clearly
- avoid implying that a single unverified source confirms an event
- distinguish raw signals from event rollups
- preserve analyst visibility into what was observed versus what was inferred

### In Exports

Exports should preserve:

- source identifier
- occurrence time
- ingest time
- provenance family
- confirmation policy

If downstream tools consume Echelon exports, they should be able to reconstruct why a signal was included and how strongly it should be trusted.

### In Scoring

Convergence scores combine signals statistically. They should not be described as confirmation. A high Z-score means "multiple indicators are elevated relative to baseline," not "the event is verified."

## Attribution and Licensing

Every source addition should be reviewed for:

- license terms
- attribution requirements
- commercial or non-commercial restrictions
- redistribution limits
- derivative work constraints

This matters especially for imagery and value-added data products. For example:

- Capella open data is suitable for analyst-facing search and review with attribution
- Maxar open data has non-commercial restrictions that must not be ignored

## Intake Checklist for New Sources

Before adding a new source, document:

1. What the source actually measures
2. Whether the source is direct observation, derived analysis, media reporting, or community reporting
3. What provenance family applies
4. What confirmation policy applies
5. What attribution or licensing requirements apply
6. Whether the source is safe to score, display only, or use as context only
7. How source-health telemetry will be reported

## Analyst Guidance

Analysts and contributors should treat source material as layered evidence:

- direct sensor data can still be misread
- news coverage can be accurate but geographically imprecise
- scraped social content can be fast but unreliable
- reference data is context, not event evidence

The value of Echelon is corroboration across domains, not certainty from any single feed.
