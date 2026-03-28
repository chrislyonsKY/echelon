/**
 * EchelonMap — cartographic GEOINT map for GIS professionals and OSINT analysts.
 *
 * - Click any point to see full detail
 * - Hover for quick info
 * - Scale bar + coordinate readout
 * - Professional symbology with source-coded colors
 */
import { useRef, useCallback, useEffect, useState, useMemo } from "react";
import Map, {
  type MapRef,
  Source,
  Layer,
  Popup,
  ScaleControl,
  NavigationControl,
  type MapLayerMouseEvent,
} from "react-map-gl/maplibre";
import { useEchelonStore } from "@/store/echelonStore";
import { convergenceApi, signalsApi, type ConvergenceTile, type SignalEvent } from "@/services/api";
import { cellToLatLng } from "h3-js";
import { format } from "date-fns";
import ConfoundersToggle from "./ConfoundersToggle";
import TimelineScrubber from "./TimelineScrubber";
import BasemapSwitcher, { getBasemapStyleUrl } from "./BasemapSwitcher";
import MeasureTools from "./MeasureTools";
import SunCalcTool from "./SunCalc";
import ExifDropZone from "./ExifDropZone";
import CyberLayers from "./CyberLayers";

const REFRESH_MS = 15 * 60 * 1000;

// Source color palette — consistent across the entire app
const SOURCE_COLORS: Record<string, { color: string; label: string }> = {
  gdelt:        { color: "#ef4444", label: "GDELT Conflict" },
  gfw:          { color: "#3b82f6", label: "Maritime (GFW)" },
  newsdata:     { color: "#f59e0b", label: "News" },
  osm:          { color: "#10b981", label: "Infrastructure" },
  sentinel2:    { color: "#a855f7", label: "Earth Observation" },
  opensky:      { color: "#06b6d4", label: "Military Aviation" },
  osint_scrape: { color: "#f59e0b", label: "OSINT" },
  firms:        { color: "#f97316", label: "Thermal/Fire" },
  aisstream:    { color: "#3b82f6", label: "AIS Vessel" },
};

