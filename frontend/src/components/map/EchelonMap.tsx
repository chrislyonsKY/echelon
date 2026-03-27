/**
 * EchelonMap
 *
 * Primary map canvas. Manages MapLibre GL JS and Deck.gl overlay.
 * All layer data flows from the Zustand store — this component
 * does not own any data state.
 *
 * Layer rendering:
 *   - H3HexagonLayer (Deck.gl) — convergence heatmap, driven by resolution
 *   - ScatterplotLayer (Deck.gl) — GDELT conflict events
 *   - H3HexagonLayer (Deck.gl) — GFW vessel density
 *   - MVTLayer (Deck.gl) — OSM infrastructure (PMTiles)
 *   - RasterLayer — active Sentinel-2 scene overlay
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

/**
 * Color ramp for convergence Z-scores.
 * Returns [R, G, B, A] for a given Z-score.
 * Low-confidence cells get reduced opacity and hatching (handled in CSS).
 */
function zScoreToColor(zScore: number, lowConfidence: boolean): [number, number, number, number] {
  const alpha = lowConfidence ? 120 : 200;
  if (zScore < 0.5)  return [30,  58,  95,  alpha * 0.3];
  if (zScore < 1.0)  return [30,  58,  95,  alpha * 0.6];
  if (zScore < 1.5)  return [245, 158, 11,  alpha];
  if (zScore < 2.0)  return [251, 113, 0,   alpha];
  if (zScore < 3.0)  return [239, 68,  68,  alpha];
  return                    [124, 58,  237, alpha];    // Extreme — purple
}

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
  const signalLayerResult = useSignalLayer("gdelt");
  const gdeltEvents = (signalLayerResult as Record<string, unknown>)["gdeltEvents"] as Array<{ location: { lng: number; lat: number }; signalType: string }> ?? [];

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
    layerVisibility.convergenceHeatmap &&
      new H3HexagonLayer({
        id: "convergence-heatmap",
        data: tiles,
        getHexagon: (d) => d.h3Index,
        getFillColor: (d) => zScoreToColor(d.zScore, d.lowConfidence),
        getElevation: () => 0,
        extruded: false,
        pickable: true,
        onClick: handleCellClick,
        updateTriggers: {
          getFillColor: [tiles],
        },
      }),

    layerVisibility.gdeltEvents &&
      new ScatterplotLayer({
        id: "gdelt-events",
        data: gdeltEvents,
        getPosition: (d) => [d.location.lng, d.location.lat],
        getRadius: 8000,
        getFillColor: () => [239, 68, 68, 200],
        pickable: true,
        radiusMinPixels: 4,
        radiusMaxPixels: 16,
      }),

    // TODO: GFW vessel H3 density layer
    // TODO: OSM infrastructure MVT layer
    // TODO: Sentinel-2 COG raster layer
  ].filter(Boolean);

  return (
    <div style={{ position: "relative", flex: 1, height: "100%" }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: vs }) => setViewState(vs as typeof viewState)}
        controller={true}
        layers={layers}
        style={{ position: "absolute", inset: "0" }}
        getTooltip={({ object }) =>
          object && {
            html: `<div class="map-tooltip">
              <strong>Z-Score: ${object.zScore?.toFixed(2) ?? "—"}</strong>
              ${object.lowConfidence ? "<span class='low-confidence'>Low confidence</span>" : ""}
            </div>`,
          }
        }
      >
        <Map
          ref={mapRef}
          mapStyle={MAPLIBRE_STYLE}
          attributionControl={false}
          reuseMaps
        />
      </DeckGL>

      {/* Loading indicator */}
      {isLoading && (
        <div
          role="status"
          aria-label="Loading convergence data"
          style={{
            position: "absolute",
            top: 12,
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(17,24,39,0.9)",
            color: "#9ca3af",
            padding: "6px 14px",
            borderRadius: 6,
            fontSize: 12,
          }}
        >
          Updating convergence scores…
        </div>
      )}

      {/* Map legend */}
      <ConvergenceLegend />

      {/* Data sources attribution */}
      <div
        style={{
          position: "absolute",
          bottom: 8,
          right: 8,
          fontSize: 9,
          color: "#4b5563",
          textAlign: "right",
          lineHeight: 1.4,
        }}
      >
        GDELT | GFW | OSM | NewsData | NewsAPI | GNews
      </div>
    </div>
  );
}

function ConvergenceLegend() {
  return (
    <div
      aria-label="Convergence heatmap legend"
      style={{
        position: "absolute",
        bottom: 32,
        left: 16,
        background: "rgba(17,24,39,0.92)",
        border: "1px solid #374151",
        borderRadius: 8,
        padding: "10px 14px",
        fontSize: 11,
        color: "#d1d5db",
        minWidth: 140,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 6, color: "#f9fafb" }}>
        Convergence Z-Score
      </div>
      {[
        { label: "< 1.0σ  Baseline", color: "#1e3a5f" },
        { label: "1.0–1.5σ  Elevated", color: "#f59e0b" },
        { label: "1.5–2.0σ  High", color: "#fb7100" },
        { label: "2.0–3.0σ  Alert", color: "#ef4444" },
        { label: "> 3.0σ  Extreme", color: "#7c3aed" },
      ].map(({ label, color }) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
          <div style={{ width: 12, height: 12, borderRadius: 2, background: color, flexShrink: 0 }} />
          <span>{label}</span>
        </div>
      ))}
      <div style={{ marginTop: 6, borderTop: "1px solid #374151", paddingTop: 6, color: "#6b7280" }}>
        <span style={{ fontStyle: "italic" }}>Hatched = low confidence (&lt;30 obs.)</span>
      </div>
    </div>
  );
}
