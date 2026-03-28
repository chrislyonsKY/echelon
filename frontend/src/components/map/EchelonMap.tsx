/**
 * EchelonMap
 *
 * Uses MapLibre GL JS native layers instead of Deck.gl for reliability.
 * Convergence heatmap rendered as circle markers from the API.
 */
import { useRef, useCallback, useEffect, useState } from "react";
import Map, { type MapRef, Source, Layer, type MapLayerMouseEvent } from "react-map-gl/maplibre";
import { useEchelonStore } from "@/store/echelonStore";
import { convergenceApi, signalsApi, type ConvergenceTile, type SignalEvent } from "@/services/api";
import { cellToLatLng } from "h3-js";

const MAPLIBRE_STYLE = "https://tiles.openfreemap.org/styles/dark";
const REFRESH_MS = 15 * 60 * 1000;

export default function EchelonMap() {
  const mapRef = useRef<MapRef>(null);
  const {
    viewState,
    setViewState,
    setSelectedCell,
    activeResolution,
    dateRange,
  } = useEchelonStore();

  const [tiles, setTiles] = useState<ConvergenceTile[]>([]);
  const [signals, setSignals] = useState<SignalEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch convergence tiles
  useEffect(() => {
    const load = () => {
      setIsLoading(true);
      convergenceApi.getTiles(activeResolution)
        .then(data => {
          console.log(`[Echelon] Loaded ${data.length} tiles`);
          setTiles(data);
        })
        .catch(err => console.error("[Echelon] Tile fetch error:", err))
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
    const bbox: [number, number, number, number] = [lon - span/2, lat - span/2, lon + span/2, lat + span/2];

    signalsApi.getForBbox(bbox, "", dateRange.from.toISOString().split("T")[0], dateRange.to.toISOString().split("T")[0])
      .then(data => setSignals(data))
      .catch(() => setSignals([]));
  }, [viewState.zoom, viewState.longitude, viewState.latitude, dateRange]);

  // Convert tiles to GeoJSON using h3 cell centers
  const tileGeoJSON = tilesToGeoJSON(tiles);
  const signalGeoJSON = signalsToGeoJSON(signals);

  const handleClick = useCallback((e: MapLayerMouseEvent) => {
    const feature = e.features?.[0];
    if (!feature?.properties) return;

    const props = feature.properties;
    if (props.h3Index) {
      setSelectedCell({
        h3Index: props.h3Index,
        resolution: activeResolution,
        zScore: props.zScore || 0,
        center: [e.lngLat.lng, e.lngLat.lat],
      });
    }
  }, [activeResolution, setSelectedCell]);

  return (
    <div style={{ position: "relative", flex: 1, height: "100%" }}>
      <Map
        ref={mapRef}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        mapStyle={MAPLIBRE_STYLE}
        attributionControl={false}
        interactiveLayerIds={["convergence-circles"]}
        onClick={handleClick}
        onLoad={() => {
          const map = mapRef.current?.getMap();
          if (!map) return;
          map.getStyle().layers.forEach((layer) => {
            if (layer.type === "symbol" && layer.layout?.["text-field"]) {
              map.setPaintProperty(layer.id, "text-opacity", [
                "interpolate", ["linear"], ["zoom"], 0, 0.15, 4, 0.3, 7, 0.6, 10, 0.85,
              ]);
            }
          });
        }}
      >
        {/* Convergence heatmap as circles */}
        <Source id="convergence" type="geojson" data={tileGeoJSON}>
          <Layer
            id="convergence-circles"
            type="circle"
            paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 4, 5, 8, 8, 14, 12, 20],
              "circle-color": [
                "interpolate", ["linear"], ["get", "score"],
                0, "rgba(26,48,80,0.4)",
                0.1, "rgba(26,48,80,0.7)",
                0.3, "rgba(30,58,95,0.9)",
                0.5, "rgba(229,164,0,0.9)",
                1.0, "rgba(251,113,0,0.9)",
                2.0, "rgba(240,68,68,0.9)",
                4.0, "rgba(147,51,234,0.95)",
              ],
              "circle-opacity": 0.85,
              "circle-blur": 0.3,
            }}
          />
        </Source>

        {/* Signal events as smaller dots */}
        <Source id="signals" type="geojson" data={signalGeoJSON}>
          <Layer
            id="signal-dots"
            type="circle"
            paint={{
              "circle-radius": 4,
              "circle-color": [
                "match", ["get", "source"],
                "gdelt", "#f04444",
                "gfw", "#2d8cf0",
                "newsdata", "#e5a400",
                "osm", "#00c48c",
                "opensky", "#06b6d4",
                "#7c8db5",
              ],
              "circle-opacity": 0.8,
              "circle-stroke-width": 1,
              "circle-stroke-color": "rgba(255,255,255,0.2)",
            }}
          />
        </Source>
      </Map>

      {isLoading && (
        <div role="status" style={{
          position: "absolute", top: 12, left: "50%", transform: "translateX(-50%)",
          background: "rgba(13,19,32,0.9)", color: "var(--color-text-muted)",
          padding: "5px 14px", borderRadius: 6, fontSize: 11,
          border: "1px solid var(--color-border)", backdropFilter: "blur(8px)",
        }}>
          <span style={{ animation: "pulse 1.5s infinite" }}>Loading signals…</span>
        </div>
      )}

      <ConvergenceLegend />
      <SignalLegend />

      <div style={{
        position: "absolute", bottom: 8, right: 320, fontSize: 8,
        color: "var(--color-text-muted)", fontFamily: "var(--font-mono)",
      }}>
        {tiles.length} cells | {signals.length} events
      </div>
    </div>
  );
}

