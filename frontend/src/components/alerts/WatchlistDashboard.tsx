/**
 * WatchlistDashboard — overview of all AOIs with current status at a glance.
 * Shows max Z-score, 7-day signal count, unread alerts, and fly-to action.
 */
import { useState, useEffect } from "react";
import { useEchelonStore } from "@/store/echelonStore";
import { alertsApi, type WatchlistStatus } from "@/services/api";
import { format } from "date-fns";

function statusColor(z: number | null, threshold: number): string {
  if (z === null) return "var(--color-text-muted)";
  if (z >= threshold * 1.5) return "#dc2626";
  if (z >= threshold) return "#f97316";
  if (z >= threshold * 0.7) return "#eab308";
  return "#22c55e";
}

function statusLabel(z: number | null, threshold: number): string {
  if (z === null) return "NO DATA";
  if (z >= threshold * 1.5) return "CRITICAL";
  if (z >= threshold) return "ALERT";
  if (z >= threshold * 0.7) return "WATCH";
  return "NORMAL";
}

export default function WatchlistDashboard() {
  const { user } = useEchelonStore();
  const [items, setItems] = useState<WatchlistStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    alertsApi.getDashboard()
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [user]);

  const flyTo = (geom: GeoJSON.Polygon) => {
    const coords = geom.coordinates[0];
    const lngs = coords.map((c) => c[0]);
    const lats = coords.map((c) => c[1]);
    const center: [number, number] = [
      (Math.min(...lngs) + Math.max(...lngs)) / 2,
      (Math.min(...lats) + Math.max(...lats)) / 2,
    ];
    useEchelonStore.getState().applyMapAction({ type: "fly_to", center, zoom: 7 });
    useEchelonStore.setState({ alertPanelOpen: false });
  };

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
        Loading watchlists...
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
        No watchlists. Create one in the Watchlists tab to start monitoring areas.
      </div>
    );
  }

  return (
    <div style={{ padding: 8 }}>
      {items.map((item) => {
        const color = statusColor(item.maxZScore, item.alertThreshold);
        const label = statusLabel(item.maxZScore, item.alertThreshold);

        return (
          <div
            key={item.id}
            style={{
              padding: "12px 14px",
              margin: "4px 8px",
              borderRadius: 8,
              border: `1px solid ${color}22`,
              background: `${color}08`,
              cursor: "pointer",
            }}
            onClick={() => flyTo(item.geometry)}
            role="button"
            tabIndex={0}
            aria-label={`Fly to ${item.name}`}
            onKeyDown={(e) => e.key === "Enter" && flyTo(item.geometry)}
          >
            {/* Header row */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-primary)" }}>
                {item.name}
              </div>
              <span style={{
                fontSize: 9, fontWeight: 800, letterSpacing: "0.06em",
                color, fontFamily: "var(--font-mono)",
                padding: "1px 6px", borderRadius: 3,
                background: `${color}18`,
              }}>
                {label}
              </span>
            </div>

            {/* Stats row */}
            <div style={{ display: "flex", gap: 14, fontSize: 10, color: "var(--color-text-secondary)" }}>
              <span>
                Z-score:{" "}
                <span style={{ color, fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                  {item.maxZScore !== null ? item.maxZScore.toFixed(2) : "—"}
                </span>
              </span>
              <span>
                Signals (7d):{" "}
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{item.signalCount7d}</span>
              </span>
              {item.unreadAlertCount > 0 && (
                <span style={{ color: "#dc2626", fontWeight: 700 }}>
                  {item.unreadAlertCount} unread
                </span>
              )}
            </div>

            {/* Footer */}
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 9, color: "var(--color-text-muted)" }}>
              <span>Threshold: Z &ge; {item.alertThreshold}</span>
              <span>
                {item.lastAlertAt
                  ? `Last alert: ${format(new Date(item.lastAlertAt), "MMM d HH:mm")}`
                  : "No alerts yet"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
