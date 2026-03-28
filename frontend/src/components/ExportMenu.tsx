/**
 * ExportMenu — dropdown for downloading signals as GeoJSON, KML, or CSV.
 */
import { useState } from "react";
import { useEchelonStore } from "@/store/echelonStore";

const FORMATS = [
  { id: "geojson", label: "GeoJSON", ext: ".geojson", desc: "For QGIS, ArcGIS, web maps" },
  { id: "kml", label: "KML", ext: ".kml", desc: "For Google Earth" },
  { id: "csv", label: "CSV", ext: ".csv", desc: "For spreadsheets, notebooks" },
];

export default function ExportMenu() {
  const [open, setOpen] = useState(false);
  const { dateRange } = useEchelonStore();

  const days = Math.max(1, Math.round((dateRange.to.getTime() - dateRange.from.getTime()) / 86400000));

  const download = (formatId: string) => {
    const url = `/api/export/${formatId}?days=${days}&limit=5000`;
    window.open(url, "_blank");
    setOpen(false);
  };

  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          padding: "4px 10px", borderRadius: 4, border: "none",
          background: "none", cursor: "pointer",
          fontSize: 11, fontWeight: 500, color: "var(--color-text-muted)",
        }}
      >
        Export
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "100%", right: 0, marginTop: 4, zIndex: 50,
          background: "var(--color-surface-raised)", border: "1px solid var(--color-border)",
          borderRadius: 6, padding: 6, minWidth: 180,
          boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
        }}>
          <div style={{ fontSize: 9, color: "var(--color-text-muted)", padding: "4px 8px", marginBottom: 4 }}>
            Export signals ({days}d window)
          </div>
          {FORMATS.map((f) => (
            <button key={f.id} onClick={() => download(f.id)} style={{
              display: "block", width: "100%", textAlign: "left", padding: "6px 8px",
              borderRadius: 4, border: "none", cursor: "pointer",
              background: "transparent", color: "var(--color-text-primary)", fontSize: 11,
            }}>
              <span style={{ fontWeight: 600 }}>{f.label}</span>
              <span style={{ color: "var(--color-text-muted)", fontSize: 9, marginLeft: 6 }}>{f.desc}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
