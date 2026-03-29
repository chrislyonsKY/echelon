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
import {
  convergenceApi,
  signalsApi,
  imageryApi,
  type ConvergenceTile,
  type SignalEvent,
  type TrackFeatureCollection,
  type ImageryScene,
  type ImageryAnalysis,
} from "@/services/api";
import { cellToLatLng, cellToBoundary } from "h3-js";
import { format } from "date-fns";
import ConfoundersToggle from "./ConfoundersToggle";
import TimelineScrubber from "./TimelineScrubber";
import BasemapSwitcher, { getBasemapStyleUrl } from "./BasemapSwitcher";
import MeasureTools from "./MeasureTools";
import SunCalcTool from "./SunCalc";
import ExifDropZone from "./ExifDropZone";
import CyberLayers from "./CyberLayers";
import ImageryPanel from "./ImageryPanel";
import { getDisplayDescription, getDisplayTitle, hasTranslation, textDirectionForRecord } from "@/utils/language";
import { countryFlagForName } from "@/utils/countries";

const REFRESH_MS = 15 * 60 * 1000;
const AIRCRAFT_ICON_ID = "opensky-aircraft-icon";
const EMPTY_LINE_FEATURE_COLLECTION: TrackFeatureCollection = { type: "FeatureCollection", features: [] };

// Source color palette — consistent across the entire app
// Weight drives dot radius: higher weight = larger point
const SOURCE_COLORS: Record<string, { color: string; label: string; weight: number }> = {
  gdelt:        { color: "#ef4444", label: "GDELT Conflict",     weight: 0.30 },
  gfw:          { color: "#2563eb", label: "Maritime (GFW)",     weight: 0.35 },
  newsdata:     { color: "#d97706", label: "News",               weight: 0.12 },
  osm:          { color: "#059669", label: "Infrastructure",     weight: 0.08 },
  sentinel2:    { color: "#7c3aed", label: "Earth Observation",  weight: 0.25 },
  opensky:      { color: "#0891b2", label: "Military Aviation",  weight: 0.20 },
  osint_scrape: { color: "#b45309", label: "OSINT",              weight: 0.12 },
  firms:        { color: "#ea580c", label: "Thermal/Fire",       weight: 0.22 },
  aisstream:    { color: "#1d4ed8", label: "AIS Vessel",         weight: 0.08 },
};

// Z-score color ramp — sequential, labeled breakpoints
const Z_RAMP: { z: number; color: string; label: string }[] = [
  { z: 0,   color: "#1e3a5f", label: "0" },
  { z: 1,   color: "#2563eb", label: "1" },
  { z: 2,   color: "#eab308", label: "2" },
  { z: 3,   color: "#f97316", label: "3" },
  { z: 5,   color: "#dc2626", label: "5" },
  { z: 10,  color: "#7f1d1d", label: "10+" },
];

