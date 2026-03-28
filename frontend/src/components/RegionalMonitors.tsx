/**
 * RegionalMonitors — preset region buttons for 1-click navigation.
 * Inspired by Liveuamap's region-specific monitors.
 * Renders as a compact row in the TopBar or as a dropdown.
 */
import { useState, useEffect } from "react";
import { useEchelonStore } from "@/store/echelonStore";
import { apiClient } from "@/services/api";

interface Region {
  name: string;
  center: [number, number]; // [lng, lat]
  zoom: number;
  bbox: string; // west,south,east,north
}

const REGIONS: Region[] = [
  { name: "Ukraine", center: [33.0, 48.5], zoom: 6, bbox: "22,44,40.5,52.5" },
  { name: "Red Sea", center: [40.0, 16.0], zoom: 6, bbox: "32,10,50,22" },
  { name: "Iran", center: [53.0, 32.5], zoom: 6, bbox: "44,25,64,40" },
  { name: "Gaza", center: [34.4, 31.4], zoom: 10, bbox: "34,29,35,32" },
  { name: "Sahel", center: [5.5, 17.5], zoom: 5, bbox: "-5,10,16,25" },
  { name: "SCS", center: [113.5, 13.5], zoom: 5, bbox: "105,5,122,22" },
  { name: "Taiwan", center: [120.0, 23.8], zoom: 7, bbox: "117,21.5,123,26" },
  { name: "Korea", center: [128.0, 38.0], zoom: 7, bbox: "124,33,132,43" },
  { name: "Myanmar", center: [96.8, 19.0], zoom: 6, bbox: "92,9.5,101.5,28.5" },
  { name: "Libya", center: [17.3, 26.5], zoom: 6, bbox: "9,19,25.5,34" },
];

interface TrendData {
  signalType: string;
  currentCount: number;
  trend: string;
}

export default function RegionalMonitors() {
  const { setViewState } = useEchelonStore();
  const [activeRegion, setActiveRegion] = useState<string | null>(null);
  const [trends, setTrends] = useState<TrendData[]>([]);

  const flyTo = (region: Region) => {
    setActiveRegion(region.name);
    setViewState({
      longitude: region.center[0],
      latitude: region.center[1],
      zoom: region.zoom,
      pitch: 0,
      bearing: 0,
    });
    // Fetch trends for this region
    apiClient
      .get<TrendData[]>(`/convergence/trends?bbox=${region.bbox}&days=7`)
      .then(setTrends)
      .catch(() => setTrends([]));
  };

  // Clear trends when deselecting
  useEffect(() => {
    if (!activeRegion) setTrends([]);
  }, [activeRegion]);

  const totalSignals = trends.reduce((sum, t) => sum + t.currentCount, 0);
  const risingCount = trends.filter((t) => t.trend === "rising").length;

  return (
    <div style={{ position: "relative" }}>
      {/* Region buttons — compact row */}
      <div style={{ display: "flex", gap: 2, alignItems: "center" }}>
        {REGIONS.map((region) => (
          <button
            key={region.name}
            onClick={() => flyTo(region)}
            title={region.name}
            style={{
              padding: "3px 7px",
              borderRadius: 4,
              border: "none",
              fontSize: 10,
              fontWeight: 500,
              cursor: "pointer",
              background: activeRegion === region.name ? "var(--color-accent-muted)" : "transparent",
              color: activeRegion === region.name ? "var(--color-accent)" : "var(--color-text-muted)",
              transition: "all 0.15s",
              whiteSpace: "nowrap",
            }}
          >
            {region.name}
          </button>
        ))}
        {activeRegion && (
          <button
            onClick={() => { setActiveRegion(null); setTrends([]); }}
            style={{
              padding: "3px 6px", borderRadius: 4, border: "none", fontSize: 10,
              cursor: "pointer", background: "none", color: "var(--color-text-muted)",
            }}
            title="Clear region"
          >
            x
          </button>
        )}
      </div>

      {/* Trend summary tooltip */}
      {activeRegion && trends.length > 0 && (
        <div style={{
          position: "absolute", top: "100%", left: 0, marginTop: 4, zIndex: 40,
          background: "var(--color-surface-raised)", border: "1px solid var(--color-border)",
          borderRadius: 6, padding: "8px 12px", minWidth: 220, fontSize: 10,
          boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
        }}>
          <div style={{ fontWeight: 600, color: "var(--color-text-primary)", marginBottom: 4 }}>
            {activeRegion} — 7-day summary
          </div>
          <div style={{ color: "var(--color-text-secondary)", marginBottom: 6 }}>
            {totalSignals} signals | {risingCount} rising
          </div>
          {trends.slice(0, 6).map((t) => (
            <div key={t.signalType} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
              <span style={{ color: "var(--color-text-secondary)" }}>{t.signalType.replace(/_/g, " ")}</span>
              <span style={{
                color: t.trend === "rising" ? "var(--color-danger)" : t.trend === "falling" ? "var(--color-success)" : "var(--color-text-muted)",
                fontFamily: "var(--font-mono)",
              }}>
                {t.currentCount} {t.trend === "rising" ? "^" : t.trend === "falling" ? "v" : "-"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
