/**
 * BasemapSwitcher — toggle between satellite, streets, and topographic basemaps.
 * Uses free tile sources (no API key required).
 */
import { useState } from "react";
import { useEchelonStore } from "@/store/echelonStore";

interface BasemapOption {
  id: string;
  label: string;
  url: string;
  preview: string; // CSS gradient as preview
}

const BASEMAPS: BasemapOption[] = [
  {
    id: "dark",
    label: "Dark",
    url: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    preview: "linear-gradient(135deg, #0d1117, #1a2332)",
  },
  {
    id: "satellite",
    label: "Satellite",
    url: "https://api.maptiler.com/maps/hybrid/style.json?key=get_your_own_OpIi9ZULNHzrESv6T2vL",
    preview: "linear-gradient(135deg, #1a3a1a, #0a1a2a)",
  },
  {
    id: "streets",
    label: "Streets",
    url: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    preview: "linear-gradient(135deg, #e8e8e8, #d0d0d0)",
  },
  {
    id: "topo",
    label: "Topo",
    url: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    preview: "linear-gradient(135deg, #f0ebe3, #ddd5c8)",
  },
  {
    id: "osm",
    label: "OSM",
    // OpenFreeMap serves OSM tiles with no key
    url: "https://tiles.openfreemap.org/styles/liberty",
    preview: "linear-gradient(135deg, #f2efe9, #c8d7c5)",
  },
];

export default function BasemapSwitcher() {
  const [open, setOpen] = useState(false);
  const { basemapStyle, setBasemapStyle } = useEchelonStore();
  const current = BASEMAPS.find((b) => b.id === basemapStyle) || BASEMAPS[0];

  return (
    <div style={{ position: "absolute", bottom: 12, right: 12, zIndex: 5 }}>
      <button
        onClick={() => setOpen(!open)}
        title="Change basemap"
        style={{
          width: 48, height: 48, borderRadius: 6, cursor: "pointer",
          border: "2px solid var(--color-border)",
          background: current.preview,
          boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 8, fontWeight: 700, color: current.id === "dark" ? "#94a3b8" : "#333",
          textTransform: "uppercase", letterSpacing: "0.05em",
        }}
      >
        {current.label}
      </button>

      {open && (
        <div style={{
          position: "absolute", bottom: "100%", right: 0, marginBottom: 8,
          display: "flex", gap: 6, padding: 6,
          background: "var(--color-surface)", border: "1px solid var(--color-border)",
          borderRadius: 8, boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
        }}>
          {BASEMAPS.map((bm) => (
            <button
              key={bm.id}
              onClick={() => { setBasemapStyle(bm.id); setOpen(false); }}
              title={bm.label}
              style={{
                width: 48, height: 48, borderRadius: 4, cursor: "pointer",
                border: basemapStyle === bm.id ? "2px solid var(--color-accent)" : "2px solid transparent",
                background: bm.preview,
                display: "flex", alignItems: "flex-end", justifyContent: "center",
                paddingBottom: 3,
              }}
            >
              <span style={{
                fontSize: 7, fontWeight: 700, color: bm.id === "dark" ? "#94a3b8" : "#333",
                textTransform: "uppercase",
              }}>
                {bm.label}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Get the MapLibre style URL for a basemap ID */
export function getBasemapStyleUrl(id: string): string {
  return BASEMAPS.find((b) => b.id === id)?.url || BASEMAPS[0].url;
}
