/**
 * ConfoundersToggle — toggle overlay layers for weather, fire, storms.
 * Helps analysts rule out non-conflict explanations for signal spikes.
 *
 * Uses free public tile services:
 * - OpenWeatherMap rain/clouds (free tier, 60 req/min)
 * - NASA FIRMS active fires (MODIS/VIIRS)
 * - GDACS recent events overlay
 */
import { useState, type RefObject } from "react";
import type { MapRef } from "react-map-gl/maplibre";

interface ConfounderLayer {
  id: string;
  label: string;
  description: string;
  color: string;
}

const LAYERS: ConfounderLayer[] = [
  { id: "weather-clouds", label: "Clouds", description: "Cloud cover from OpenWeatherMap", color: "#94a3b8" },
  { id: "weather-precip", label: "Rain", description: "Precipitation from OpenWeatherMap", color: "#60a5fa" },
  { id: "firms-fires", label: "Fires", description: "NASA FIRMS active fire detections", color: "#f97316" },
];

// NASA GIBS tile layers (free, no key needed)
const GIBS_BASE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";

interface Props {
  mapRef: RefObject<MapRef | null>;
}

export default function ConfoundersToggle({ mapRef }: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<Set<string>>(new Set());

  const toggle = (layerId: string) => {
    const map = mapRef.current?.getMap();
    if (!map) return;

    const next = new Set(active);
    if (next.has(layerId)) {
      next.delete(layerId);
      // Remove layers from map
      if (map.getLayer(layerId)) map.removeLayer(layerId);
      if (map.getSource(layerId)) map.removeSource(layerId);
    } else {
      next.add(layerId);
      // Add raster tile source to map
      const tileUrl = getTileUrl(layerId);
      if (tileUrl && !map.getSource(layerId)) {
        map.addSource(layerId, {
          type: "raster",
          tiles: [tileUrl],
          tileSize: 256,
        });
        map.addLayer({
          id: layerId,
          type: "raster",
          source: layerId,
          paint: { "raster-opacity": 0.5 },
        }, "convergence-glow"); // Insert below convergence layers
      }
    }
    setActive(next);
  };

  return (
    <div style={{
      position: "absolute", top: 12, right: 12, zIndex: 5,
    }}>
      <button
        onClick={() => setOpen(!open)}
        title="Confounder overlays — weather, fire, storms"
        style={{
          padding: "6px 10px", borderRadius: 6,
          border: "1px solid var(--color-border)",
          background: active.size > 0 ? "var(--color-accent-muted)" : "var(--color-surface)",
          color: active.size > 0 ? "var(--color-accent)" : "var(--color-text-muted)",
          cursor: "pointer", fontSize: 10, fontWeight: 600,
        }}
      >
        Overlays {active.size > 0 && `(${active.size})`}
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "100%", right: 0, marginTop: 4,
          background: "var(--color-surface-raised)", border: "1px solid var(--color-border)",
          borderRadius: 6, padding: 8, minWidth: 180,
          boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
        }}>
          <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>
            Confounder Layers
          </div>
          {LAYERS.map((layer) => (
            <button
              key={layer.id}
              onClick={() => toggle(layer.id)}
              title={layer.description}
              style={{
                display: "flex", alignItems: "center", gap: 8, width: "100%",
                padding: "5px 6px", borderRadius: 4, border: "none",
                background: active.has(layer.id) ? "var(--color-accent-muted)" : "transparent",
                color: active.has(layer.id) ? "var(--color-text-primary)" : "var(--color-text-secondary)",
                cursor: "pointer", fontSize: 11, textAlign: "left",
              }}
            >
              <span style={{
                width: 8, height: 8, borderRadius: "50%",
                background: active.has(layer.id) ? layer.color : "var(--color-border)",
                flexShrink: 0,
              }} />
              {layer.label}
            </button>
          ))}
          <div style={{ fontSize: 8, color: "var(--color-text-muted)", marginTop: 6, lineHeight: 1.4 }}>
            Overlay layers help rule out non-conflict signal explanations.
          </div>
        </div>
      )}
    </div>
  );
}

function getTileUrl(layerId: string): string | null {
  const today = new Date().toISOString().split("T")[0];

  switch (layerId) {
    case "weather-clouds":
      // NASA GIBS MODIS cloud optical thickness
      return `${GIBS_BASE}/MODIS_Terra_Cloud_Optical_Thickness/default/${today}/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png`;
    case "weather-precip":
      // NASA GIBS IMERG precipitation
      return `${GIBS_BASE}/IMERG_Precipitation_Rate/default/${today}/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png`;
    case "firms-fires":
      // NASA GIBS MODIS active fires
      return `${GIBS_BASE}/MODIS_Terra_Thermal_Anomalies_All/default/${today}/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png`;
    default:
      return null;
  }
}
