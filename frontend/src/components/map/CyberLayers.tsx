/**
 * CyberLayers — toggle panel for cyber-GEOINT data layers.
 *
 * Free layers (no key): submarine cables, data centers, IXPs
 * BYOK layers: Shodan devices, Censys hosts, WiGLE WiFi/cells
 *
 * All IP geolocation results show accuracy warnings.
 */
import { useState, type RefObject } from "react";
import type { MapRef } from "react-map-gl/maplibre";
import { useEchelonStore } from "@/store/echelonStore";
import { apiClient } from "@/services/api";

interface CyberResult {
  lat: number;
  lng: number;
  name?: string;
  type: string;
  [key: string]: unknown;
}

interface CyberLayer {
  id: string;
  label: string;
  color: string;
  free: boolean;
  description: string;
}

const LAYERS: CyberLayer[] = [
  { id: "submarine-cables", label: "Submarine Cables", color: "#2d8cf0", free: true, description: "TeleGeography cable landing points" },
  { id: "data-centers", label: "Data Centers", color: "#9333ea", free: true, description: "PeeringDB colocation facilities" },
  { id: "shodan", label: "Shodan Devices", color: "#f04444", free: false, description: "Exposed IoT/servers (BYOK)" },
  { id: "wigle-wifi", label: "WiFi Networks", color: "#00c48c", free: false, description: "WiGLE WiFi mapping (BYOK)" },
  { id: "wigle-cells", label: "Cell Towers", color: "#e5a400", free: false, description: "WiGLE cell towers (BYOK)" },
];

interface Props {
  mapRef: RefObject<MapRef | null>;
}

export default function CyberLayers({ mapRef }: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const { viewState } = useEchelonStore();

  const toggle = async (layer: CyberLayer) => {
    const map = mapRef.current?.getMap();
    if (!map) return;

    if (active.has(layer.id)) {
      // Remove layer
      if (map.getLayer(`cyber-${layer.id}`)) map.removeLayer(`cyber-${layer.id}`);
      if (map.getSource(`cyber-${layer.id}`)) map.removeSource(`cyber-${layer.id}`);
      setActive((prev) => { const next = new Set(prev); next.delete(layer.id); return next; });
      return;
    }

    setLoading(layer.id);
    try {
      const results = await fetchCyberData(layer.id, viewState);
      if (!results.length) {
        setLoading(null);
        return;
      }

      // Add as GeoJSON source + circle layer
      const geojson: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: results.map((r) => ({
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [r.lng, r.lat] },
          properties: { name: r.name || r.type, type: r.type },
        })),
      };

      if (map.getSource(`cyber-${layer.id}`)) map.removeSource(`cyber-${layer.id}`);
      map.addSource(`cyber-${layer.id}`, { type: "geojson", data: geojson });
      map.addLayer({
        id: `cyber-${layer.id}`,
        type: "circle",
        source: `cyber-${layer.id}`,
        paint: {
          "circle-radius": 5,
          "circle-color": layer.color,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#fff",
          "circle-opacity": 0.8,
        },
      });

      setActive((prev) => new Set(prev).add(layer.id));

      // Show IP geolocation warning for device layers
      if (["shodan", "censys"].includes(layer.id)) {
        setWarning("IP geolocation is approximate. Pins may show ISP default locations, not actual device positions.");
        setTimeout(() => setWarning(null), 8000);
      }
    } catch (err) {
      console.error(`Cyber layer ${layer.id} failed:`, err);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div style={{ position: "absolute", top: 84, left: 12, zIndex: 5 }}>
      <button
        onClick={() => setOpen(!open)}
        title="Cyber-GEOINT layers"
        style={{
          padding: "6px 10px", borderRadius: 6, border: "none", fontSize: 10, fontWeight: 600,
          cursor: "pointer",
          background: active.size > 0 ? "rgba(147,51,234,0.15)" : "var(--color-surface)",
          color: active.size > 0 ? "#9333ea" : "var(--color-text-muted)",
          boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
        }}
      >
        Cyber {active.size > 0 && `(${active.size})`}
      </button>

      {open && (
        <div style={{
          marginTop: 4, padding: 8, borderRadius: 6, minWidth: 220,
          background: "rgba(13,19,32,0.92)", border: "1px solid var(--color-border)",
          backdropFilter: "blur(8px)", boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
        }}>
          <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>
            Cyber Infrastructure
          </div>
          {LAYERS.map((layer) => (
            <button
              key={layer.id}
              onClick={() => toggle(layer)}
              disabled={loading === layer.id}
              title={layer.description}
              style={{
                display: "flex", alignItems: "center", gap: 8, width: "100%",
                padding: "5px 6px", borderRadius: 4, border: "none",
                background: active.has(layer.id) ? `${layer.color}22` : "transparent",
                color: active.has(layer.id) ? "var(--color-text-primary)" : "var(--color-text-secondary)",
                cursor: "pointer", fontSize: 11, textAlign: "left",
                opacity: loading === layer.id ? 0.5 : 1,
              }}
            >
              <span style={{
                width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                background: active.has(layer.id) ? layer.color : "var(--color-border)",
              }} />
              <span style={{ flex: 1 }}>{layer.label}</span>
              {!layer.free && (
                <span style={{ fontSize: 7, padding: "1px 3px", borderRadius: 2, background: "var(--color-accent-muted)", color: "var(--color-accent)" }}>
                  BYOK
                </span>
              )}
            </button>
          ))}
          <div style={{ fontSize: 8, color: "var(--color-text-muted)", marginTop: 6, lineHeight: 1.4 }}>
            BYOK layers require API keys set in copilot settings.
            Free layers load instantly.
          </div>
        </div>
      )}

      {/* IP geolocation warning toast */}
      {warning && (
        <div style={{
          position: "fixed", top: 60, left: "50%", transform: "translateX(-50%)",
          padding: "8px 16px", borderRadius: 6, maxWidth: 400, zIndex: 50,
          background: "rgba(229,164,0,0.15)", border: "1px solid rgba(229,164,0,0.3)",
          fontSize: 10, color: "#e5a400", textAlign: "center",
        }}>
          {warning}
        </div>
      )}
    </div>
  );
}