export default function EchelonMap() {
  const mapRef = useRef<MapRef>(null);
  const {
    viewState, setViewState, setSelectedCell,
    activeResolution, dateRange, basemapStyle,
  } = useEchelonStore();

  const [tiles, setTiles] = useState<ConvergenceTile[]>([]);
  const [signals, setSignals] = useState<SignalEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [popup, setPopup] = useState<{
    lng: number; lat: number;
    type: "signal" | "convergence";
    data: Record<string, unknown>;
  } | null>(null);
  const [cursorCoord, setCursorCoord] = useState<{ lat: number; lng: number } | null>(null);

  // Fetch convergence tiles
  useEffect(() => {
    const load = () => {
      setIsLoading(true);
      convergenceApi.getTiles(activeResolution)
        .then(data => setTiles(data))
        .catch(() => {})
        .finally(() => setIsLoading(false));
    };
    load();
    const interval = setInterval(load, REFRESH_MS);
    return () => clearInterval(interval);
  }, [activeResolution]);

  // Fetch signal events when zoomed in
  useEffect(() => {
    const zoom = viewState.zoom ?? 2;
    if (zoom < 4) { setSignals([]); return; }
    const span = 360 / Math.pow(2, zoom);
    const lon = viewState.longitude ?? 0;
    const lat = viewState.latitude ?? 0;
    const bbox: [number, number, number, number] = [lon - span / 2, lat - span / 2, lon + span / 2, lat + span / 2];
    signalsApi.getForBbox(bbox, "", dateRange.from.toISOString().split("T")[0], dateRange.to.toISOString().split("T")[0])
      .then(data => setSignals(data))
      .catch(() => setSignals([]));
  }, [viewState.zoom, viewState.longitude, viewState.latitude, dateRange]);

  const tileGeoJSON = useMemo(() => tilesToGeoJSON(tiles), [tiles]);
  const signalGeoJSON = useMemo(() => signalsToGeoJSON(signals), [signals]);

  // Click handler — works for both convergence cells and signal events
  const handleClick = useCallback((e: MapLayerMouseEvent) => {
    const feature = e.features?.[0];
    if (!feature?.properties) return;
    const props = feature.properties;
    const { lng, lat } = e.lngLat;

    if (props.h3Index) {
      setPopup({
        lng, lat, type: "convergence",
        data: {
          h3Index: props.h3Index,
          zScore: props.zScore,
          rawScore: props.rawScore,
          lowConfidence: props.lowConfidence,
        },
      });
      setSelectedCell({
        h3Index: props.h3Index,
        resolution: activeResolution,
        zScore: props.zScore || 0,
        center: [lng, lat],
      });
      return;
    }

    if (props.signalId) {
      setPopup({
        lng, lat, type: "signal",
        data: {
          id: props.signalId,
          source: props.source,
          signalType: props.signalType,
          title: props.title,
          occurredAt: props.occurredAt,
          provenance: props.provenance,
          detail1: props.detail1,
          detail2: props.detail2,
          url: props.url,
        },
      });
      // Also open the event detail panel
      window.dispatchEvent(new CustomEvent("echelon:open-event", { detail: props.signalId }));
      return;
    }
  }, [activeResolution, setSelectedCell]);

  // Cursor changes on hover
  const handleMouseEnter = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (map) map.getCanvas().style.cursor = "pointer";
  }, []);
  const handleMouseLeave = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (map) map.getCanvas().style.cursor = "";
  }, []);

  // Track cursor position for coordinate readout
  const handleMouseMove = useCallback((e: MapLayerMouseEvent) => {
    setCursorCoord({ lat: e.lngLat.lat, lng: e.lngLat.lng });
  }, []);

  return (
    <div style={{ position: "relative", flex: 1, height: "100%" }}>
      <Map
        ref={mapRef}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        onMouseMove={handleMouseMove}
        mapStyle={getBasemapStyleUrl(basemapStyle)}
        attributionControl={false}
        interactiveLayerIds={["convergence-circles", "signal-dots"]}
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onLoad={() => {
          const map = mapRef.current?.getMap();
          if (!map) return;
          // Dim basemap labels so data stands out
          map.getStyle().layers.forEach((layer) => {
            if (layer.type === "symbol" && layer.layout?.["text-field"]) {
              map.setPaintProperty(layer.id, "text-opacity", [
                "interpolate", ["linear"], ["zoom"], 0, 0.2, 4, 0.35, 7, 0.55, 10, 0.8,
              ]);
            }
          });
        }}
      >
        {/* ── Convergence heatmap ─────────────────────────────────────── */}
        <Source id="convergence" type="geojson" data={tileGeoJSON}>
          {/* Outer glow — atmospheric effect */}
          <Layer
            id="convergence-glow"
            type="circle"
            paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 10, 5, 20, 8, 28, 12, 36],
              "circle-color": [
                "interpolate", ["linear"], ["get", "score"],
                0, "rgba(30,64,175,0)",
                0.3, "rgba(59,130,246,0.12)",
                0.5, "rgba(245,158,11,0.18)",
                1.0, "rgba(249,115,22,0.22)",
                2.0, "rgba(239,68,68,0.28)",
                4.0, "rgba(168,85,247,0.32)",
              ],
              "circle-blur": 1.2,
            }}
          />
          {/* Core circles */}
          <Layer
            id="convergence-circles"
            type="circle"
            paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 3.5, 5, 7, 8, 11, 12, 16],
              "circle-color": [
                "interpolate", ["linear"], ["get", "score"],
                0, "#1e40af",
                0.15, "#3b82f6",
                0.4, "#f59e0b",
                0.8, "#f97316",
                1.5, "#ef4444",
                3.0, "#c084fc",
              ],
              "circle-opacity": ["interpolate", ["linear"], ["get", "score"], 0, 0.6, 0.5, 0.85, 2, 0.95],
              "circle-stroke-width": ["interpolate", ["linear"], ["get", "score"], 0, 0.5, 0.5, 1, 2, 1.5],
              "circle-stroke-color": "rgba(255,255,255,0.25)",
            }}
          />
        </Source>

        {/* ── Signal events ──────────────────────────────────────────── */}
        <Source id="signals" type="geojson" data={signalGeoJSON}>
          {/* Glow ring */}
          <Layer
            id="signal-glow"
            type="circle"
            paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 8, 8, 12, 12, 16],
              "circle-color": [
                "match", ["get", "source"],
                "gdelt", "rgba(239,68,68,0.2)",
                "gfw", "rgba(59,130,246,0.2)",
                "newsdata", "rgba(245,158,11,0.2)",
                "osm", "rgba(16,185,129,0.15)",
                "opensky", "rgba(6,182,212,0.2)",
                "osint_scrape", "rgba(245,158,11,0.15)",
                "firms", "rgba(249,115,22,0.2)",
                "rgba(148,163,184,0.12)",
              ],
              "circle-blur": 0.8,
            }}
          />
          {/* Core dots */}
          <Layer
            id="signal-dots"
            type="circle"
            paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 3, 8, 5, 12, 7],
              "circle-color": [
                "match", ["get", "source"],
                "gdelt", "#ef4444",
                "gfw", "#3b82f6",
                "newsdata", "#f59e0b",
                "osm", "#10b981",
                "opensky", "#06b6d4",
                "osint_scrape", "#f59e0b",
                "firms", "#f97316",
                "aisstream", "#3b82f6",
                "#94a3b8",
              ],
              "circle-opacity": 0.92,
              "circle-stroke-width": 1,
              "circle-stroke-color": "rgba(255,255,255,0.5)",
            }}
          />
        </Source>

        {/* ── Popup ──────────────────────────────────────────────────── */}
        {popup && (
          <Popup
            longitude={popup.lng}
            latitude={popup.lat}
            anchor="bottom"
            onClose={() => setPopup(null)}
            closeButton={true}
            closeOnClick={false}
            maxWidth="340px"
            className="echelon-popup"
          >
            {popup.type === "convergence" ? (
              <ConvergencePopup data={popup.data} lat={popup.lat} lng={popup.lng} />
            ) : (
              <SignalPopup data={popup.data} lat={popup.lat} lng={popup.lng} />
            )}
          </Popup>
        )}

        {/* ── Map controls ───────────────────────────────────────────── */}
        <ScaleControl position="bottom-right" maxWidth={120} unit="metric" />
        <NavigationControl position="top-right" showCompass={true} showZoom={false} />
      </Map>

      {/* Loading indicator */}
      {isLoading && (
        <div role="status" style={{
          position: "absolute", top: 12, left: "50%", transform: "translateX(-50%)",
          background: "rgba(17,24,39,0.92)", color: "var(--color-text-secondary)",
          padding: "5px 14px", borderRadius: 6, fontSize: 11,
          border: "1px solid var(--color-border)", backdropFilter: "blur(8px)",
        }}>
          <span style={{ animation: "pulse 1.5s infinite" }}>Loading signals...</span>
        </div>
      )}

      {/* OSINT tools */}
      <MeasureTools mapRef={mapRef} />
      <SunCalcTool mapRef={mapRef} />
      <ExifDropZone />
      <CyberLayers mapRef={mapRef} />
      <ConfoundersToggle mapRef={mapRef} />
      <TimelineScrubber />
      <BasemapSwitcher />

      {/* Cartographic legend */}
      <MapLegend tileCount={tiles.length} signalCount={signals.length} />

      {/* Coordinate readout — always visible at bottom */}
      <div style={{
        position: "absolute", bottom: 24, left: "50%", transform: "translateX(-50%)",
        display: "flex", gap: 16, alignItems: "center",
        padding: "3px 12px", borderRadius: 4,
        background: "rgba(17,24,39,0.75)", backdropFilter: "blur(4px)",
        fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)",
      }}>
        {cursorCoord && (
          <span>{cursorCoord.lat.toFixed(5)}, {cursorCoord.lng.toFixed(5)}</span>
        )}
        <span style={{ color: "var(--color-text-muted)" }}>
          Z{(viewState.zoom ?? 2).toFixed(1)} | H3r{activeResolution}
        </span>
        <span style={{ color: "var(--color-text-muted)" }}>
          {tiles.length} cells | {signals.length} events
        </span>
      </div>
    </div>
  );
}