function tilesToGeoJSON(tiles: ConvergenceTile[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: tiles.map(t => {
      let lat = 0, lng = 0;
      try {
        const [la, ln] = cellToLatLng(t.h3Index);
        lat = la; lng = ln;
      } catch { /* skip invalid */ }
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
    features: signals.map(s => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [s.location.lng, s.location.lat] },
      properties: { source: s.source, signalType: s.signalType },
    })),
  };
}

function ConvergenceLegend() {
  return (
    <div aria-label="Convergence legend" style={{
      position: "absolute", bottom: 32, left: 16,
      background: "rgba(13,19,32,0.92)", border: "1px solid var(--color-border)",
      borderRadius: 8, padding: "10px 14px", backdropFilter: "blur(8px)",
    }}>
      <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--color-text-primary)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em" }}>
        Convergence
      </div>
      {[
        { label: "Baseline", color: "#1a3050" },
        { label: "Elevated", color: "#e5a400" },
        { label: "High", color: "#fb7100" },
        { label: "Alert", color: "#f04444" },
        { label: "Extreme", color: "#9333ea" },
      ].map(({ label, color }) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: color, flexShrink: 0 }} />
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--color-text-secondary)" }}>{label}</span>
        </div>
      ))}
    </div>
  );
}

function SignalLegend() {
  return (
    <div style={{
      position: "absolute", bottom: 32, left: 160,
      background: "rgba(13,19,32,0.92)", border: "1px solid var(--color-border)",
      borderRadius: 8, padding: "10px 14px", backdropFilter: "blur(8px)",
    }}>
      <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--color-text-primary)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em" }}>
        Signals
      </div>
      {[
        { label: "Conflict", color: "#f04444" },
        { label: "Maritime", color: "#2d8cf0" },
        { label: "News", color: "#e5a400" },
        { label: "Infrastructure", color: "#00c48c" },
        { label: "Aviation", color: "#06b6d4" },
      ].map(({ label, color }) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0 }} />
          <span style={{ fontSize: 10, color: "var(--color-text-secondary)" }}>{label}</span>
        </div>
      ))}
    </div>
  );
}