async function fetchCyberData(layerId: string, viewState: any): Promise<CyberResult[]> {
  const lat = viewState.latitude ?? 20;
  const lng = viewState.longitude ?? 0;
  const zoom = viewState.zoom ?? 2;
  const span = 180 / Math.pow(2, zoom);

  switch (layerId) {
    case "submarine-cables": {
      const data = await apiClient.get<{ results: CyberResult[] }>("/cyber/infrastructure/submarine-cables");
      return data.results;
    }
    case "data-centers": {
      const data = await apiClient.get<{ results: CyberResult[] }>("/cyber/infrastructure/data-centers");
      return data.results;
    }
    case "shodan": {
      const key = localStorage.getItem("echelon:shodan-key");
      if (!key) { alert("Set your Shodan API key in browser localStorage: echelon:shodan-key"); return []; }
      const data = await apiClient.get<{ results: CyberResult[] }>(
        `/cyber/shodan/search?lat=${lat}&lng=${lng}&radius_km=100`,
        { headers: { "X-Shodan-Key": key } } as any,
      );
      return data.results;
    }
    case "wigle-wifi": {
      const name = localStorage.getItem("echelon:wigle-name");
      const token = localStorage.getItem("echelon:wigle-token");
      if (!name || !token) { alert("Set WiGLE credentials: echelon:wigle-name and echelon:wigle-token in localStorage"); return []; }
      const data = await apiClient.get<{ results: CyberResult[] }>(
        `/cyber/wigle/wifi?lat_min=${lat - span}&lat_max=${lat + span}&lng_min=${lng - span}&lng_max=${lng + span}`,
        { headers: { "X-WiGLE-Name": name, "X-WiGLE-Token": token } } as any,
      );
      return data.results;
    }
    case "wigle-cells": {
      const name = localStorage.getItem("echelon:wigle-name");
      const token = localStorage.getItem("echelon:wigle-token");
      if (!name || !token) { alert("Set WiGLE credentials in localStorage"); return []; }
      const data = await apiClient.get<{ results: CyberResult[] }>(
        `/cyber/wigle/cells?lat_min=${lat - span}&lat_max=${lat + span}&lng_min=${lng - span}&lng_max=${lng + span}`,
        { headers: { "X-WiGLE-Name": name, "X-WiGLE-Token": token } } as any,
      );
      return data.results;
    }
    default:
      return [];
  }
}
