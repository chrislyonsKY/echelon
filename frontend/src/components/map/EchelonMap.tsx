/**
 * EchelonMap
 *
 * Primary map canvas. Manages MapLibre GL JS and Deck.gl overlay.
 * All layer data flows from the Zustand store.
 *
 * Layers:
 *   - H3HexagonLayer — convergence heatmap
 *   - ScatterplotLayer — GDELT conflict events (red dots)
 *   - ScatterplotLayer — GFW vessel events (blue diamonds)
 *   - ScatterplotLayer — News/OSINT signals (amber)
 */
import { useRef, useCallback } from "react";
import Map, { type MapRef } from "react-map-gl/maplibre";
import { DeckGL } from "@deck.gl/react";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { ScatterplotLayer } from "@deck.gl/layers";
import { useEchelonStore } from "@/store/echelonStore";
import { useConvergenceTiles, useSignalLayer } from "@/hooks/useConvergenceTiles";
import type { PickingInfo } from "@deck.gl/core";

const MAPLIBRE_STYLE = "https://tiles.openfreemap.org/styles/dark";

function zScoreToColor(zScore: number, lowConfidence: boolean, rawScore?: number): [number, number, number, number] {
  const score = lowConfidence && rawScore !== undefined
    ? rawScore * 3
    : zScore;

  const alpha = lowConfidence ? 140 : 200;
  if (score < 0.1)  return [26,  48,  80,  alpha * 0.4];
  if (score < 0.3)  return [26,  48,  80,  alpha * 0.7];
  if (score < 0.5)  return [30,  58,  95,  alpha];
  if (score < 1.0)  return [229, 164, 0,   alpha];
  if (score < 1.5)  return [251, 113, 0,   alpha];
  if (score < 2.5)  return [240, 68,  68,  alpha];
  return                   [147, 51,  234, alpha];
}

// Signal type → color mapping for event dots
const SIGNAL_COLORS: Record<string, [number, number, number, number]> = {
  gdelt_conflict:    [240, 68,  68,  200],  // red
  gdelt_gkg_threat:  [240, 68,  68,  140],  // red (muted)
  gfw_ais_gap:       [45, 140, 240, 220],   // blue
  gfw_loitering:     [45, 140, 240, 150],   // blue (muted)
  newsdata_article:  [229, 164, 0,   180],  // amber
  osint_scrape:      [229, 164, 0,   140],  // amber (muted)
  osm_change:        [0,  196, 140, 120],   // green
  opensky_military:  [6,  182, 212, 200],   // cyan
  ais_position:      [45, 140, 240, 100],   // blue (subtle)
};

