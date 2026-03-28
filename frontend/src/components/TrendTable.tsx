/**
 * TrendTable — Admin1-level trend analysis table.
 * Shows signal counts per type with period-over-period trend,
 * low-baseline suppression, and CSV export.
 */
import { useState, useEffect, useCallback } from "react";
import { useEchelonStore } from "@/store/echelonStore";
import { apiClient } from "@/services/api";

interface TrendRow {
  signalType: string;
  currentCount: number;
  previousCount: number;
  changePct: number;
  trend: "rising" | "falling" | "stable";
  lowBaseline: boolean;
}

const TREND_ICONS: Record<string, { symbol: string; color: string }> = {
  rising: { symbol: "^", color: "var(--color-danger)" },
  falling: { symbol: "v", color: "var(--color-success)" },
  stable: { symbol: "-", color: "var(--color-text-muted)" },
};

const SIGNAL_LABELS: Record<string, string> = {
  gdelt_conflict: "Conflict Events",
  gdelt_gkg_threat: "Threat Articles",
  gfw_ais_gap: "Vessel Dark",
  gfw_loitering: "Vessel Loitering",
  opensky_military: "Military Aircraft",
  sentinel2_nbr_anomaly: "EO Anomalies",
  newsdata_article: "News Articles",
  osm_change: "Infra Changes",
  osint_scrape: "OSINT",
  firms_thermal: "Thermal Anomalies",
  ais_position: "AIS Positions",
  natural_hazard: "Natural Hazards",
};

export default function TrendTable() {
  const { viewState } = useEchelonStore();
  const [trends, setTrends] = useState<TrendRow[]>([]);
  const [days, setDays] = useState(7);
  const [open, setOpen] = useState(false);

  const fetchTrends = useCallback(() => {
    const zoom = viewState.zoom ?? 2;
    const lng = viewState.longitude ?? 0;
    const lat = viewState.latitude ?? 20;

    // Only scope to viewport if zoomed in enough
    let bboxParam = "";
    if (zoom >= 4) {
      const span = 180 / Math.pow(2, zoom);
      bboxParam = `&bbox=${lng - span},${lat - span},${lng + span},${lat + span}`;
    }

    apiClient
      .get<TrendRow[]>(`/convergence/trends?days=${days}${bboxParam}`)
      .then(setTrends)
      .catch(() => setTrends([]));
  }, [viewState, days]);

  useEffect(() => {
    if (open) fetchTrends();
  }, [open, fetchTrends]);

  const exportCsv = () => {
    const header = "Signal Type,Current Period,Previous Period,Change %,Trend,Low Baseline\n";
    const rows = trends.map((t) =>
      `${t.signalType},${t.currentCount},${t.previousCount},${t.changePct},${t.trend},${t.lowBaseline}`
    ).join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `echelon-trends-${days}d.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const totalCurrent = trends.reduce((s, t) => s + t.currentCount, 0);
  const risingCount = trends.filter((t) => t.trend === "rising" && !t.lowBaseline).length;

  return (
    <div style={{ position: "fixed", bottom: 24, left: 180, zIndex: 20 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          padding: "6px 12px", borderRadius: 6,
          border: "1px solid var(--color-border)",
          background: "var(--color-surface)", cursor: "pointer",
          fontSize: 10, fontWeight: 600, fontFamily: "var(--font-mono)",
          color: risingCount > 0 ? "var(--color-danger)" : "var(--color-text-muted)",
        }}
      >
        Trends {risingCount > 0 && `(${risingCount} rising)`}
      </button>

      {open && (
        <div style={{
          position: "absolute", bottom: "100%", left: 0, marginBottom: 8,
          width: 420, maxHeight: 460, overflow: "auto",
          background: "var(--color-surface)", border: "1px solid var(--color-border)",
          borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
        }}>
          {/* Controls */}
          <div style={{
            padding: "8px 14px", borderBottom: "1px solid var(--color-border)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <div style={{ display: "flex", gap: 4 }}>
              {[7, 14, 30].map((d) => (
                <button key={d} onClick={() => setDays(d)} style={{
                  padding: "3px 8px", borderRadius: 4, border: "none", fontSize: 10,
                  fontFamily: "var(--font-mono)", cursor: "pointer",
                  background: days === d ? "var(--color-accent-muted)" : "none",
                  color: days === d ? "var(--color-accent)" : "var(--color-text-muted)",
                }}>
                  {d}d
                </button>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
                {totalCurrent.toLocaleString()} signals
              </span>
              <button onClick={exportCsv} style={{
                padding: "3px 8px", borderRadius: 4, fontSize: 10,
                border: "1px solid var(--color-border)", background: "none",
                color: "var(--color-accent)", cursor: "pointer",
              }}>
                CSV
              </button>
            </div>
          </div>

          {/* Table */}
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                <th style={thStyle}>Signal</th>
                <th style={{ ...thStyle, textAlign: "right" }}>Current</th>
                <th style={{ ...thStyle, textAlign: "right" }}>Previous</th>
                <th style={{ ...thStyle, textAlign: "right" }}>Change</th>
                <th style={{ ...thStyle, textAlign: "center" }}>Trend</th>
              </tr>
            </thead>
            <tbody>
              {trends.map((t) => {
                const trend = TREND_ICONS[t.trend] || TREND_ICONS.stable;
                return (
                  <tr key={t.signalType} style={{
                    borderBottom: "1px solid rgba(30,45,70,0.3)",
                    opacity: t.lowBaseline ? 0.5 : 1,
                  }}>
                    <td style={tdStyle}>
                      {SIGNAL_LABELS[t.signalType] || t.signalType.replace(/_/g, " ")}
                      {t.lowBaseline && (
                        <span title="Low baseline — insufficient data for reliable trends" style={{
                          marginLeft: 4, fontSize: 8, padding: "1px 3px", borderRadius: 3,
                          background: "var(--color-warning)", color: "#000", fontWeight: 700,
                        }}>
                          LOW
                        </span>
                      )}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)" }}>
                      {t.currentCount.toLocaleString()}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
                      {t.previousCount.toLocaleString()}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right", fontFamily: "var(--font-mono)", color: trend.color }}>
                      {t.lowBaseline ? "—" : `${t.changePct > 0 ? "+" : ""}${t.changePct}%`}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "center", color: trend.color, fontWeight: 700 }}>
                      {t.lowBaseline ? "?" : trend.symbol}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {trends.some((t) => t.lowBaseline) && (
            <div style={{ padding: "6px 14px", fontSize: 9, color: "var(--color-text-muted)", fontStyle: "italic" }}>
              LOW = fewer than 30 total observations. Trend data is unreliable for these signal types in this region.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: "6px 14px", textAlign: "left", fontWeight: 600,
  fontSize: 9, textTransform: "uppercase", letterSpacing: "0.05em",
  color: "var(--color-text-muted)",
};

const tdStyle: React.CSSProperties = {
  padding: "6px 14px", color: "var(--color-text-primary)",
};
