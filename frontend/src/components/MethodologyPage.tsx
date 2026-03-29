/**
 * Methodology & Coverage Transparency Page
 *
 * Explains scoring methodology, source descriptions, update cadence,
 * known blind spots, and how to interpret Z-scores and confidence levels.
 * Accessible from TopBar link or /methodology route.
 */
import { useEchelonStore } from "@/store/echelonStore";

const SOURCES = [
  {
    key: "gfw",
    name: "Global Fishing Watch",
    family: "Official Sensor",
    cadence: "Every 12 hours",
    lag: "~24 hours",
    description:
      "AIS transmission gap and loitering events from satellite-tracked vessel data. Gaps indicate potential dark activity (transponder disabled).",
    caveats:
      "Only covers vessels with AIS transponders. Small craft, military vessels, and vessels in non-cooperative flag states are invisible. ~24h processing delay from GFW pipeline.",
    weight: 0.35,
  },
  {
    key: "gdelt",
    name: "GDELT",
    family: "Curated Dataset",
    cadence: "Every 15 minutes",
    lag: "~15 minutes",
    description:
      "Machine-coded conflict events from global news. CAMEO codes 19x (Fight) and 20x (Use conventional military force) are ingested.",
    caveats:
      "Machine-coded, not human-verified. High false-positive rate in ambiguous contexts. Geocoding is article-level (city/country), not precise coordinates. English-language bias.",
    weight: 0.3,
  },
  {
    key: "sentinel2",
    name: "Sentinel-2 Earth Observation",
    family: "Official Sensor",
    cadence: "Daily",
    lag: "24-48 hours",
    description:
      "Normalized Burn Ratio (NBR) change detection from multispectral satellite imagery. Detects fires, explosions, and large-scale destruction.",
    caveats:
      "Cloud cover blocks detection. 10m resolution misses small-scale events. 5-day revisit time creates gaps. Only active for user-defined AOIs, not global.",
    weight: 0.25,
  },
  {
    key: "firms",
    name: "NASA FIRMS",
    family: "Official Sensor",
    cadence: "Every 6 hours",
    lag: "~3 hours",
    description:
      "VIIRS thermal anomaly detections — active fires and large explosions visible from space.",
    caveats:
      "Cannot distinguish conflict fires from agricultural burns or wildfires. Industrial heat sources create false positives. Cloud cover blocks detection.",
    weight: 0.22,
  },
  {
    key: "opensky",
    name: "OpenSky Network",
    family: "Official Sensor",
    cadence: "Every 30 minutes",
    lag: "Real-time",
    description:
      "ADS-B aircraft position data filtered for military callsigns and ICAO24 ranges over conflict zones.",
    caveats:
      "Only covers aircraft with ADS-B transponders broadcasting. Military aircraft often operate transponder-off. Coverage depends on ground receiver density.",
    weight: 0.2,
  },
  {
    key: "gdelt_gkg",
    name: "GDELT GKG Threats",
    family: "Curated Dataset",
    cadence: "Every 15 minutes",
    lag: "~15 minutes",
    description:
      "Global Knowledge Graph threat-themed articles with negative tone scores. Captures emerging narrative shifts.",
    caveats:
      "Tone scoring is automated — sarcasm, opinion, and propaganda are not filtered. Geocoding imprecise.",
    weight: 0.15,
  },
  {
    key: "newsdata",
    name: "News APIs (3 sources)",
    family: "News Media",
    cadence: "Every 4 hours",
    lag: "1-4 hours",
    description:
      "Conflict-keyword articles from NewsData.io, NewsAPI, and GNews. Geocoded to article-mentioned locations.",
    caveats:
      "Geocoding is approximate (city-level). Duplicate articles across APIs are deduplicated but near-duplicates may persist. English-language bias in keyword matching.",
    weight: 0.12,
  },
  {
    key: "osint_scrape",
    name: "OSINT RSS Feeds",
    family: "News Media",
    cadence: "Every 2 hours",
    lag: "Minutes to hours",
    description:
      "Aggregated RSS from 20+ sources including Al Jazeera, BBC, Reuters, AP, TASS, Kyiv Independent, and regional outlets.",
    caveats:
      "Feed availability varies. Some sources have editorial delays. Geocoding depends on article content and may fail. Source provenance varies (state media to wire services).",
    weight: 0.12,
  },
  {
    key: "gfw_loitering",
    name: "GFW Loitering",
    family: "Official Sensor",
    cadence: "Every 12 hours",
    lag: "~24 hours",
    description:
      "Vessel loitering events near ports, infrastructure, or in unusual patterns.",
    caveats: "Same limitations as GFW AIS gaps. Fishing vessels legitimately loiter.",
    weight: 0.1,
  },
  {
    key: "osm",
    name: "OpenStreetMap (ohsome)",
    family: "Open Source",
    cadence: "Daily",
    lag: "Hours to days",
    description:
      "Military and infrastructure tag changes detected via the ohsome full-history API across 10 conflict zones.",
    caveats:
      "Contributor-dependent — coverage is uneven globally. Mappers may lag events by days or weeks. Tag changes reflect community interpretation, not ground truth.",
    weight: 0.08,
  },
  {
    key: "aisstream",
    name: "AISStream",
    family: "Crowd-Sourced",
    cadence: "Every 30 minutes",
    lag: "Real-time",
    description:
      "Real-time AIS vessel positions from WebSocket feed, filtered to conflict zone bounding boxes.",
    caveats:
      "Depends on API key availability. Only covers vessels broadcasting AIS. 60-second collection window per run — not continuous.",
    weight: 0.08,
  },
];

