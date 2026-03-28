/**
 * AlertsPanel — slide-out panel for managing AOI watchlists and viewing alert history.
 * Opens when the alert bell is clicked. Requires authentication.
 */
import { useState, useEffect, useCallback } from "react";
import { useEchelonStore } from "@/store/echelonStore";
import { alertsApi, type AlertRecord, type AOI } from "@/services/api";
import { format } from "date-fns";

export default function AlertsPanel() {
  const { alertPanelOpen, user, setViewState } = useEchelonStore();
  const [tab, setTab] = useState<"alerts" | "watchlists">("alerts");
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [aois, setAois] = useState<AOI[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newThreshold, setNewThreshold] = useState("2.0");
  const [newEmail, setNewEmail] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) return;
    try {
      const [a, w] = await Promise.all([alertsApi.getUnread(), alertsApi.getAois()]);
      setAlerts(a);
      setAois(w);
    } catch { /* non-critical */ }
  }, [user]);

  useEffect(() => {
    if (alertPanelOpen && user) refresh();
  }, [alertPanelOpen, user, refresh]);

  const markRead = async (id: string) => {
    await alertsApi.markRead(id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
    useEchelonStore.setState((s) => ({ unreadAlertCount: Math.max(0, s.unreadAlertCount - 1) }));
  };

  const createAoi = async () => {
    if (!newName.trim()) return;
    const viewState = useEchelonStore.getState().viewState;
    const lng = viewState.longitude ?? 0;
    const lat = viewState.latitude ?? 20;
    const size = 2; // ~2 degree box around viewport center
    const geometry = {
      type: "Polygon" as const,
      coordinates: [[
        [lng - size, lat - size],
        [lng + size, lat - size],
        [lng + size, lat + size],
        [lng - size, lat + size],
        [lng - size, lat - size],
      ]],
    };
    await alertsApi.createAoi({
      name: newName.trim(),
      geometry,
      alertThreshold: parseFloat(newThreshold) || 2.0,
      alertEmail: newEmail,
    });
    setNewName("");
    setShowCreate(false);
    refresh();
  };

  const deleteAoi = async (id: string) => {
    await alertsApi.deleteAoi(id);
    setAois((prev) => prev.filter((a) => a.id !== id));
  };

  if (!alertPanelOpen || !user) return null;

  return (
    <div style={{
      position: "fixed", top: "var(--topbar-height)", right: 0, bottom: 0, width: 360,
      background: "var(--color-surface)", borderLeft: "1px solid var(--color-border)",
      display: "flex", flexDirection: "column", zIndex: 30,
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderBottom: "1px solid var(--color-border)" }}>
        <div style={{ display: "flex", gap: 8 }}>
          {(["alerts", "watchlists"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: "4px 10px", borderRadius: 4, border: "none", fontSize: 11, fontWeight: 600,
              textTransform: "uppercase", letterSpacing: "0.05em", cursor: "pointer",
              background: tab === t ? "var(--color-accent-muted)" : "none",
              color: tab === t ? "var(--color-accent)" : "var(--color-text-muted)",
            }}>
              {t === "alerts" ? `Alerts (${alerts.length})` : `Watchlists (${aois.length})`}
            </button>
          ))}
        </div>
        <button onClick={() => useEchelonStore.setState({ alertPanelOpen: false })} style={{
          background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 16,
        }}>
          x
        </button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: "8px 0" }}>
        {tab === "alerts" && (
          alerts.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
              No unread alerts. Set up watchlists to receive alerts when Z-scores spike in areas you monitor.
            </div>
          ) : (
            alerts.map((alert) => (
              <div key={alert.id} style={{
                padding: "10px 16px", borderBottom: "1px solid var(--color-border)",
                display: "flex", gap: 10, alignItems: "flex-start",
              }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--color-danger)", flexShrink: 0, marginTop: 6 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-primary)" }}>
                    {alert.aoiName}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--color-text-secondary)", marginTop: 2 }}>
                    Z-score: {alert.zScore?.toFixed(2)} | {alert.triggerType}
                  </div>
                  <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 2, fontFamily: "var(--font-mono)" }}>
                    {alert.firedAt ? format(new Date(alert.firedAt), "MMM d HH:mm") : ""}
                  </div>
                </div>
                <button onClick={() => markRead(alert.id)} title="Dismiss" style={{
                  background: "none", border: "1px solid var(--color-border)", borderRadius: 4,
                  color: "var(--color-text-muted)", cursor: "pointer", fontSize: 10, padding: "2px 6px",
                }}>
                  OK
                </button>
              </div>
            ))
          )
        )}

        {tab === "watchlists" && (
          <>
            {aois.map((aoi) => (
              <div key={aoi.id} style={{
                padding: "10px 16px", borderBottom: "1px solid var(--color-border)",
                display: "flex", gap: 10, alignItems: "center",
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-primary)" }}>{aoi.name}</div>
                  <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 2 }}>
                    Threshold: Z &ge; {aoi.alertThreshold} | Email: {aoi.alertEmail ? "on" : "off"}
                  </div>
                </div>
                <button onClick={() => deleteAoi(aoi.id)} title="Delete watchlist" style={{
                  background: "none", border: "1px solid var(--color-border)", borderRadius: 4,
                  color: "var(--color-danger)", cursor: "pointer", fontSize: 10, padding: "2px 6px",
                }}>
                  Del
                </button>
              </div>
            ))}

            {showCreate ? (
              <div style={{ padding: "12px 16px", borderTop: "1px solid var(--color-border)" }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-primary)", marginBottom: 8 }}>
                  New Watchlist
                </div>
                <input
                  placeholder="Name (e.g., Black Sea)"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  style={{
                    width: "100%", padding: "6px 8px", borderRadius: 4, border: "1px solid var(--color-border)",
                    background: "var(--color-bg)", color: "var(--color-text-primary)", fontSize: 12, marginBottom: 6,
                  }}
                />
                <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
                  <label style={{ fontSize: 10, color: "var(--color-text-secondary)" }}>
                    Z-score threshold:
                    <input
                      type="number" step="0.5" min="0.5" max="10" value={newThreshold}
                      onChange={(e) => setNewThreshold(e.target.value)}
                      style={{
                        width: 50, padding: "3px 6px", marginLeft: 4, borderRadius: 4,
                        border: "1px solid var(--color-border)", background: "var(--color-bg)",
                        color: "var(--color-text-primary)", fontSize: 11,
                      }}
                    />
                  </label>
                  <label style={{ fontSize: 10, color: "var(--color-text-secondary)", display: "flex", alignItems: "center", gap: 4 }}>
                    <input type="checkbox" checked={newEmail} onChange={(e) => setNewEmail(e.target.checked)} />
                    Email alerts
                  </label>
                </div>
                <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginBottom: 8 }}>
                  Creates a watchlist centered on your current map viewport.
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button onClick={createAoi} disabled={!newName.trim()} style={{
                    background: "var(--color-accent)", border: "none", borderRadius: 4,
                    color: "#fff", padding: "5px 12px", fontSize: 11, cursor: "pointer",
                    opacity: newName.trim() ? 1 : 0.5,
                  }}>
                    Create
                  </button>
                  <button onClick={() => setShowCreate(false)} style={{
                    background: "none", border: "1px solid var(--color-border)", borderRadius: 4,
                    color: "var(--color-text-muted)", padding: "5px 12px", fontSize: 11, cursor: "pointer",
                  }}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button onClick={() => setShowCreate(true)} style={{
                display: "block", width: "calc(100% - 32px)", margin: "12px 16px", padding: "8px",
                background: "none", border: "1px dashed var(--color-border)", borderRadius: 6,
                color: "var(--color-accent)", cursor: "pointer", fontSize: 11, textAlign: "center",
              }}>
                + Add Watchlist
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
