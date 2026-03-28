/**
 * EventFeed — compact live feed of recent significant signals.
 * Fixed to bottom-right of the map. Shows latest events globally.
 * Click an event to fly to its location.
 */
import { useState, useEffect } from "react";
import { useEchelonStore } from "@/store/echelonStore";
import { signalsApi, type SignalEvent } from "@/services/api";
import { format } from "date-fns";

const FEED_REFRESH_MS = 60_000; // 1 minute

const SOURCE_COLORS: Record<string, string> = {
  gdelt: "#f04444",
  gfw: "#2d8cf0",
  newsdata: "#e5a400",
  osm: "#00c48c",
  sentinel2: "#9333ea",
  opensky: "#06b6d4",
};

export default function EventFeed() {
  const { setViewState, dateRange } = useEchelonStore();
  const [events, setEvents] = useState<SignalEvent[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const fetch = () => {
      signalsApi
        .getForBbox(
          [-180, -90, 180, 90],
          "",
          dateRange.from.toISOString().split("T")[0],
          dateRange.to.toISOString().split("T")[0]
        )
        .then((data) => setEvents(data.slice(0, 15)))
        .catch(() => {});
    };
    fetch();
    const interval = setInterval(fetch, FEED_REFRESH_MS);
    return () => clearInterval(interval);
  }, [dateRange]);

  const flyTo = (event: SignalEvent) => {
    setViewState({
      longitude: event.location.lng,
      latitude: event.location.lat,
      zoom: 9,
      pitch: 0,
      bearing: 0,
    });
  };

  return (
    <div
      style={{
        position: "absolute",
        bottom: 32,
        right: 16,
        width: 300,
        maxHeight: collapsed ? 36 : 340,
        background: "rgba(13,19,32,0.92)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        overflow: "hidden",
        backdropFilter: "blur(8px)",
        transition: "max-height 0.2s",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "8px 12px",
          background: "none",
          border: "none",
          borderBottom: collapsed ? "none" : "1px solid var(--color-border)",
          color: "var(--color-text-primary)",
          cursor: "pointer",
          width: "100%",
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Live Feed
        </span>
        <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
          {collapsed ? "▲" : "▼"} {events.length}
        </span>
      </button>

      {/* Events */}
      {!collapsed && (
        <div style={{ flex: 1, overflow: "auto" }}>
          {events.length === 0 ? (
            <div style={{ padding: 16, textAlign: "center", color: "var(--color-text-muted)", fontSize: 11 }}>
              No recent signals
            </div>
          ) : (
            events.map((event) => {
              const color = SOURCE_COLORS[event.source] || "#7c8db5";
              return (
                <button
                  key={event.id}
                  onClick={() => flyTo(event)}
                  style={{
                    display: "flex",
                    gap: 8,
                    padding: "6px 12px",
                    background: "none",
                    border: "none",
                    borderBottom: "1px solid rgba(30,45,70,0.5)",
                    color: "var(--color-text-primary)",
                    cursor: "pointer",
                    width: "100%",
                    textAlign: "left",
                    fontSize: 11,
                    lineHeight: 1.4,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-surface-hover)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
                >
                  <div style={{ width: 4, borderRadius: 2, background: color, flexShrink: 0, alignSelf: "stretch" }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 4 }}>
                      <span style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {_feedTitle(event)}
                      </span>
                      <span style={{ fontSize: 9, color: "var(--color-text-muted)", flexShrink: 0, fontFamily: "var(--font-mono)" }}>
                        {event.occurredAt ? format(new Date(event.occurredAt), "HH:mm") : ""}
                      </span>
                    </div>
                    <div style={{ fontSize: 10, color: "var(--color-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {_feedDetail(event)}
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

function _feedTitle(event: SignalEvent): string {
  const p = event.rawPayload || {};
  switch (event.signalType) {
    case "gdelt_conflict": return "Conflict event";
    case "gdelt_gkg_threat": return (p.title as string)?.slice(0, 50) || "Threat signal";
    case "gfw_ais_gap": return "Vessel went dark";
    case "gfw_loitering": return "Vessel loitering";
    case "newsdata_article": return (p.title as string)?.slice(0, 50) || "News";
    case "osm_change": return `${(p.infra_type as string || "").replace(/_/g, " ")}`;
    case "opensky_military": return `Military: ${p.callsign || "unknown"}`;
    default: return event.signalType.replace(/_/g, " ");
  }
}

function _feedDetail(event: SignalEvent): string {
  const p = event.rawPayload || {};
  if (p.origin_country) return `${p.origin_country}`;
  if (p.source) return `${p.source}`;
  if (p.country && Array.isArray(p.country)) return (p.country as string[]).join(", ");
  return `${event.location.lat.toFixed(2)}, ${event.location.lng.toFixed(2)}`;
}