export default function EchelonMap() {
  const mapRef = useRef<MapRef>(null);
  const {
    viewState, setViewState, setSelectedCell,
    activeResolution, dateRange, basemapStyle, theaterMode,
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
  const [aisTracks, setAisTracks] = useState<TrackFeatureCollection>(EMPTY_LINE_FEATURE_COLLECTION);
  const [flightTracks, setFlightTracks] = useState<TrackFeatureCollection>(EMPTY_LINE_FEATURE_COLLECTION);
  const [imageryOpen, setImageryOpen] = useState(false);
  const [imageryProvider, setImageryProvider] = useState<"capella" | "maxar">("capella");
  const [imageryScenes, setImageryScenes] = useState<ImageryScene[]>([]);
  const [imageryLoading, setImageryLoading] = useState(false);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [imageryAnalysis, setImageryAnalysis] = useState<ImageryAnalysis | null>(null);
  const [analyzingSceneId, setAnalyzingSceneId] = useState<string | null>(null);
  const [imageryRefreshKey, setImageryRefreshKey] = useState(0);
  const currentBbox = useMemo(() => viewportToBbox(viewState), [viewState]);
  const historyHours = useMemo(() => {
    const diffMs = dateRange.to.getTime() - dateRange.from.getTime();
    const diffHours = Math.ceil(diffMs / (60 * 60 * 1000));
    return Math.max(6, Math.min(72, diffHours));
  }, [dateRange]);

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
    signalsApi.getForBbox(currentBbox, "", dateRange.from.toISOString().split("T")[0], dateRange.to.toISOString().split("T")[0])
      .then(data => setSignals(data))
      .catch(() => setSignals([]));
  }, [viewState.zoom, currentBbox, dateRange]);

  useEffect(() => {
    const zoom = viewState.zoom ?? 2;
    if (zoom < 5) {
      setAisTracks(EMPTY_LINE_FEATURE_COLLECTION);
      setFlightTracks(EMPTY_LINE_FEATURE_COLLECTION);
      return;
    }

    let cancelled = false;
    Promise.all([
      signalsApi.getTracks(currentBbox, "aisstream", historyHours),
      signalsApi.getTracks(currentBbox, "opensky", historyHours),
    ])
      .then(([ais, flights]) => {
        if (cancelled) return;
        setAisTracks(ais);
        setFlightTracks(flights);
      })
      .catch(() => {
        if (cancelled) return;
        setAisTracks(EMPTY_LINE_FEATURE_COLLECTION);
        setFlightTracks(EMPTY_LINE_FEATURE_COLLECTION);
      });

    return () => {
      cancelled = true;
    };
  }, [viewState.zoom, currentBbox, historyHours]);

  useEffect(() => {
    if (!imageryOpen) return;
    const zoom = viewState.zoom ?? 2;
    if (zoom < 5) {
      setImageryScenes([]);
      setSelectedSceneId(null);
      return;
    }

    let cancelled = false;
    setImageryLoading(true);
    imageryApi.search({
      provider: imageryProvider,
      bbox: currentBbox,
      dateFrom: dateRange.from.toISOString().split("T")[0],
      dateTo: dateRange.to.toISOString().split("T")[0],
      limit: 10,
    })
      .then((scenes) => {
        if (cancelled) return;
        setImageryScenes(scenes);
        setSelectedSceneId((current) => current && scenes.some((scene) => scene.id === current) ? current : scenes[0]?.id ?? null);
        setImageryAnalysis((current) => current && scenes.some((scene) => scene.id === current.sceneId) ? current : null);
      })
      .catch(() => {
        if (cancelled) return;
        setImageryScenes([]);
        setSelectedSceneId(null);
        setImageryAnalysis(null);
      })
      .finally(() => {
        if (!cancelled) setImageryLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [imageryOpen, imageryProvider, currentBbox, dateRange, imageryRefreshKey, viewState.zoom]);

  // Re-register aircraft icon whenever style reloads.
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    const ensure = () => { void ensureAircraftIcon(map); };
    ensure();
    map.on("styledata", ensure);
    return () => {
      map.off("styledata", ensure);
    };
  }, [basemapStyle]);

  // Theater mode: auto-fly to highest Z-score cell every 60 seconds.
  useEffect(() => {
    if (!theaterMode || tiles.length === 0) return;

    const flyToHighest = () => {
      const highest = tiles.reduce((max, tile) => (tile.zScore > max.zScore ? tile : max), tiles[0]);
      if (!highest) return;
      try {
        const [lat, lng] = cellToLatLng(highest.h3Index);
        const current = useEchelonStore.getState().viewState;
        setViewState({
          ...current,
          longitude: lng,
          latitude: lat,
          zoom: Math.max(6, current.zoom ?? 2),
          pitch: 0,
          bearing: 0,
        });
      } catch {
        // Ignore malformed cells in fly-to logic.
      }
    };

    flyToHighest();
    const interval = setInterval(flyToHighest, 60_000);
    return () => clearInterval(interval);
  }, [theaterMode, tiles, setViewState]);

  const useHex = (viewState.zoom ?? 2) >= 5;
  const tileGeoJSON = useMemo(() => tilesToGeoJSON(tiles, useHex), [tiles, useHex]);
  const signalGeoJSON = useMemo(() => signalsToGeoJSON(signals), [signals]);
  const imageryFootprintsGeoJSON = useMemo(
    () => imageryOpen ? imageryScenesToGeoJSON(imageryScenes) : { type: "FeatureCollection", features: [] },
    [imageryOpen, imageryScenes],
  );

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
          zScore: props.zScore,
          heading: props.heading,
          callsign: props.callsign,
          originCountry: props.originCountry,
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

    if (props.sceneId) {
      setImageryOpen(true);
      setSelectedSceneId(String(props.sceneId));
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

  const handleAnalyzeScene = useCallback((scene: ImageryScene) => {
    setSelectedSceneId(scene.id);
    setAnalyzingSceneId(scene.id);
    imageryApi.analyze({
      itemUrl: scene.itemUrl,
      bbox: scene.bbox ?? currentBbox,
    })
      .then(setImageryAnalysis)
      .catch(() => setImageryAnalysis(null))
      .finally(() => setAnalyzingSceneId(null));
  }, [currentBbox]);

  return (
    <div style={{ position: "relative", flex: 1, height: "100%" }}>
      <Map
        ref={mapRef}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        onMouseMove={handleMouseMove}
        mapStyle={getBasemapStyleUrl(basemapStyle)}
        attributionControl={false}
        interactiveLayerIds={["convergence-hex-fill", "convergence-circles", "signal-dots", "opensky-aircraft", "imagery-footprints-outline"]}
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onLoad={() => {
          const map = mapRef.current?.getMap();
          if (!map) return;
          void ensureAircraftIcon(map);
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
          {/* H3 hex fill — rendered as polygons at zoom >= 5, circles at global */}
          <Layer
            id="convergence-hex-fill"
            type="fill"
            filter={["==", ["geometry-type"], "Polygon"]}
            paint={{
              "fill-color": [
                "interpolate", ["linear"], ["get", "zScore"],
                0, "#1e3a5f",
                1, "#2563eb",
                2, "#eab308",
                3, "#f97316",
                5, "#dc2626",
                10, "#7f1d1d",
              ],
              "fill-opacity": ["interpolate", ["linear"], ["get", "zScore"], 0, 0.35, 1, 0.55, 3, 0.75, 5, 0.85],
            }}
          />
          {/* Hex outline — solid for normal, dashed for low confidence */}
          <Layer
            id="convergence-hex-outline"
            type="line"
            filter={["all", ["==", ["geometry-type"], "Polygon"], ["!=", ["get", "lowConfidence"], true]]}
            paint={{
              "line-color": "rgba(255,255,255,0.3)",
              "line-width": 1,
            }}
          />
          <Layer
            id="convergence-hex-outline-low"
            type="line"
            filter={["all", ["==", ["geometry-type"], "Polygon"], ["==", ["get", "lowConfidence"], true]]}
            paint={{
              "line-color": "rgba(234,179,8,0.6)",
              "line-width": 1.5,
              "line-dasharray": [3, 2],
            }}
          />
          {/* Fallback circles at global zoom (< 5) */}
          <Layer
            id="convergence-circles"
            type="circle"
            filter={["==", ["geometry-type"], "Point"]}
            paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 3.5, 4, 6],
              "circle-color": [
                "interpolate", ["linear"], ["get", "zScore"],
                0, "#1e3a5f",
                1, "#2563eb",
                2, "#eab308",
                3, "#f97316",
                5, "#dc2626",
                10, "#7f1d1d",
              ],
              "circle-opacity": ["interpolate", ["linear"], ["get", "zScore"], 0, 0.5, 1, 0.7, 3, 0.9],
              "circle-stroke-width": ["case", ["==", ["get", "lowConfidence"], true], 1.5, 0.5],
              "circle-stroke-color": ["case",
                ["==", ["get", "lowConfidence"], true], "rgba(234,179,8,0.6)",
                "rgba(255,255,255,0.2)",
              ],
            }}
          />
        </Source>

        <Source id="ais-tracks" type="geojson" data={aisTracks}>
          <Layer
            id="ais-tracks-line"
            type="line"
            paint={{
              "line-color": "rgba(59,130,246,0.65)",
              "line-width": ["interpolate", ["linear"], ["zoom"], 4, 1, 8, 2, 12, 3.5],
              "line-opacity": ["interpolate", ["linear"], ["zoom"], 4, 0.25, 8, 0.5, 12, 0.7],
            }}
          />
        </Source>

        <Source id="flight-tracks" type="geojson" data={flightTracks}>
          <Layer
            id="flight-tracks-line"
            type="line"
            paint={{
              "line-color": "rgba(34,211,238,0.75)",
              "line-width": ["interpolate", ["linear"], ["zoom"], 4, 1, 8, 2.2, 12, 3],
              "line-opacity": ["interpolate", ["linear"], ["zoom"], 4, 0.3, 8, 0.55, 12, 0.78],
            }}
            layout={{
              "line-cap": "round",
              "line-join": "round",
            }}
          />
        </Source>

        <Source id="imagery-footprints" type="geojson" data={imageryFootprintsGeoJSON}>
          <Layer
            id="imagery-footprints-fill"
            type="fill"
            paint={{
              "fill-color": [
                "match", ["get", "provider"],
                "capella", "rgba(14,165,233,0.16)",
                "rgba(249,115,22,0.14)",
              ],
              "fill-opacity": 1,
            }}
          />
          <Layer
            id="imagery-footprints-outline"
            type="line"
            paint={{
              "line-color": [
                "match", ["get", "provider"],
                "capella", "#38bdf8",
                "#fb923c",
              ],
              "line-width": ["interpolate", ["linear"], ["zoom"], 4, 1, 8, 1.6, 12, 2.2],
              "line-opacity": 0.85,
            }}
          />
        </Source>

        {/* ── Signal events ──────────────────────────────────────────── */}
        <Source id="signals" type="geojson" data={signalGeoJSON}>
          {/* Signal dots — sized by source weight, colored by source */}
          <Layer
            id="signal-dots"
            type="circle"
            filter={["!=", ["get", "source"], "opensky"]}
            paint={{
              "circle-radius": [
                "interpolate", ["linear"], ["zoom"],
                4, ["*", ["get", "sourceWeight"], 12],
                8, ["*", ["get", "sourceWeight"], 18],
                12, ["*", ["get", "sourceWeight"], 24],
              ],
              "circle-color": [
                "match", ["get", "source"],
                "gdelt", "#ef4444",
                "gfw", "#2563eb",
                "newsdata", "#d97706",
                "osm", "#059669",
                "osint_scrape", "#b45309",
                "firms", "#ea580c",
                "aisstream", "#1d4ed8",
                "sentinel2", "#7c3aed",
                "#64748b",
              ],
              "circle-opacity": 0.88,
              "circle-stroke-width": 0.75,
              "circle-stroke-color": "rgba(255,255,255,0.35)",
            }}
          />
          <Layer
            id="opensky-aircraft"
            type="symbol"
            filter={["==", ["get", "source"], "opensky"]}
            layout={{
              "icon-image": AIRCRAFT_ICON_ID,
              "icon-size": ["interpolate", ["linear"], ["zoom"], 4, 0.42, 8, 0.62, 12, 0.84],
              "icon-allow-overlap": true,
              "icon-ignore-placement": true,
              "icon-rotation-alignment": "map",
              "icon-rotate": ["coalesce", ["to-number", ["get", "heading"]], 0],
              "text-field": ["get", "callsignLabel"],
              "text-size": ["interpolate", ["linear"], ["zoom"], 4, 9, 10, 11],
              "text-font": ["Open Sans Semibold", "Arial Unicode MS Regular"],
              "text-offset": [1.2, 0],
              "text-anchor": "left",
              "text-allow-overlap": true,
              "text-ignore-placement": true,
            }}
            paint={{
              "text-color": "#f8fafc",
              "text-halo-color": "rgba(15,23,42,0.92)",
              "text-halo-width": 1.6,
              "text-halo-blur": 0.6,
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

      <button
        onClick={() => setImageryOpen((open) => !open)}
        style={{
          position: "absolute",
          top: 72,
          left: 12,
          padding: "9px 12px",
          borderRadius: 10,
          border: "1px solid rgba(148,163,184,0.18)",
          background: "rgba(15,23,42,0.88)",
          color: "var(--color-text-secondary)",
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          cursor: "pointer",
          backdropFilter: "blur(10px)",
          zIndex: 10,
        }}
      >
        {imageryOpen ? "Hide Imagery" : "Open Imagery"}
      </button>

      <ImageryPanel
        open={imageryOpen}
        provider={imageryProvider}
        loading={imageryLoading}
        scenes={imageryScenes}
        selectedSceneId={selectedSceneId}
        analysis={imageryAnalysis}
        analyzingSceneId={analyzingSceneId}
        onClose={() => setImageryOpen(false)}
        onProviderChange={(provider) => {
          setImageryProvider(provider);
          setSelectedSceneId(null);
          setImageryAnalysis(null);
        }}
        onRefresh={() => setImageryRefreshKey((value) => value + 1)}
        onSelectScene={(sceneId) => setSelectedSceneId(sceneId)}
        onAnalyze={handleAnalyzeScene}
      />

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

function convergenceAssessment(z: number): { label: string; color: string; description: string } {
  if (z >= 5) return { label: "CRITICAL", color: "#dc2626", description: "Extreme multi-source convergence — immediate review recommended" };
  if (z >= 3) return { label: "HIGH", color: "#f97316", description: "Strong convergence across multiple independent sources" };
  if (z >= 2) return { label: "ELEVATED", color: "#eab308", description: "Above-baseline activity from several sources" };
  if (z >= 1) return { label: "MODERATE", color: "#2563eb", description: "Slightly above historical baseline" };
  return { label: "BASELINE", color: "#64748b", description: "Activity within normal range for this cell" };
}

function ConvergencePopup({ data, lat, lng }: { data: Record<string, unknown>; lat: number; lng: number }) {
  const z = Number(data.zScore) || 0;
  const low = Boolean(data.lowConfidence);
  const assessment = convergenceAssessment(z);

  return (
    <div style={{ fontFamily: "Inter, system-ui, sans-serif", fontSize: 12, lineHeight: 1.6, minWidth: 240 }}>
      {/* Severity header with colored bar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8, marginBottom: 6,
        paddingBottom: 6, borderBottom: `2px solid ${assessment.color}`,
      }}>
        <span style={{
          fontSize: 10, fontWeight: 800, letterSpacing: "0.06em",
          color: assessment.color, fontFamily: "var(--font-mono)",
        }}>
          {assessment.label}
        </span>
        <span style={{ fontSize: 18, fontWeight: 700, color: "#f1f5f9", fontFamily: "var(--font-mono)" }}>
          {z.toFixed(2)}
        </span>
        <span style={{ fontSize: 10, color: "#94a3b8" }}>Z-score</span>
      </div>

      {/* Plain-language description */}
      <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 8, lineHeight: 1.5 }}>
        {assessment.description}
      </div>

      {/* Key facts */}
      <PopupRow label="Location" value={`${lat.toFixed(4)}, ${lng.toFixed(4)}`} mono />
      <PopupRow label="H3 Cell" value={String(data.h3Index).slice(0, 12) + "..."} mono />

      {low && (
        <div style={{
          marginTop: 6, fontSize: 10, color: "#eab308",
          padding: "4px 8px", background: "rgba(234,179,8,0.1)",
          borderRadius: 4, border: "1px solid rgba(234,179,8,0.2)",
        }}>
          Low confidence — fewer than 30 baseline observations
        </div>
      )}

      {/* Action button */}
      <div style={{
        marginTop: 8, padding: "6px 0", textAlign: "center",
        fontSize: 11, fontWeight: 600, color: "#3b82f6",
        borderTop: "1px solid rgba(148,163,184,0.15)",
        cursor: "pointer",
      }}>
        Investigate signals in this cell &rarr;
      </div>
    </div>
  );
}

function relativeTime(isoString: string): string {
  try {
    const ms = Date.now() - new Date(isoString).getTime();
    if (ms < 0) return "just now";
    const mins = Math.floor(ms / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch { return isoString; }
}

function SignalPopup({ data, lat, lng }: { data: Record<string, unknown>; lat: number; lng: number }) {
  const source = String(data.source || "");
  const signalType = String(data.signalType || "");
  const title = String(data.title || signalType.replace(/_/g, " "));
  const titleDirection = String(data.textDirection || "ltr") === "rtl" ? "rtl" : "ltr";
  const occurredAt = String(data.occurredAt || "");
  const provenance = String(data.provenance || "");
  const detail1 = String(data.detail1 || "");
  const detail2 = String(data.detail2 || "");
  const url = String(data.url || "");

  const srcMeta = SOURCE_COLORS[source] || { color: "#94a3b8", label: source, weight: 0.1 };

  return (
    <div style={{ fontFamily: "Inter, system-ui, sans-serif", fontSize: 12, lineHeight: 1.6, minWidth: 250 }}>
      {/* Source tag — colored bar top */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 6, paddingBottom: 5,
        borderBottom: `2px solid ${srcMeta.color}`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{
            width: 10, height: 10, borderRadius: "50%",
            background: srcMeta.color, flexShrink: 0,
            border: "1.5px solid rgba(255,255,255,0.3)",
          }} />
          <span style={{ fontSize: 10, fontWeight: 700, color: srcMeta.color, letterSpacing: "0.04em", textTransform: "uppercase" }}>
            {srcMeta.label}
          </span>
        </div>
        {occurredAt && (
          <span style={{ fontSize: 10, color: "#94a3b8", fontFamily: "var(--font-mono)" }}>
            {relativeTime(occurredAt)}
          </span>
        )}
      </div>

      {/* Title */}
      <div dir={titleDirection} style={{ fontWeight: 600, fontSize: 13, color: "#f1f5f9", marginBottom: 4, lineHeight: 1.4 }}>
        {title.length > 80 ? title.slice(0, 77) + "..." : title}
      </div>

      {/* Signal type */}
      <div style={{ fontSize: 11, color: "#64748b", marginBottom: 6 }}>
        {signalType.replace(/_/g, " ")}
      </div>

      {/* Details */}
      {detail1 && <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 2 }}>{detail1}</div>}
      {detail2 && <div style={{ fontSize: 11, color: "#64748b", marginBottom: 4 }}>{detail2}</div>}

      {/* Metadata row */}
      <div style={{
        display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap",
        marginTop: 4, marginBottom: 4,
      }}>
        {provenance && (
          <span style={{
            fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 3,
            background: provenance.includes("wire") ? "rgba(16,185,129,0.15)" : "rgba(148,163,184,0.12)",
            color: provenance.includes("wire") ? "#10b981" : "#94a3b8",
            textTransform: "uppercase", letterSpacing: "0.04em",
          }}>
            {provenance.replace(/_/g, " ")}
          </span>
        )}
        <span style={{ fontSize: 10, color: "#64748b", fontFamily: "var(--font-mono)" }}>
          {lat.toFixed(4)}, {lng.toFixed(4)}
        </span>
      </div>

      {occurredAt && (
        <div style={{ fontSize: 10, color: "#64748b" }}>
          {(() => { try { return format(new Date(occurredAt), "MMM d, yyyy HH:mm") + " UTC"; } catch { return occurredAt; } })()}
        </div>
      )}

      {/* Actions */}
      <div style={{
        display: "flex", gap: 12, marginTop: 8, paddingTop: 6,
        borderTop: "1px solid rgba(148,163,184,0.15)",
      }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "#3b82f6", cursor: "pointer" }}>
          View detail &rarr;
        </span>
        {url && (
          <a href={url} target="_blank" rel="noopener noreferrer" style={{
            fontSize: 11, fontWeight: 600, color: "#64748b", textDecoration: "none",
          }}>
            Source &nearr;
          </a>
        )}
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

function MapLegend({ tileCount, signalCount }: { tileCount: number; signalCount: number }) {
  const [collapsed, setCollapsed] = useState(false);
  const legendHeading: React.CSSProperties = {
    fontSize: 8, fontWeight: 700, color: "var(--color-text-muted)",
    textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4, marginTop: 8,
  };

  return (
    <div style={{
      position: "absolute", bottom: 40, left: 12,
      background: "rgba(17,24,39,0.94)", border: "1px solid var(--color-border)",
      borderRadius: 8, backdropFilter: "blur(8px)",
      overflow: "hidden", minWidth: collapsed ? 80 : 170,
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
          {/* Convergence Z-Score ramp with labeled breakpoints */}
          <div style={legendHeading}>Convergence Z-Score</div>
          <div style={{ display: "flex", height: 10, borderRadius: 2, overflow: "hidden", marginBottom: 2 }}>
            {Z_RAMP.map((stop, i) => (
              <div key={i} style={{ flex: 1, background: stop.color }} />
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 8, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
            {Z_RAMP.map((stop) => (
              <span key={stop.z}>{stop.label}</span>
            ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
            <div style={{ width: 14, height: 8, border: "1.5px dashed rgba(234,179,8,0.7)", borderRadius: 1 }} />
            <span style={{ fontSize: 8, color: "var(--color-text-muted)" }}>Low confidence (&lt;30 obs)</span>
          </div>

          {/* Signal sources — all types, dot size reflects weight */}
          <div style={legendHeading}>Signal Sources</div>
          {Object.entries(SOURCE_COLORS).map(([, meta]) => (
            <div key={meta.label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
              <div style={{
                width: 4 + meta.weight * 16,
                height: 4 + meta.weight * 16,
                borderRadius: "50%",
                background: meta.color,
                flexShrink: 0,
                border: "0.5px solid rgba(255,255,255,0.25)",
              }} />
              <span style={{ fontSize: 9, color: "var(--color-text-secondary)" }}>{meta.label}</span>
            </div>
          ))}

          {/* Track lines */}
          <div style={legendHeading}>Tracks</div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
            <div style={{ width: 18, height: 0, borderTop: "2px solid rgba(59,130,246,0.65)" }} />
            <span style={{ fontSize: 9, color: "var(--color-text-secondary)" }}>AIS Vessel</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
            <div style={{ width: 18, height: 0, borderTop: "2px solid rgba(34,211,238,0.75)" }} />
            <span style={{ fontSize: 9, color: "var(--color-text-secondary)" }}>ADS-B Flight</span>
          </div>

          {/* Counts */}
          <div style={{ marginTop: 6, fontSize: 8, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
            {tileCount} cells | {signalCount} signals
          </div>
        </div>
      )}
    </div>
  );
}

// ── GeoJSON builders ──────────────────────────────────────────────────────────

function tilesToGeoJSON(tiles: ConvergenceTile[], useHex: boolean): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: tiles.map(t => {
      if (useHex) {
        // Render as H3 hex polygon
        try {
          const boundary = cellToBoundary(t.h3Index);
          // h3 returns [lat, lng] pairs — flip to [lng, lat] for GeoJSON
          const ring = boundary.map(([la, ln]) => [ln, la]);
          ring.push(ring[0]); // close the ring
          return {
            type: "Feature" as const,
            geometry: { type: "Polygon" as const, coordinates: [ring] },
            properties: { h3Index: t.h3Index, zScore: t.zScore, rawScore: t.rawScore, lowConfidence: t.lowConfidence },
          };
        } catch { /* fall through to point */ }
      }
      // Fallback: centroid point at global zoom
      let lat = 0, lng = 0;
      try { const [la, ln] = cellToLatLng(t.h3Index); lat = la; lng = ln; } catch { /* skip */ }
      return {
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [lng, lat] },
        properties: { h3Index: t.h3Index, zScore: t.zScore, rawScore: t.rawScore, lowConfidence: t.lowConfidence },
      };
    }).filter(f => {
      if (f.geometry.type === "Point") return f.geometry.coordinates[0] !== 0;
      return true;
    }),
  };
}

function imageryScenesToGeoJSON(scenes: ImageryScene[]): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  for (const scene of scenes) {
    if (!scene.geometry) continue;
    features.push({
      type: "Feature",
      geometry: scene.geometry,
      properties: {
        sceneId: scene.id,
        provider: scene.provider,
        title: scene.title,
      },
    });
  }

  return {
    type: "FeatureCollection",
    features,
  };
}

function signalsToGeoJSON(signals: SignalEvent[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: signals.map(s => {
      const p = s.rawPayload || {};
      const title = getDisplayTitle(s, s.signalType.replace(/_/g, " "));
      const detailDescription = getDisplayDescription(s);
      const textDirection = hasTranslation(s) ? "ltr" : textDirectionForRecord(s);

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
      if (detailDescription) {
        detail1 = detail1 || detailDescription.slice(0, 100);
      }
      const heading = asNumber(p.heading);
      const callsign = asString(p.callsign);
      const originCountry = asString(p.origin_country);
      const flag = countryFlagForName(originCountry);
      const callsignLabel = callsign
        ? [flag, callsign].filter(Boolean).join(" ")
        : [flag, originCountry].filter(Boolean).join(" ");
      const zScore = asNumber(p.z_score) ?? asNumber(p.zScore) ?? asNumber(p.zscore);

      return {
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [s.location.lng, s.location.lat] },
        properties: {
          signalId: s.id,
          source: s.source,
          sourceWeight: SOURCE_COLORS[s.source]?.weight ?? 0.1,
          signalType: s.signalType,
          title,
          textDirection,
          zScore: zScore ?? 0,
          heading: heading ?? 0,
          callsign: callsign || "",
          originCountry: originCountry || "",
          callsignLabel: callsignLabel || originCountry || "",
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

function viewportToBbox(viewState: { longitude?: number; latitude?: number; zoom?: number }): [number, number, number, number] {
  const zoom = viewState.zoom ?? 2;
  const span = 360 / Math.pow(2, zoom);
  const lon = viewState.longitude ?? 0;
  const lat = viewState.latitude ?? 0;
  return [
    lon - span / 2,
    Math.max(-85, lat - span / 2),
    lon + span / 2,
    Math.min(85, lat + span / 2),
  ];
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

async function ensureAircraftIcon(map: any): Promise<void> {
  if (map.hasImage(AIRCRAFT_ICON_ID)) return;
  const image = await loadAircraftSvgImage();
  if (!map.hasImage(AIRCRAFT_ICON_ID)) {
    map.addImage(AIRCRAFT_ICON_ID, image, { pixelRatio: 2 });
  }
}

function loadAircraftSvgImage(): Promise<HTMLImageElement> {
  const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <g transform="translate(32 32)">
    <path d="M-1 -26 L4 -5 L14 -2 L14 2 L4 1 L0 14 L4 19 L4 24 L0 22 L-4 24 L-4 19 L0 14 L-4 1 L-14 2 L-14 -2 L-4 -5 Z"
      fill="rgba(2,6,23,0.55)" transform="translate(1 2)"/>
    <path d="M0 -27 L5 -6 L16 -3 L16 3 L5 1 L1 15 L5 21 L5 26 L0 23 L-5 26 L-5 21 L-1 15 L-5 1 L-16 3 L-16 -3 L-5 -6 Z"
      fill="#ffffff"/>
  </g>
</svg>`;
  const src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  return new Promise((resolve, reject) => {
    const image = new Image(64, 64);
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Failed to load aircraft icon"));
    image.src = src;
  });
}
