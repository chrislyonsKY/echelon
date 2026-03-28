/**
 * EventDetail — modal/panel showing full detail for a single signal event.
 * Supports permalink via ?signal=<id> URL parameter.
 * Shows related signals in the same H3 cell for event clustering context.
 */
import { type CSSProperties, useState, useEffect } from "react";
import { apiClient } from "@/services/api";
import { useEchelonStore } from "@/store/echelonStore";
import { format } from "date-fns";
import EvidenceTab from "./EvidenceTab";
import { countryForCoordinates } from "@/utils/countries";
import { corroborationBadgeFromCount } from "@/utils/symbology";
import {
  getDisplayDescription,
  getDisplayTitle,
  getOriginalDescription,
  getOriginalTitle,
  hasTranslation,
  languageLabel,
  textDirectionForRecord,
} from "@/utils/language";

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
  language?: string;
  textDirection?: string;
  translationStatus?: string;
  titleOriginal?: string | null;
  descriptionOriginal?: string | null;
  titleTranslated?: string | null;
  descriptionTranslated?: string | null;
  displayTitle?: string | null;
  displayDescription?: string | null;
  relatedSignals: Array<{
    id: string;
    source: string;
    signalType: string;
    location: { lat: number; lng: number };
    occurredAt: string | null;
    weight: number;
    provenanceFamily?: string;
    confirmationPolicy?: string;
    language?: string;
    textDirection?: string;
    titleOriginal?: string | null;
    descriptionOriginal?: string | null;
    titleTranslated?: string | null;
    descriptionTranslated?: string | null;
    displayTitle?: string | null;
    displayDescription?: string | null;
    rawPayload: Record<string, unknown>;
  }>;
}