const IMAGERY_SOURCES = [
  {
    key: "capella",
    name: "Capella Space Open Data",
    type: "SAR (Synthetic Aperture Radar)",
    description:
      "X-band SAR scenes from Capella's community open-data program. Provides all-weather, day/night imaging at sub-meter resolution.",
    caveats:
      "Coverage is limited to scenes Capella has released publicly. Not continuous — availability depends on tasking and release schedule. Search traverses daily catalogs so wide date ranges are slower.",
    mode: "On-demand analyst search",
  },
  {
    key: "maxar",
    name: "Maxar Open Data",
    type: "Optical (multispectral)",
    description:
      "High-resolution optical imagery released by Maxar for disaster response and humanitarian events. Event-driven collections with sub-meter GSD.",
    caveats:
      "Coverage is event-driven and sparse by design — only areas with declared events are imaged. Collections are organized by event, not continuous geographic coverage.",
    mode: "On-demand analyst search",
  },
];

export default function MethodologyPage() {
  const { showMethodology, setShowMethodology } = useEchelonStore();

  if (!showMethodology) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9000,
        background: "var(--color-bg)",
        overflowY: "auto",
        padding: "0 24px 60px",
      }}
    >
      {/* Header */}
      <div
        style={{
          position: "sticky",
          top: 0,
          background: "var(--color-bg)",
          borderBottom: "1px solid var(--color-border)",
          padding: "16px 0",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          zIndex: 1,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>
          Methodology & Coverage
        </h1>
        <button
          onClick={() => setShowMethodology(false)}
          style={{
            background: "var(--color-surface-raised)",
            border: "1px solid var(--color-border)",
            color: "var(--color-text-primary)",
            padding: "6px 16px",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          Close
        </button>
      </div>

      <div style={{ maxWidth: 860, margin: "0 auto" }}>
        {/* Convergence Scoring */}
        <Section title="Convergence Scoring">
          <p>
            Echelon computes a <strong>convergence Z-score</strong> per H3
            hexagonal cell by fusing signals from multiple independent sources.
            The core premise: a single signal is noise, but multiple independent
            signals elevated simultaneously in the same location is analytically
            meaningful.
          </p>

          <h4>Formula</h4>
          <code style={codeStyle}>
            {`raw_score(cell, t) = Σ weight(signal_type) × exp(-0.05 × age_hours)
z_score(cell, t) = (raw_score - μ) / max(σ, 0.01)`}
          </code>
          <ul>
            <li>
              <strong>Recency decay</strong>: exponential with half-life ~14
              hours. Signals older than ~3 days contribute near-zero weight.
            </li>
            <li>
              <strong>Z-score normalization</strong>: raw score is compared
              against the 365-day rolling mean (μ) and standard deviation (σ)
              for each cell. A Z-score of 3.0 means the current activity is 3
              standard deviations above the historical baseline.
            </li>
            <li>
              <strong>Sigma floor</strong>: σ is floored at 0.01 to prevent
              extreme Z-scores in cells with no baseline history (cold-start
              protection).
            </li>
            <li>
              <strong>Z-score cap</strong>: capped at ±20. Values above 20 are
              statistically meaningless and typically indicate a single
              high-volume source.
            </li>
            <li>
              <strong>Per-source cap</strong>: maximum 50 signals per source
              type per cell to prevent any single source from dominating the
              score.
            </li>
          </ul>
        </Section>

        {/* H3 Resolution */}
        <Section title="H3 Hexagonal Grid">
          <p>
            Signals are indexed at three H3 resolutions at ingest time.
            The frontend requests the appropriate resolution based on zoom
            level:
          </p>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Map Zoom</th>
                <th style={thStyle}>H3 Resolution</th>
                <th style={thStyle}>Cell Size</th>
                <th style={thStyle}>Use</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={tdStyle}>&lt; 5</td>
                <td style={tdStyle}>Resolution 5</td>
                <td style={tdStyle}>~252 km²</td>
                <td style={tdStyle}>Global overview heatmap</td>
              </tr>
              <tr>
                <td style={tdStyle}>5–9</td>
                <td style={tdStyle}>Resolution 7</td>
                <td style={tdStyle}>~5.2 km²</td>
                <td style={tdStyle}>Regional investigation</td>
              </tr>
              <tr>
                <td style={tdStyle}>&gt; 9</td>
                <td style={tdStyle}>Resolution 9</td>
                <td style={tdStyle}>~0.1 km²</td>
                <td style={tdStyle}>Tactical detail</td>
              </tr>
            </tbody>
          </table>
        </Section>

        {/* Low Confidence */}
        <Section title="Low Confidence Cells">
          <p>
            Cells with fewer than <strong>30 baseline observations</strong> are
            flagged as <em>low confidence</em> and rendered with a dashed
            outline on the map. This means the Z-score is based on insufficient
            historical data — the score may be artificially inflated or
            deflated.
          </p>
          <p>
            Low-confidence cells are common in newly monitored areas, ocean
            regions, and locations where ingestors have limited coverage. They
            should not be treated as confirmed hotspots.
          </p>
        </Section>

        {/* Event Corroboration */}
        <Section title="Event Corroboration">
          <p>
            Signals are clustered into <strong>events</strong> based on
            spatiotemporal proximity (same H3 res-7 cell, within 48 hours).
            Each event is assessed for corroboration:
          </p>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Source Families</th>
                <th style={thStyle}>Meaning</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={tdStyle}>Single Source</td>
                <td style={tdStyle}>1</td>
                <td style={tdStyle}>
                  Only one source family reporting. Treat as unconfirmed.
                </td>
              </tr>
              <tr>
                <td style={tdStyle}>Multi-Source</td>
                <td style={tdStyle}>2</td>
                <td style={tdStyle}>
                  Two independent source families. Higher confidence but not
                  fully corroborated.
                </td>
              </tr>
              <tr>
                <td style={tdStyle}>Corroborated</td>
                <td style={tdStyle}>3+</td>
                <td style={tdStyle}>
                  Three or more independent source families confirm the event.
                  Highest confidence level.
                </td>
              </tr>
            </tbody>
          </table>

          <h4>Source Families</h4>
          <ul>
            <li>
              <strong>Official Sensor</strong>: GFW, OpenSky, FIRMS, Sentinel-2
              — instrument data with known provenance
            </li>
            <li>
              <strong>Curated Dataset</strong>: GDELT, ACLED — human or
              machine-coded from structured pipelines
            </li>
            <li>
              <strong>News Media</strong>: NewsData, OSINT RSS feeds — editorial
              content with varying reliability
            </li>
            <li>
              <strong>Open Source</strong>: OpenStreetMap — community-contributed
              geospatial data
            </li>
            <li>
              <strong>Crowd-Sourced</strong>: AISStream — real-time data from
              distributed receiver networks
            </li>
          </ul>
        </Section>

        {/* Sources */}
        <Section title="Data Sources">
          <p>
            Echelon ingests from {SOURCES.length} data sources. Each source has
            a base weight that reflects its analytical specificity — higher
            weight means a stronger signal of genuine activity.
          </p>

          {SOURCES.map((src) => (
            <div
              key={src.key}
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                padding: "14px 16px",
                marginBottom: 10,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  marginBottom: 6,
                }}
              >
                <h4 style={{ margin: 0, fontSize: 14 }}>{src.name}</h4>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                  {src.family} &middot; Weight: {src.weight} &middot;{" "}
                  {src.cadence}
                </div>
              </div>
              <p style={{ margin: "4px 0", fontSize: 13, lineHeight: 1.5 }}>
                {src.description}
              </p>
              <p
                style={{
                  margin: "6px 0 0",
                  fontSize: 12,
                  color: "var(--color-warning)",
                  lineHeight: 1.5,
                }}
              >
                Caveats: {src.caveats}
              </p>
            </div>
          ))}
        </Section>

        {/* Satellite Imagery */}
        <Section title="Satellite Imagery (On-Demand)">
          <p>
            Echelon provides analyst-driven search across two public satellite
            imagery catalogs. These are <strong>not</strong> scored into
            convergence — they are inspection tools for corroborating signals
            identified by the heatmap.
          </p>

          {IMAGERY_SOURCES.map((src) => (
            <div
              key={src.key}
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                padding: "14px 16px",
                marginBottom: 10,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  marginBottom: 6,
                }}
              >
                <h4 style={{ margin: 0, fontSize: 14 }}>{src.name}</h4>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                  {src.type} &middot; {src.mode}
                </div>
              </div>
              <p style={{ margin: "4px 0", fontSize: 13, lineHeight: 1.5 }}>
                {src.description}
              </p>
              <p
                style={{
                  margin: "6px 0 0",
                  fontSize: 12,
                  color: "var(--color-warning)",
                  lineHeight: 1.5,
                }}
              >
                Caveats: {src.caveats}
              </p>
            </div>
          ))}
        </Section>

        {/* Derived Tracks */}
        <Section title="Vessel & Aircraft Tracks">
          <p>
            Echelon derives movement tracks from AIS (vessel) and ADS-B
            (aircraft) signal history. Tracks are <strong>not</strong> a
            separate data source — they are reconstructed by grouping stored
            signal points by <code>source_id</code> (MMSI for vessels, ICAO24
            for aircraft) and ordering by timestamp.
          </p>
          <ul>
            <li>
              <strong>AIS tracks</strong>: grouped from AISStream snapshots.
              Track smoothness depends on polling cadence (currently 30-minute
              intervals with 60-second collection windows). Gaps between points
              may be large.
            </li>
            <li>
              <strong>ADS-B tracks</strong>: grouped from OpenSky Network
              snapshots. Same cadence limitations apply. Military aircraft
              frequently disappear mid-track when transponders are disabled.
            </li>
            <li>
              <strong>Rendering</strong>: tracks are returned as GeoJSON
              LineString features and rendered as map overlays. Each track
              carries the latest known metadata (callsign, vessel name, flag
              state where available).
            </li>
          </ul>
          <p>
            Tracks are queryable for any bounding box and time window up to 168
            hours (7 days). They are best used for pattern-of-life analysis, not
            real-time tracking.
          </p>
        </Section>

        {/* Blind Spots */}
        <Section title="Known Blind Spots">
          <p>
            No monitoring system sees everything. Echelon has significant blind
            spots that analysts should be aware of:
          </p>
          <ul>
            <li>
              <strong>No ground truth</strong>: Echelon does not have access to
              classified intelligence, human sources, or on-the-ground
              reporting. All data is from open sources.
            </li>
            <li>
              <strong>Maritime dark vessels</strong>: Vessels that never enable
              AIS (many military, fishing, and smuggling vessels) are invisible
              to GFW and AISStream.
            </li>
            <li>
              <strong>Cloud-covered areas</strong>: Sentinel-2 and FIRMS cannot
              see through cloud cover. Persistent cloud cover (e.g., monsoon
              seasons) creates systematic blind spots.
            </li>
            <li>
              <strong>English-language bias</strong>: GDELT and news APIs are
              biased toward English-language media. Events in non-English
              regions may be under-reported.
            </li>
            <li>
              <strong>ADS-B coverage gaps</strong>: OpenSky depends on ground
              receiver density. Remote and ocean areas have poor coverage.
            </li>
            <li>
              <strong>Cold-start problem</strong>: New deployment has no
              baseline history. Z-scores are unreliable until at least 30
              observations accumulate per cell (~2-4 weeks).
            </li>
            <li>
              <strong>Sub-Saharan Africa</strong>: Multiple sources have reduced
              coverage in this region — fewer AIS receivers, fewer OSM
              contributors, less English-language news.
            </li>
            <li>
              <strong>Cyber domain</strong>: Echelon monitors physical geography.
              Cyber attacks, information operations, and electronic warfare are
              not directly detected.
            </li>
            <li>
              <strong>Natural hazards</strong>: Earthquakes, volcanic eruptions,
              and severe weather can trigger false positives in FIRMS and
              Sentinel-2 change detection.
            </li>
          </ul>
        </Section>

        {/* Disclaimer */}
        <Section title="Disclaimer">
          <p style={{ color: "var(--color-text-secondary)" }}>
            Echelon is an experimental open-source tool for geospatial analysis
            research. It is not a finished intelligence product. Convergence
            scores indicate statistical anomalies relative to historical
            baselines — they do not confirm that events have occurred. All
            findings should be verified through independent analysis before any
            decision-making. The developers assume no responsibility for actions
            taken based on this data.
          </p>
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section style={{ marginTop: 32 }}>
      <h2
        style={{
          fontSize: 16,
          fontWeight: 600,
          borderBottom: "1px solid var(--color-border)",
          paddingBottom: 8,
          marginBottom: 12,
        }}
      >
        {title}
      </h2>
      <div
        style={{
          fontSize: 13,
          lineHeight: 1.7,
          color: "var(--color-text-secondary)",
        }}
      >
        {children}
      </div>
    </section>
  );
}

const codeStyle: React.CSSProperties = {
  display: "block",
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: 4,
  padding: "12px 16px",
  fontFamily: "var(--font-mono)",
  fontSize: 12,
  lineHeight: 1.6,
  whiteSpace: "pre",
  overflowX: "auto",
  color: "var(--color-text-primary)",
  margin: "8px 0 12px",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  margin: "8px 0 16px",
  fontSize: 13,
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  borderBottom: "1px solid var(--color-border)",
  color: "var(--color-text-primary)",
  fontWeight: 600,
  fontSize: 12,
};

const tdStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderBottom: "1px solid var(--color-border)",
  color: "var(--color-text-secondary)",
};
