/**
 * EventDetail — modal/panel showing full detail for a single signal event.
 * Supports permalink via ?event=<id> URL parameter.
 * Shows related signals in the same H3 cell for event clustering context.
 */
import { useState, useEffect } from "react";
import { apiClient } from "@/services/api";
import { useEchelonStore } from "@/store/echelonStore";
import { format } from "date-fns";
import EvidenceTab from "./EvidenceTab";

interface EventDetailData {
  id: string;
  source: string;
  signalType: string;
  location: { lat: number; lng: number };
  h3: { res5: string; res7: string; res9: string };
  occurredAt: string | null;
  ingestedAt: string | null;
  weight: number;
  sourceId: string;
  rawPayload: Record<string, unknown>;
  provenanceFamily?: string;
  confirmationPolicy?: string;
  relatedSignals: Array<{
    id: string;
    source: string;
    signalType: string;
    location: { lat: number; lng: number };
    occurredAt: string | null;
    weight: number;
    provenanceFamily?: string;
    confirmationPolicy?: string;
  }>;
}

export default function EventDetail() {
  const { setViewState } = useEchelonStore();
  const [event, setEvent] = useState<EventDetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"detail" | "evidence">("detail");

  // Check URL for ?event=<id> permalink on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const eventId = params.get("event");
    if (eventId) loadEvent(eventId);
  }, []);

  // Listen for custom event to open detail
  useEffect(() => {
    const handler = (e: Event) => loadEvent((e as CustomEvent<string>).detail);
    window.addEventListener("echelon:open-event", handler);
    return () => window.removeEventListener("echelon:open-event", handler);
  }, []);

  const loadEvent = async (id: string) => {
    setLoading(true);
    try {
      const data = await apiClient.get<EventDetailData>(`/signals/event/${id}`);
      setEvent(data);
      // Update URL without reload
      const url = new URL(window.location.href);
      url.searchParams.set("event", id);
      window.history.replaceState({}, "", url.toString());
      // Fly to location
      setViewState({
        longitude: data.location.lng,
        latitude: data.location.lat,
        zoom: 10,
        pitch: 0,
        bearing: 0,
      });
    } catch {
      setEvent(null);
    } finally {
      setLoading(false);
    }
  };

  const close = () => {
    setEvent(null);
    const url = new URL(window.location.href);
    url.searchParams.delete("event");
    window.history.replaceState({}, "", url.toString());
  };

  const copyPermalink = () => {
    if (!event) return;
    const url = `${window.location.origin}?event=${event.id}`;
    navigator.clipboard.writeText(url);
  };

  if (!event && !loading) return null;

  return (
    <div style={{
      position: "fixed", top: "var(--topbar-height)", right: 0, bottom: 0, width: 400,
      background: "var(--color-surface)", borderLeft: "1px solid var(--color-border)",
      display: "flex", flexDirection: "column", zIndex: 35, overflow: "auto",
    }}>
      {loading ? (
        <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-muted)" }}>Loading event...</div>
      ) : event && (
        <>
          {/* Header */}
          <div style={{
            padding: "12px 16px", borderBottom: "1px solid var(--color-border)",
            display: "flex", justifyContent: "space-between", alignItems: "flex-start",
          }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text-primary)" }}>
                {event.signalType.replace(/_/g, " ")}
              </div>
              <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 2 }}>
                {event.source} | {event.occurredAt ? format(new Date(event.occurredAt), "MMM d, yyyy HH:mm") : ""}
              </div>
            </div>
            <div style={{ display: "flex", gap: 4 }}>
              <button onClick={copyPermalink} title="Copy permalink" style={btnStyle}>Link</button>
              <button onClick={close} style={btnStyle}>x</button>
            </div>
          </div>

          {/* Tab bar */}
          <div style={{
            display: "flex", borderBottom: "1px solid var(--color-border)",
          }}>
            {(["detail", "evidence"] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)} style={{
                flex: 1, padding: "8px", border: "none", fontSize: 11, fontWeight: 600,
                textTransform: "uppercase", letterSpacing: "0.05em", cursor: "pointer",
                background: tab === t ? "var(--color-accent-muted)" : "none",
                color: tab === t ? "var(--color-accent)" : "var(--color-text-muted)",
                borderBottom: tab === t ? "2px solid var(--color-accent)" : "2px solid transparent",
              }}>
                {t}
              </button>
            ))}
          </div>

          {tab === "evidence" && <EvidenceTab signalId={event.id} />}

          {tab === "detail" && <>
          {/* Provenance */}
          {(event.provenanceFamily || event.confirmationPolicy) && (
            <div style={{ padding: "8px 16px", borderBottom: "1px solid var(--color-border)", display: "flex", gap: 6 }}>
              {event.provenanceFamily && (
                <Badge label={event.provenanceFamily.replace(/_/g, " ")} color="#2d8cf0" />
              )}
              {event.confirmationPolicy && (
                <Badge label={event.confirmationPolicy.replace(/_/g, " ")} color={
                  event.confirmationPolicy === "wire_confirmed" ? "#00c48c" :
                  event.confirmationPolicy === "context_only" ? "#e5a400" : "#7c8db5"
                } />
              )}
            </div>
          )}

          {/* Location */}
          <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--color-border)", fontSize: 11 }}>
            <Row label="Location" value={`${event.location.lat.toFixed(4)}, ${event.location.lng.toFixed(4)}`} />
            <Row label="H3 Cell (r7)" value={event.h3.res7} mono />
            <Row label="Weight" value={event.weight.toFixed(3)} />
            <Row label="Ingested" value={event.ingestedAt ? format(new Date(event.ingestedAt), "MMM d HH:mm:ss") : "—"} />
            {event.sourceId && <Row label="Source ID" value={event.sourceId} mono />}
          </div>

          {/* Payload */}
          <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--color-border)" }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
              Raw Payload
            </div>
            {Object.entries(event.rawPayload || {}).map(([k, v]) => {
              if (k === "metadata" || v === null || v === "") return null;
              const display = typeof v === "object" ? JSON.stringify(v) : String(v);
              return <Row key={k} label={k} value={display.slice(0, 120)} />;
            })}
          </div>

          {/* Related signals */}
          {event.relatedSignals.length > 0 && (
            <div style={{ padding: "10px 16px" }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
                Related ({event.relatedSignals.length} signals in same cell, +-24h)
              </div>
              {event.relatedSignals.map((r) => (
                <button key={r.id} onClick={() => loadEvent(r.id)} style={{
                  display: "flex", gap: 8, padding: "6px 0", width: "100%",
                  background: "none", border: "none", borderBottom: "1px solid rgba(30,45,70,0.3)",
                  color: "var(--color-text-primary)", cursor: "pointer", textAlign: "left", fontSize: 11,
                }}>
                  <SourceDot source={r.source} />
                  <div style={{ flex: 1 }}>
                    <span style={{ fontWeight: 500 }}>{r.signalType.replace(/_/g, " ")}</span>
                    {r.provenanceFamily && (
                      <span style={{ marginLeft: 4, fontSize: 8, padding: "1px 3px", borderRadius: 3, background: "rgba(45,140,240,0.15)", color: "#60a5fa" }}>
                        {r.provenanceFamily.replace(/_/g, " ")}
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: 9, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                    {r.occurredAt ? format(new Date(r.occurredAt), "HH:mm") : ""}
                  </span>
                </button>
              ))}
            </div>
          )}
          </>}
        </>
      )}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", gap: 8 }}>
      <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>{label}</span>
      <span style={{
        fontSize: 10, color: "var(--color-text-secondary)", textAlign: "right",
        fontFamily: mono ? "var(--font-mono)" : "inherit",
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 220,
      }}>
        {value}
      </span>
    </div>
  );
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span style={{
      fontSize: 9, fontWeight: 600, padding: "2px 6px", borderRadius: 4,
      background: `${color}22`, color, border: `1px solid ${color}44`,
    }}>
      {label}
    </span>
  );
}

const SOURCE_COLORS: Record<string, string> = {
  gdelt: "#f04444", gfw: "#2d8cf0", newsdata: "#e5a400",
  osm: "#00c48c", opensky: "#06b6d4", osint_scrape: "#e5a400",
};

function SourceDot({ source }: { source: string }) {
  return (
    <span style={{
      width: 6, height: 6, borderRadius: "50%", flexShrink: 0, marginTop: 5,
      background: SOURCE_COLORS[source] || "#7c8db5",
    }} />
  );
}

const btnStyle: React.CSSProperties = {
  padding: "3px 8px", borderRadius: 4, border: "1px solid var(--color-border)",
  background: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 10,
};