// ── Popup components ──────────────────────────────────────────────────────────

function ConvergencePopup({ data, lat, lng }: { data: Record<string, unknown>; lat: number; lng: number }) {
  const z = Number(data.zScore) || 0;
  const raw = Number(data.rawScore) || 0;
  const low = Boolean(data.lowConfidence);

  return (
    <div style={{ fontFamily: "Inter, system-ui, sans-serif", fontSize: 12, lineHeight: 1.6, minWidth: 200 }}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4, color: z > 2 ? "#ef4444" : z > 1 ? "#f59e0b" : "#f1f5f9" }}>
        Convergence Cell
      </div>
      <PopupRow label="Z-Score" value={z.toFixed(3)} highlight={z > 1.5} />
      <PopupRow label="Raw Score" value={raw.toFixed(5)} />
      <PopupRow label="H3 Index" value={String(data.h3Index)} mono />
      <PopupRow label="Coordinates" value={`${lat.toFixed(5)}, ${lng.toFixed(5)}`} mono />
      {low && (
        <div style={{ marginTop: 4, fontSize: 10, color: "#f59e0b", fontStyle: "italic" }}>
          Low confidence — fewer than 30 baseline observations
        </div>
      )}
      <div style={{ marginTop: 6, fontSize: 9, color: "#64748b" }}>
        Click to investigate all signals in this cell
      </div>
    </div>
  );
}

