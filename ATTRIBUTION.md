# Attribution

## Purpose

Echelon depends on public and third-party data sources with different attribution and redistribution requirements. This document is the maintainer-facing reference for what must be credited and what constraints need to follow the data.

This file is not a substitute for upstream license text. When in doubt, read the source provider's current terms directly.

## Core Rules

- Do not remove required attribution from the UI, exports, or docs.
- Do not assume "publicly accessible" means "free of licensing restrictions."
- Do not treat analyst-only access and public redistribution as the same thing.
- When adding a new source, update this file and [DATA_PROVENANCE.md](DATA_PROVENANCE.md).

## Current Source Notes

| Source | Typical Use in Echelon | Attribution / Constraint Notes |
|--------|-------------------------|-------------------------------|
| GDELT | conflict and article signals | Attribute the GDELT Project where relevant |
| Global Fishing Watch | maritime anomaly signals | Follow GFW attribution and API terms |
| OpenSky Network | aviation situational awareness | Attribute OpenSky Network where outputs or docs reference the source |
| AISStream | real-time AIS positions | Follow AISStream terms and do not imply Echelon owns underlying AIS data |
| Sentinel-2 via Element84 Earth Search | EO change detection | Preserve Sentinel / provider attribution in docs and analyst context |
| Capella Open Data | analyst-facing SAR search and analysis | Preserve Capella attribution and associated open-data license requirements |
| Maxar Open Data | analyst-facing optical imagery | Respect Maxar attribution and non-commercial restrictions |
| OpenStreetMap / ohsome | infrastructure and context | Attribute OpenStreetMap contributors |
| GeoNames | geocoding and place context | Preserve GeoNames attribution requirements |
| OurAirports | reference airfield data | Preserve source attribution in documentation if redistributed |
| geoBoundaries | administrative boundary context | Follow geoBoundaries attribution guidance |
| NewsData / NewsAPI / GNews | article metadata and signal generation | Respect each provider's API terms and redistribution limits |
| RSS / public OSINT feeds | article and context enrichment | Keep source URLs and publication names visible when practical |

## Imagery-Specific Notes

### Capella Open Data

- Use analyst-facing attribution in any UI or export that shows Capella imagery-derived results.
- If derived analytics are exported, preserve the original source reference where possible.

### Maxar Open Data

- Treat Maxar open data with extra care because non-commercial restrictions may apply.
- Do not remove or suppress Maxar attribution in public-facing materials.
- Before adding broader export or downstream redistribution features for Maxar-derived outputs, review current license terms again.

## Exports

Exports should preserve enough metadata for downstream users to understand where a signal or scene came from. At minimum, where available, exports should include:

- source name
- source identifier
- source URL or item URL
- timestamp
- provenance family
- confirmation policy

## Contributor Requirement

Any PR that adds a new provider, scraper, parser, or imagery source should update:

- [ATTRIBUTION.md](ATTRIBUTION.md)
- [DATA_PROVENANCE.md](DATA_PROVENANCE.md)
- any relevant UI-facing attribution text in the app or README