export default function EchelonMap() {
  const mapRef = useRef<MapRef>(null);
  const {
    viewState,
    setViewState,
    setSelectedCell,
    activeResolution,
    layerVisibility,
  } = useEchelonStore();

  const { tiles, isLoading } = useConvergenceTiles(activeResolution);

  // Fetch signal layers for different sources
  const gdeltResult = useSignalLayer("gdelt");
  const gdeltEvents = (gdeltResult as Record<string, unknown>)["gdeltEvents"] as Array<{ location: { lng: number; lat: number }; signalType: string }> ?? [];

  const gfwResult = useSignalLayer("gfw");
  const gfwEvents = (gfwResult as Record<string, unknown>)["gfwEvents"] as Array<{ location: { lng: number; lat: number }; signalType: string }> ?? [];

  const handleCellClick = useCallback(
    (info: PickingInfo) => {
      if (!info.object) return;
      setSelectedCell({
        h3Index: info.object.h3Index,
        resolution: activeResolution,
        zScore: info.object.zScore,
        center: [info.coordinate![0], info.coordinate![1]],
      });
    },
    [activeResolution, setSelectedCell]
  );

  const layers = [
    // Base layer: convergence heatmap
    layerVisibility.convergenceHeatmap &&
      new H3HexagonLayer({
        id: "convergence-heatmap",
        data: tiles,
        getHexagon: (d) => d.h3Index,
        getFillColor: (d) => zScoreToColor(d.zScore, d.lowConfidence, d.rawScore),
        getElevation: () => 0,
        extruded: false,
        pickable: true,
        onClick: handleCellClick,
        updateTriggers: { getFillColor: [tiles] },
      }),

    // GDELT conflict events — red pulsing dots
    layerVisibility.gdeltEvents &&
      new ScatterplotLayer({
        id: "gdelt-events",
        data: gdeltEvents,
        getPosition: (d) => [d.location.lng, d.location.lat],
        getRadius: 6000,
        getFillColor: (d) => SIGNAL_COLORS[d.signalType] || [240, 68, 68, 200],
        getLineColor: [255, 255, 255, 60],
        stroked: true,
        lineWidthMinPixels: 1,
        pickable: true,
        radiusMinPixels: 3,
        radiusMaxPixels: 12,
      }),

    // GFW vessel events — blue markers
    layerVisibility.gfwVessels &&
      new ScatterplotLayer({
        id: "gfw-events",
        data: gfwEvents,
        getPosition: (d) => [d.location.lng, d.location.lat],
        getRadius: 8000,
        getFillColor: (d) => SIGNAL_COLORS[d.signalType] || [45, 140, 240, 200],
        getLineColor: [255, 255, 255, 80],
        stroked: true,
        lineWidthMinPixels: 1,
        pickable: true,
        radiusMinPixels: 4,
        radiusMaxPixels: 14,
      }),
  ].filter(Boolean);

  return (
    <div style={{ position: "relative", flex: 1, height: "100%" }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: vs }) => setViewState(vs as typeof viewState)}
        controller={true}
        layers={layers}
        style={{ position: "absolute", inset: "0" }}
        getTooltip={({ object }) => {
          if (!object) return null;
          // H3 cell tooltip
          if (object.h3Index) {
            const sources = object.signalBreakdown ? Object.keys(object.signalBreakdown) : [];
            return {
              html: `<div class="map-tooltip">
                <strong>${object.lowConfidence ? "Activity Score" : "Z-Score"}: ${object.lowConfidence ? (object.rawScore ?? 0).toFixed(3) : (object.zScore ?? 0).toFixed(2) + "σ"}</strong>
                ${sources.length ? `<div style="margin-top:3px;font-size:10px;color:#7c8db5">${sources.map((s: string) => s.replace(/_/g, " ")).join(" + ")}</div>` : ""}
                ${object.lowConfidence ? "<span class='low-confidence'>Building baseline…</span>" : ""}
                <div style="margin-top:4px;font-size:9px;color:#4a5a7a">Click to investigate</div>
              </div>`,
            };
          }
          // Signal event tooltip
          if (object.signalType) {
            return {
              html: `<div class="map-tooltip">
                <strong>${(object.signalType as string).replace(/_/g, " ")}</strong>
                <div style="font-size:10px;color:#7c8db5">${object.location?.lat?.toFixed(2)}, ${object.location?.lng?.toFixed(2)}</div>
              </div>`,
            };
          }
          return null;
        }}
      >
        <Map
          ref={mapRef}
          mapStyle={MAPLIBRE_STYLE}
          attributionControl={false}
          reuseMaps
          onLoad={() => {
            const map = mapRef.current?.getMap();
            if (!map) return;
            map.getStyle().layers.forEach((layer) => {
              if (layer.type === "symbol" && layer.layout?.["text-field"]) {
                map.setPaintProperty(layer.id, "text-opacity", [
                  "interpolate", ["linear"], ["zoom"], 0, 0.15, 4, 0.3, 7, 0.6, 10, 0.85,
                ]);
                map.setPaintProperty(layer.id, "text-halo-opacity", [
                  "interpolate", ["linear"], ["zoom"], 0, 0.1, 4, 0.2, 7, 0.5, 10, 0.8,
                ]);
              }
            });
          }}
        />
      </DeckGL>

      {isLoading && (
        <div role="status" aria-label="Loading" style={{
          position: "absolute", top: 12, left: "50%", transform: "translateX(-50%)",
          background: "rgba(13,19,32,0.9)", color: "var(--color-text-muted)",
          padding: "5px 14px", borderRadius: 6, fontSize: 11,
          border: "1px solid var(--color-border)", backdropFilter: "blur(8px)",
        }}>
          <span style={{ animation: "pulse 1.5s infinite" }}>Updating convergence…</span>
        </div>
      )}

      <ConvergenceLegend />
      <SignalLegend />

      <div style={{
        position: "absolute", bottom: 8, right: 8, fontSize: 8,
        color: "var(--color-text-muted)", textAlign: "right", lineHeight: 1.4,
        fontFamily: "var(--font-mono)",
      }}>
        GDELT | GFW | OpenSky | OSM | News | OSINT
      </div>
    </div>
  );
}

function ConvergenceLegend() {
  return (
    <div aria-label="Convergence legend" style={{
      position: "absolute", bottom: 32, left: 16,
      background: "rgba(13,19,32,0.92)", border: "1px solid var(--color-border)",
      borderRadius: 8, padding: "10px 14px", fontSize: 11,
      color: "var(--color-text-secondary)", minWidth: 140, backdropFilter: "blur(8px)",
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
          <div style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0, border: "1px solid rgba(255,255,255,0.08)" }} />
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>{label}</span>
        </div>
      ))}
    </div>
  );
}

function SignalLegend() {
  return (
    <div style={{
      position: "absolute", bottom: 32, left: 176,
      background: "rgba(13,19,32,0.92)", border: "1px solid var(--color-border)",
      borderRadius: 8, padding: "10px 14px", fontSize: 11,
      color: "var(--color-text-secondary)", backdropFilter: "blur(8px)",
    }}>
      <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--color-text-primary)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em" }}>
        Signal Layers
      </div>
      {[
        { label: "Conflict", color: "rgb(240,68,68)" },
        { label: "Vessel", color: "rgb(45,140,240)" },
        { label: "News / OSINT", color: "rgb(229,164,0)" },
        { label: "Infrastructure", color: "rgb(0,196,140)" },
        { label: "Military Air", color: "rgb(6,182,212)" },
      ].map(({ label, color }) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0 }} />
          <span style={{ fontSize: 10 }}>{label}</span>
        </div>
      ))}
    </div>
  );
}