function SignalPopup({ data, lat, lng }: { data: Record<string, unknown>; lat: number; lng: number }) {
  const source = String(data.source || "");
  const signalType = String(data.signalType || "");
  const title = String(data.title || signalType.replace(/_/g, " "));
  const occurredAt = String(data.occurredAt || "");
  const provenance = String(data.provenance || "");
  const detail1 = String(data.detail1 || "");
  const detail2 = String(data.detail2 || "");
  const url = String(data.url || "");

  const srcMeta = SOURCE_COLORS[source] || { color: "#94a3b8", label: source };

  return (
    <div style={{ fontFamily: "Inter, system-ui, sans-serif", fontSize: 12, lineHeight: 1.6, minWidth: 220 }}>
      {/* Source badge + title */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
        <span style={{
          width: 8, height: 8, borderRadius: "50%", background: srcMeta.color, flexShrink: 0,
        }} />
        <span style={{ fontWeight: 700, fontSize: 13, color: "#f1f5f9" }}>
          {title.length > 60 ? title.slice(0, 57) + "..." : title}
        </span>
      </div>

      <PopupRow label="Source" value={srcMeta.label} />
      <PopupRow label="Type" value={signalType.replace(/_/g, " ")} />
      {occurredAt && (
        <PopupRow
          label="Time"
          value={(() => { try { return format(new Date(occurredAt), "MMM d, yyyy HH:mm"); } catch { return occurredAt; } })()}
        />
      )}
      <PopupRow label="Coordinates" value={`${lat.toFixed(5)}, ${lng.toFixed(5)}`} mono />

      {provenance && (
        <div style={{ marginTop: 4 }}>
          <span style={{
            fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 3,
            background: provenance.includes("wire") ? "rgba(16,185,129,0.2)" : "rgba(148,163,184,0.2)",
            color: provenance.includes("wire") ? "#10b981" : "#94a3b8",
          }}>
            {provenance.replace(/_/g, " ").toUpperCase()}
          </span>
        </div>
      )}

      {detail1 && <div style={{ marginTop: 4, fontSize: 11, color: "#94a3b8" }}>{detail1}</div>}
      {detail2 && <div style={{ fontSize: 11, color: "#64748b" }}>{detail2}</div>}

      {url && (
        <a href={url} target="_blank" rel="noopener noreferrer" style={{
          display: "inline-block", marginTop: 6, fontSize: 10,
          color: "#3b82f6", textDecoration: "none",
        }}>
          Open source &rarr;
        </a>
      )}

      <div style={{ marginTop: 6, fontSize: 9, color: "#64748b" }}>
        Click to view full event detail
      </div>
    </div>
  );
}

function PopupRow({ label, value, mono, highlight }: {
  label: string; value: string; mono?: boolean; highlight?: boolean;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "1px 0" }}>
      <span style={{ color: "#64748b", fontSize: 11 }}>{label}</span>
      <span style={{
        color: highlight ? "#ef4444" : "#e2e8f0",
        fontFamily: mono ? "var(--font-mono)" : "inherit",
        fontSize: 11, fontWeight: highlight ? 600 : 400,
        textAlign: "right",
      }}>
        {value}
      </span>
    </div>
  );
}