export default function EventDetail() {
  const { setViewState, openCountryOverview } = useEchelonStore();
  const [event, setEvent] = useState<EventDetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"detail" | "evidence">("detail");

  // Check URL for ?signal=<id> permalink on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const signalId = params.get("signal");
    if (signalId) loadEvent(signalId);
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
      url.searchParams.set("signal", id);
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
    url.searchParams.delete("signal");
    window.history.replaceState({}, "", url.toString());
  };

  const copyPermalink = () => {
    if (!event) return;
    const url = `${window.location.origin}?signal=${event.id}`;
    navigator.clipboard.writeText(url);
  };

  if (!event && !loading) return null;

  const displayTitle = event ? getDisplayTitle(event, event.signalType.replace(/_/g, " ")) : "";
  const displayDescription = event ? getDisplayDescription(event) : null;
  const originalTitle = event ? getOriginalTitle(event) : null;
  const originalDescription = event ? getOriginalDescription(event) : null;
  const translated = event ? hasTranslation(event) : false;
  const textDirection = event ? textDirectionForRecord(event) : "ltr";
  const contentDirection = translated ? "ltr" : textDirection;
  const showOriginalBlock = translated && ((originalTitle && originalTitle !== displayTitle) || originalDescription);
  const hiddenPayloadFields = new Set([
    "title",
    "description",
    "title_original",
    "description_original",
    "title_translated",
    "description_translated",
    "language",
    "language_name",
    "text_direction",
    "translation_status",
  ]);
  const country = event ? countryForCoordinates(event.location.lat, event.location.lng) : null;
  const sourceFamilyCount = event
    ? new Set(
        [event, ...event.relatedSignals]
          .map((s) => (s.provenanceFamily || s.source || "").trim())
          .filter(Boolean)
      ).size || 1
    : 1;
  const confidence = corroborationBadgeFromCount(sourceFamilyCount);

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
              <div dir={contentDirection} style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text-primary)" }}>
                {displayTitle}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3, flexWrap: "wrap" }}>
                <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
                  {event.signalType.replace(/_/g, " ")} | {event.source} | {event.occurredAt ? format(new Date(event.occurredAt), "MMM d, yyyy HH:mm") : ""}
                </span>
                {country && (
                  <button
                    type="button"
                    onClick={() => openCountryOverview(country.name)}
                    style={{
                      border: "1px solid var(--color-border)",
                      borderRadius: 999,
                      background: "transparent",
                      color: "var(--color-text-secondary)",
                      padding: "0 7px",
                      cursor: "pointer",
                      fontSize: 9,
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {country.flag} {country.name}
                  </button>
                )}
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    fontSize: 9,
                    fontWeight: 700,
                    fontFamily: "var(--font-mono)",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    borderRadius: 999,
                    border: `1px solid ${confidence.color}88`,
                    background: `${confidence.color}1a`,
                    color: confidence.color,
                    padding: "1px 8px",
                  }}
                >
                  <span aria-hidden>{confidence.icon}</span>
                  <span>{confidence.label}</span>
                </span>
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
                <Badge label={event.provenanceFamily.replace(/_/g, " ")} color="#3b82f6" />
              )}
              {event.confirmationPolicy && (
                <Badge label={event.confirmationPolicy.replace(/_/g, " ")} color={
                  event.confirmationPolicy === "wire_confirmed" ? "#10b981" :
                  event.confirmationPolicy === "context_only" ? "#f59e0b" : "#94a3b8"
                } />
              )}
            </div>
          )}

          {(displayDescription || event.language || showOriginalBlock) && (
            <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--color-border)" }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
                Content
              </div>
              {event.language && (
                <div style={{ display: "flex", gap: 6, marginBottom: displayDescription || showOriginalBlock ? 8 : 0, flexWrap: "wrap" }}>
                  <Badge label={languageLabel(event.language)} color="#8b5cf6" />
                  {translated && <Badge label="TRANSLATED" color="#8b5cf6" />}
                </div>
              )}
              {displayDescription && (
                <div dir={contentDirection} style={{ fontSize: 11, color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
                  {displayDescription}
                </div>
              )}
              {showOriginalBlock && (
                <div
                  style={{
                    marginTop: 10,
                    padding: "8px 10px",
                    borderRadius: 4,
                    background: "rgba(51,65,85,0.22)",
                    border: "1px solid rgba(71,85,105,0.35)",
                  }}
                >
                  <div style={{ fontSize: 9, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                    Original ({languageLabel(event.language)})
                  </div>
                  {originalTitle && originalTitle !== displayTitle && (
                    <div dir={textDirection} style={{ fontSize: 11, fontWeight: 500, color: "var(--color-text-primary)", marginBottom: originalDescription ? 4 : 0 }}>
                      {originalTitle}
                    </div>
                  )}
                  {originalDescription && (
                    <div dir={textDirection} style={{ fontSize: 10, color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                      {originalDescription}
                    </div>
                  )}
                </div>
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
              if (k === "metadata" || hiddenPayloadFields.has(k) || v === null || v === "") return null;
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
                  background: "none", border: "none", borderBottom: "1px solid rgba(51,65,85,0.3)",
                  color: "var(--color-text-primary)", cursor: "pointer", textAlign: "left", fontSize: 11,
                }}>
                  <SourceDot source={r.source} />
                  <div style={{ flex: 1 }}>
                    <span dir={hasTranslation(r) ? "ltr" : textDirectionForRecord(r)} style={{ fontWeight: 500 }}>
                      {getDisplayTitle(r, r.signalType.replace(/_/g, " "))}
                    </span>
                    {r.provenanceFamily && (
                      <span style={{ marginLeft: 4, fontSize: 8, padding: "1px 3px", borderRadius: 3, background: "rgba(59,130,246,0.15)", color: "#60a5fa" }}>
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
  gdelt: "#ef4444", gfw: "#3b82f6", newsdata: "#f59e0b",
  osm: "#10b981", opensky: "#06b6d4", osint_scrape: "#f59e0b",
};

function SourceDot({ source }: { source: string }) {
  return (
    <span style={{
      width: 6, height: 6, borderRadius: "50%", flexShrink: 0, marginTop: 5,
      background: SOURCE_COLORS[source] || "#94a3b8",
    }} />
  );
}

const btnStyle: CSSProperties = {
  padding: "3px 8px", borderRadius: 4, border: "1px solid var(--color-border)",
  background: "none", color: "var(--color-text-secondary)", cursor: "pointer", fontSize: 10,
};
