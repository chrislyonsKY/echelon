/**
 * InvestigationSidebar
 *
 * Opens when user clicks an H3 cell. Shows narrative summary of what's
 * happening in that cell — events, vessel activity, news — in plain language.
 *
 * Accessibility: Escape closes.
 */
import { useCallback, useEffect, useState } from "react";
import { useEchelonStore } from "@/store/echelonStore";
import { signalsApi, type SignalEvent } from "@/services/api";
import { format } from "date-fns";
import { getDisplayTitle, hasTranslation, textDirectionForRecord } from "@/utils/language";
import LayerPanel from "./LayerPanel";
import EventsPanel from "../EventsPanel";

const SOURCE_META: Record<string, { label: string; color: string; icon: string }> = {
  gdelt:    { label: "GDELT",              color: "#ef4444", icon: "!" },
  gfw:      { label: "Global Fishing Watch", color: "#3b82f6", icon: "~" },
  newsdata: { label: "News",              color: "#f59e0b", icon: "#" },
  osm:      { label: "Infrastructure",    color: "#10b981", icon: "+" },
  sentinel2:{ label: "Sentinel-2",        color: "#9333ea", icon: "*" },
  opensky:  { label: "Air Traffic",       color: "#06b6d4", icon: "^" },
};

export default function InvestigationSidebar() {
  const { selectedCell, setSelectedCell, setSidebarOpen, sidebarTab, setSidebarTab, dateRange } = useEchelonStore();
  const [events, setEvents] = useState<SignalEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const tab = sidebarTab;

  const handleClose = useCallback(() => {
    setSelectedCell(null);
    setSidebarOpen(false);
  }, [setSelectedCell, setSidebarOpen]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleClose]);

  // Fetch events when cell is selected
  useEffect(() => {
    if (!selectedCell) {
      setEvents([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    signalsApi
      .getForCell(
        selectedCell.h3Index,
        dateRange.from.toISOString().split("T")[0],
        dateRange.to.toISOString().split("T")[0]
      )
      .then((data) => setEvents(data))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [selectedCell, dateRange]);

  // Group events by source
  const grouped: Record<string, SignalEvent[]> = {};
  for (const e of events) {
    (grouped[e.source] ??= []).push(e);
  }

  return (
    <aside
      aria-label="Investigation sidebar"
      style={{
        width: "var(--sidebar-width)",
        height: "100%",
        background: "var(--color-surface)",
        borderLeft: "1px solid var(--color-border)",
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--color-border)", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--color-text-muted)", fontWeight: 600, marginBottom: 4 }}>
            {selectedCell ? "Cell Investigation" : "Global Events"}
          </div>
          {selectedCell ? (
            <>
              <div style={{ fontSize: 12, color: "var(--color-text-secondary)", fontFamily: "var(--font-mono)" }}>
                {selectedCell.h3Index}
              </div>
              <div style={{ marginTop: 6, display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{
                  display: "inline-block", padding: "2px 8px", borderRadius: 4, fontSize: 11,
                  fontWeight: 600, fontFamily: "var(--font-mono)",
                  background: "var(--color-accent-muted)", color: "var(--color-accent)",
                  border: "1px solid rgba(45,140,240,0.3)",
                }}>
                  {events.length} signal{events.length !== 1 ? "s" : ""}
                </span>
                {Object.keys(grouped).length > 1 && (
                  <span style={{ fontSize: 10, color: "var(--color-warning)" }}>
                    {Object.keys(grouped).length} sources converging
                  </span>
                )}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>
              Regional event clusters for the current date range
            </div>
          )}
        </div>
        <button onClick={handleClose} aria-label="Close" style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 18, padding: 4 }}>
          ×
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--color-border)" }}>
        {(["activity", "events", "layers"] as const).map((t) => (
          <button
            key={t}
            disabled={!selectedCell && t !== "events"}
            onClick={() => setSidebarTab(t)}
            style={{
            flex: 1, padding: "8px", background: "none", border: "none",
            borderBottom: tab === t ? "2px solid var(--color-accent)" : "2px solid transparent",
            color: tab === t ? "var(--color-text-primary)" : "var(--color-text-muted)",
            cursor: !selectedCell && t !== "events" ? "not-allowed" : "pointer",
            opacity: !selectedCell && t !== "events" ? 0.5 : 1,
            fontSize: 11, fontWeight: tab === t ? 600 : 400,
            textTransform: "uppercase", letterSpacing: "0.05em",
          }}
          >
            {t === "activity" ? "Activity" : t === "events" ? "Events" : "Layers"}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {tab === "layers" ? (
          selectedCell ? (
            <LayerPanel />
          ) : (
            <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
              Select a convergence cell to inspect layer-level signals.
            </div>
          )
        ) : tab === "events" ? (
          <EventsPanel />
        ) : loading ? (
          <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
            <span style={{ animation: "pulse 1.5s infinite" }}>Loading signals...</span>
          </div>
        ) : events.length === 0 ? (
          <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
            No signals in this cell for the selected date range.
          </div>
        ) : (
          <div style={{ padding: "12px 0" }}>
            {/* Narrative summary */}
            <div style={{ padding: "0 16px 12px", fontSize: 12, color: "var(--color-text-secondary)", lineHeight: 1.6, borderBottom: "1px solid var(--color-border)" }}>
              {_buildNarrative(grouped)}
            </div>

            {/* Event cards by source */}
            {Object.entries(grouped).map(([source, sourceEvents]) => {
              const meta = SOURCE_META[source] || { label: source, color: "#94a3b8", icon: "?" };
              return (
                <div key={source} style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <div style={{ padding: "10px 16px 6px", display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: meta.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 10, fontWeight: 600, color: meta.color, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                      {meta.label}
                    </span>
                    <span style={{ fontSize: 10, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                      {sourceEvents.length}
                    </span>
                  </div>
                  {sourceEvents.slice(0, 5).map((event) => (
                    <EventCard key={event.id} event={event} color={meta.color} />
                  ))}
                  {sourceEvents.length > 5 && (
                    <div style={{ padding: "4px 16px 10px", fontSize: 10, color: "var(--color-text-muted)" }}>
                      +{sourceEvents.length - 5} more
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}

function EventCard({ event, color }: { event: SignalEvent; color: string }) {
  const payload = event.rawPayload || {};
  const title = _getEventTitle(event);
  const detail = _getEventDetail(payload);
  const provenance = event.confirmationPolicy || event.provenanceFamily;
  const titleDirection = hasTranslation(event) ? "ltr" : textDirectionForRecord(event);

  return (
    <div style={{ padding: "6px 16px 6px 28px", fontSize: 11, lineHeight: 1.5 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <span dir={titleDirection} style={{ color: "var(--color-text-primary)", fontWeight: 500, display: "flex", alignItems: "center", gap: 4 }}>
          {title}
          {provenance && (
            <span style={{ fontSize: 8, fontWeight: 700, padding: "1px 4px", borderRadius: 3, background: _provenanceColor(provenance) + "22", color: _provenanceColor(provenance), border: `1px solid ${_provenanceColor(provenance)}44` }}>
              {_provenanceLabel(provenance)}
            </span>
          )}
        </span>
        <span style={{ color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", fontSize: 10, flexShrink: 0 }}>
          {event.occurredAt ? format(new Date(event.occurredAt), "MMM d HH:mm") : ""}
        </span>
      </div>
      {detail && <div style={{ color: "var(--color-text-secondary)", fontSize: 10, marginTop: 1 }}>{detail}</div>}
      {typeof payload.url === "string" && payload.url && (
        <a href={payload.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 10, color, textDecoration: "none" }}>
          Source →
        </a>
      )}
    </div>
  );
}

function _getEventTitle(event: SignalEvent): string {
  const p = event.rawPayload || {};
  const displayTitle = getDisplayTitle(event);
  switch (event.signalType) {
    case "gdelt_conflict": return `Conflict event (CAMEO ${p.EventCode || "?"})`;
    case "gdelt_gkg_threat": return displayTitle || `Threat article (${(p.themes as string[])?.join(", ") || "?"})`;
    case "gfw_ais_gap": return "AIS gap — vessel went dark";
    case "gfw_loitering": return "Vessel loitering detected";
    case "newsdata_article": return displayTitle || "News article";
    case "osm_change": return `${((p.infra_type as string) || "infrastructure").replace(/_/g, " ")}${p.name ? `: ${p.name}` : ""}`;
    case "sentinel2_nbr_anomaly": return `EO anomaly — ${((p.anomaly_fraction as number) * 100).toFixed(0)}% disturbed`;
    case "opensky_military": return `Military aircraft${p.callsign ? ` (${p.callsign})` : ""}`;
    default: return displayTitle || event.signalType.replace(/_/g, " ");
  }
}

function _getEventDetail(payload: Record<string, unknown>): string {
  if (payload.GoldsteinScale) return `Goldstein: ${payload.GoldsteinScale}, ${payload.NumArticles || 0} articles`;
  if (payload.vessel && typeof payload.vessel === "object") {
    const v = payload.vessel as Record<string, unknown>;
    return `${v.name || "Unknown"} (${v.flag || "?"})`;
  }
  if (payload.source && payload.provider) return `via ${payload.source} (${payload.provider})`;
  if (payload.source && typeof payload.source === "string" && payload.tone) return `${payload.source} — tone: ${(payload.tone as number).toFixed(1)}`;
  if (payload.origin_country) return `${payload.origin_country}${payload.velocity ? `, ${Math.round(payload.velocity as number)} m/s` : ""}`;
  return "";
}

function _buildNarrative(grouped: Record<string, SignalEvent[]>): string {
  const parts: string[] = [];
  const sources = Object.keys(grouped);

  if (grouped.gdelt) {
    const conflicts = grouped.gdelt.filter((e) => e.signalType === "gdelt_conflict").length;
    const threats = grouped.gdelt.filter((e) => e.signalType === "gdelt_gkg_threat").length;
    if (conflicts) parts.push(`${conflicts} GDELT conflict event${conflicts > 1 ? "s" : ""}`);
    if (threats) parts.push(`${threats} threat-themed article${threats > 1 ? "s" : ""}`);
  }
  if (grouped.gfw) {
    const gaps = grouped.gfw.filter((e) => e.signalType === "gfw_ais_gap").length;
    const loiter = grouped.gfw.filter((e) => e.signalType === "gfw_loitering").length;
    if (gaps) parts.push(`${gaps} AIS gap${gaps > 1 ? "s" : ""} (vessel${gaps > 1 ? "s" : ""} went dark)`);
    if (loiter) parts.push(`${loiter} vessel loitering event${loiter > 1 ? "s" : ""}`);
  }
  if (grouped.newsdata) parts.push(`${grouped.newsdata.length} news article${grouped.newsdata.length > 1 ? "s" : ""}`);
  if (grouped.osm) parts.push(`${grouped.osm.length} infrastructure feature${grouped.osm.length > 1 ? "s" : ""}`);
  if (grouped.opensky) parts.push(`${grouped.opensky.length} military aircraft detection${grouped.opensky.length > 1 ? "s" : ""}`);

  if (parts.length === 0) return "No recent activity in this cell.";
  if (sources.length > 1) return `Multi-source convergence: ${parts.join(", ")}.`;
  return parts.join(", ") + ".";
}

function _provenanceLabel(policy: string): string {
  switch (policy) {
    case "wire_confirmed":
    case "western_wire": return "WIRE";
    case "context_only": return "CTX";
    case "aggregated_context": return "AGG";
    default: return policy.slice(0, 4).toUpperCase();
  }
}

function _provenanceColor(policy: string): string {
  switch (policy) {
    case "wire_confirmed":
    case "western_wire": return "#10b981";
    case "context_only": return "#f59e0b";
    case "aggregated_context": return "#94a3b8";
    default: return "#94a3b8";
  }
}