// ── Map legend ────────────────────────────────────────────────────────────────

function MapLegend(_props: { tileCount: number; signalCount: number }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div style={{
      position: "absolute", bottom: 40, left: 12,
      background: "rgba(17,24,39,0.92)", border: "1px solid var(--color-border)",
      borderRadius: 8, backdropFilter: "blur(8px)",
      overflow: "hidden", minWidth: collapsed ? 80 : 150,
    }}>
      <button
        onClick={() => setCollapsed(!collapsed)}
        style={{
          width: "100%", padding: "6px 12px", border: "none", cursor: "pointer",
          background: "none", display: "flex", justifyContent: "space-between", alignItems: "center",
        }}
      >
        <span style={{ fontSize: 9, fontWeight: 700, color: "var(--color-text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Legend
        </span>
        <span style={{ fontSize: 8, color: "var(--color-text-muted)" }}>
          {collapsed ? "+" : "-"}
        </span>
      </button>

      {!collapsed && (
        <div style={{ padding: "0 12px 10px" }}>
          {/* Convergence ramp */}
          <div style={{ fontSize: 8, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", marginBottom: 4, letterSpacing: "0.05em" }}>
            Convergence Z-Score
          </div>
          <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", marginBottom: 2 }}>
            {["#1e40af", "#3b82f6", "#f59e0b", "#f97316", "#ef4444", "#c084fc"].map((c, i) => (
              <div key={i} style={{ flex: 1, background: c }} />
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 8, color: "var(--color-text-muted)", marginBottom: 8 }}>
            <span>Low</span><span>High</span>
          </div>

          {/* Signal sources */}
          <div style={{ fontSize: 8, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", marginBottom: 4, letterSpacing: "0.05em" }}>
            Signal Sources
          </div>
          {Object.entries(SOURCE_COLORS).slice(0, 6).map(([, meta]) => (
            <div key={meta.label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: meta.color, flexShrink: 0 }} />
              <span style={{ fontSize: 9, color: "var(--color-text-secondary)" }}>{meta.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── GeoJSON builders ──────────────────────────────────────────────────────────

function tilesToGeoJSON(tiles: ConvergenceTile[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: tiles.map(t => {
      let lat = 0, lng = 0;
      try { const [la, ln] = cellToLatLng(t.h3Index); lat = la; lng = ln; } catch { /* skip */ }
      const score = t.lowConfidence ? t.rawScore * 3 : t.zScore;
      return {
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [lng, lat] },
        properties: { h3Index: t.h3Index, zScore: t.zScore, rawScore: t.rawScore, score, lowConfidence: t.lowConfidence },
      };
    }).filter(f => f.geometry.coordinates[0] !== 0),
  };
}

function signalsToGeoJSON(signals: SignalEvent[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: signals.map(s => {
      const p = s.rawPayload || {};

      // Extract human-readable info from payload
      const title = (p.title as string) || (p.callsign as string) || (p.name as string)
        || (p.infra_type as string)?.replace(/_/g, " ") || s.signalType.replace(/_/g, " ");

      // Build detail lines for the popup
      let detail1 = "";
      let detail2 = "";
      if (p.GoldsteinScale) detail1 = `Goldstein: ${p.GoldsteinScale}`;
      if (p.NumArticles) detail1 += ` | ${p.NumArticles} articles`;
      if (p.vessel && typeof p.vessel === "object") {
        const v = p.vessel as Record<string, unknown>;
        detail1 = `${v.name || "Unknown vessel"} (${v.flag || "?"})`;
      }
      if (p.origin_country) detail1 = `${p.origin_country}`;
      if (p.velocity) detail2 = `Speed: ${Math.round(p.velocity as number)} m/s`;
      if (p.source && typeof p.source === "string") detail2 = `via ${p.source}`;
      if (p.description && typeof p.description === "string") {
        detail1 = detail1 || (p.description as string).slice(0, 100);
      }

      return {
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [s.location.lng, s.location.lat] },
        properties: {
          signalId: s.id,
          source: s.source,
          signalType: s.signalType,
          title,
          occurredAt: s.occurredAt || "",
          provenance: s.provenanceFamily || s.confirmationPolicy || "",
          detail1,
          detail2,
          url: typeof p.url === "string" ? p.url : "",
        },
      };
    }),
  };
}
