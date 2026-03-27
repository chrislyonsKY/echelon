# Echelon — Specification

**Version:** 0.1.0
**Status:** Active
**Author:** Chris Lyons

---

## Purpose

Echelon is an open-source GEOINT conflict and maritime activity monitoring dashboard. It fuses five independent open-data signal streams into a convergence heatmap, enabling OSINT researchers, journalists, policy analysts, and the public to identify locations where multiple signals simultaneously exceed historical baselines.

---

## v1.0 Feature Requirements

### F-01: Convergence Heatmap (Primary View)
- **MUST** render a global MapLibre GL JS map with H3 hexagonal heatmap overlay
- **MUST** color cells by Z-score using a diverging color ramp (neutral → yellow → orange → red)
- **MUST** switch H3 resolution automatically based on zoom: res 5 (zoom < 5), res 7 (zoom 5–9), res 9 (zoom > 9)
- **MUST** render low-confidence cells (< 30 baseline observations) with a distinct hatched pattern
- **MUST** refresh heatmap data every 15 minutes without full page reload
- **MUST** show a legend explaining Z-score thresholds and color mapping
- **SHOULD** allow toggling between absolute Z-score and percentile rank display

### F-02: Investigation Sidebar (Secondary Mode)
- **MUST** open on click of any H3 cell
- **MUST** contain three tabs: Layer Panel, Event Timeline, Signal Cards
- **Layer Panel:** Toggle individual signal feeds (ACLED, GFW, Sentinel-2, OSM, News) on/off as map overlays
- **Event Timeline:** Chronological list of all signals in the selected cell, filterable by date range and signal type
- **Signal Cards:** Evidence cards per event with source attribution, timestamp, description, and link to original source
- **MUST** close when clicking outside the cell or pressing Escape

### F-03: Signal Layers
- **ACLED:** Point layer, symbolized by event type (battle, explosion, protest, riot). Clickable points open Signal Cards.
- **GFW Vessels:** H3 hexbin density at res 7; individual vessel tracks at zoom > 9. AIS gap events highlighted in red.
- **Sentinel-2:** Sidebar scene browser (thumbnail grid filtered by current viewport); load scene as styled COG overlay on click. NBR anomaly cells highlighted on map.
- **OSM Infrastructure:** Toggleable overlay for `military=*`, `aeroway=*`, `man_made=petroleum_well`, pipeline features.
- **LandScan Population:** Choropleth toggle (PMTiles). Off by default.
- **NGA Tearline:** Sidebar panel showing latest Tearline reports, linked to geographic extent where possible.

### F-04: Timeline Scrubber
- **MUST** provide a date range control (start/end date pickers + preset buttons: 24h, 7d, 30d, 90d)
- **MUST** apply date range to ACLED, GFW, and News layers simultaneously
- **MUST** NOT affect OSM or LandScan layers (these are near-static)

### F-05: BYOK Copilot
- **MUST** allow user to enter their Anthropic API key in a settings panel
- **MUST** offer two key storage modes with clear UI explanation: browser localStorage only, or server-side AES-256 encrypted (authenticated users only)
- **MUST** support the full 6-tool agent manifest (query_acled, query_stac, query_overpass, query_vessels, get_convergence_score, get_news)
- **MUST** implement map control protocol: copilot responses may include `map_action` objects that pan/zoom/highlight the map
- **MUST** display tool call activity in the chat UI (collapsible "Using tool: query_acled...")
- **MUST** never log the user's API key server-side
- **SHOULD** persist conversation history in browser sessionStorage (cleared on tab close)

### F-06: Alert System
- **MUST** allow authenticated users to draw or import AOI polygons
- **MUST** support four alert trigger types: Z-score threshold (default 2.0σ), new ACLED event type in AOI, GFW AIS gap within AOI, news spike above rolling average
- **MUST** display in-app notifications via a notification bell (polled every 60s)
- **MUST** support email opt-in per AOI via Resend
- **SHOULD** allow per-AOI custom Z-score thresholds
- **SHOULD** allow users to configure email digest (instant vs. daily summary)

### F-07: Authentication
- **MUST** support fully anonymous read access (no friction for journalists/researchers)
- **MUST** support GitHub OAuth login
- **MUST** use HttpOnly session cookies — never expose session tokens to JavaScript
- Authenticated features: saved AOIs, alert subscriptions, server-side BYOK storage

### F-08: Advanced Weight Controls
- **MUST** provide a collapsible advanced panel with signal weight sliders
- **MUST** apply weight adjustments client-side to a visual preview; server-side weights are always the validated defaults
- **SHOULD** allow saving custom weight profiles per user (authenticated only)

---

## Non-Functional Requirements

### Performance
- Heatmap tile API response < 500ms for res 5 (global), < 1000ms for res 7 (regional)
- Copilot tool call responses < 10s for cached data; live API calls may take longer with user-visible progress
- Frontend initial load < 3s on 10Mbps connection

### Reliability
- All Celery ingestion tasks must be idempotent and retry-safe
- Signal deduplication prevents duplicate events from multiple ingestion runs
- PostGIS convergence score cache is stale-acceptable (15-minute refresh) — UI should show last-computed timestamp

### Security
- All external API keys stored in environment variables only
- BYOK keys never written to logs
- Authenticated endpoints enforce session validation on every request
- SQL parameters always use bound parameters — no string interpolation

### Data Attribution
- All Signal Cards must display source attribution (ACLED, GFW, NewsData, etc.)
- Map UI must display a data sources panel with links and license notices
- ACLED requires explicit attribution per their EULA

---

## Out of Scope (v1.0)

- Real-time AIS positional feed (GFW event-based data only in v1)
- Satellite AIS (requires commercial provider)
- User-to-user collaboration or shared workspaces
- Mobile-native app
- Automated GEOINT report generation
- Historical playback animation
- Integration with classified or restricted data sources
