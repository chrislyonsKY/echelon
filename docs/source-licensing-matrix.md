# Source Licensing Matrix

**Last Updated:** 2026-03-29

This document tracks the license terms, attribution requirements, and redistribution constraints for every external data source integrated into Echelon.

---

## License Summary Table

| Source | License | Attribution Required | Commercial Use | Redistribution | Notes |
|--------|---------|---------------------|----------------|----------------|-------|
| GDELT | Open / unrestricted | No | Yes | Yes | Fully open bulk data. No API key required. No usage caps. |
| Global Fishing Watch (GFW) | CC BY-SA 4.0 | Yes | Non-commercial only (free tier) | Yes, under same license | Must display: "Vessel data from Global Fishing Watch -- globalfishingwatch.org". Contact GFW for commercial licensing if Echelon is ever monetized. |
| ACLED | Restricted academic license (EULA) | Yes | No (non-commercial only) | No (raw data) | Redistribution of raw ACLED records is prohibited. Echelon stores derived signals (H3-indexed weights), not raw exports. Must display: "Data sourced from ACLED (Armed Conflict Location & Event Data Project) -- acleddata.com". |
| Sentinel-2 (Copernicus) | Copernicus Open Access | Yes | Yes | Yes | Free and open for all purposes. Attribution: "Contains modified Copernicus Sentinel data [year]". Accessed via Element84 Earth Search STAC. |
| OpenSky Network | Open Database License (ODbL 1.0) | Yes | Yes | Yes, under ODbL | Derived databases must remain open. Attribution: "Data from The OpenSky Network -- opensky-network.org". |
| OSM / ohsome (Overpass API) | Open Database License (ODbL 1.0) | Yes | Yes | Yes, under ODbL | Must attribute: "(c) OpenStreetMap contributors". Derived works using OSM data must be released under ODbL or a compatible license. Rate-limit Overpass queries (1 req/60s for large queries). |
| NewsData.io | API Terms of Service | Per terms | Yes (free tier allows commercial) | No (content belongs to publishers) | 200 credits/day on free tier. Echelon stores article metadata and summaries as signals, not full article text. Paid tier required above daily cap. |
| NewsAPI | API Terms of Service | Per terms | Paid plans only | No (content belongs to publishers) | Free tier restricted to development only. Production use requires a paid plan. |
| GNews | API Terms of Service | Per terms | Yes (with paid plan) | No (content belongs to publishers) | 100 requests/day on free tier. Similar constraints to NewsAPI. |
| NASA FIRMS | US Government public domain | No (courtesy appreciated) | Yes | Yes | US government works are not subject to copyright. Free MAP key required for API access. No usage restrictions. |
| AISStream | API Terms of Service | Per terms | Check current terms | No | Free tier requires GitHub authentication. Real-time AIS data feed. Terms may change; review periodically. |
| Capella Open Data | CC BY 4.0 | Yes | Yes | Yes | Attribution: "Capella Space Open Data". SAR imagery for select events and disaster response. |
| Maxar Open Data | CC BY-NC 4.0 | Yes | No (non-commercial only) | Yes, non-commercial | Maxar Open Data Program releases are for humanitarian and non-commercial use. Attribution: "Maxar Open Data Program". |
| GeoNames | CC BY 4.0 | Yes | Yes | Yes | Attribution: "GeoNames -- geonames.org". Free gazetteer data. |
| OurAirports | Public domain | No | Yes | Yes | Community-maintained airport database. No restrictions. |
| geoBoundaries | CC BY 4.0 | Yes | Yes | Yes | Attribution: "geoBoundaries -- geoboundaries.org". Open political boundary dataset. |

---

## Redistribution Caveats

Echelon aggregates data from sources with different and sometimes conflicting license terms. When exporting, sharing, or redistributing data derived from Echelon, the following rules apply:

1. **Most-restrictive-wins rule.** Any export that contains elements derived from multiple sources must comply with the most restrictive license among them. For example, if an export includes both GDELT (open) and ACLED (restricted) derived signals, the ACLED restrictions govern the entire export.

2. **ACLED raw data cannot be redistributed.** Echelon stores ACLED-derived signals (H3 cell weights and convergence contributions), not raw ACLED event records. However, any export that allows reconstruction of individual ACLED events may violate their EULA. Do not export raw_payload fields for ACLED signals.

3. **ODbL share-alike obligations.** Data derived from OSM or OpenSky carries ODbL share-alike requirements. If you create a derivative database that includes OSM or OpenSky data, that database must also be released under ODbL.

4. **CC BY-SA 4.0 share-alike (GFW).** Exports containing GFW-derived data must be shared under the same or a compatible license.

5. **CC BY-NC 4.0 (Maxar).** Any export containing Maxar Open Data derivatives is restricted to non-commercial use regardless of the licenses of other included sources.

6. **News content is not redistributable.** NewsData.io, NewsAPI, and GNews content belongs to the original publishers. Echelon stores metadata (title, URL, summary) as signal context. Full article text must not be stored or exported.

7. **Attribution stacking.** Exports must include attribution for every source that contributed data to the export. The UI data sources panel and any export file headers should list all applicable attributions.

---

## Periodic Review

License terms for API-based sources (NewsData.io, AISStream, GNews, NewsAPI) are governed by terms of service that may change. Review these terms at least once per quarter. Pin a reminder in your project management tool.

For open-data sources (GDELT, Sentinel-2, FIRMS), license changes are rare but should be checked annually.
