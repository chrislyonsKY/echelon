/**
 * EventsPanel — clustered events and corroboration metadata.
 */
import { type CSSProperties, useEffect, useMemo, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { useEchelonStore } from "@/store/echelonStore";
import { eventsApi, type EchelonEvent, type EventDetail } from "@/services/api";
import { corroborationBadgeFromCount, severityFromConfirmationStatus, type CorroborationMeta } from "@/utils/symbology";
import { countryForCoordinates } from "@/utils/countries";

const CONFIRMATION_COLORS: Record<string, string> = {
  corroborated: "#10b981",
  multi_source: "#3b82f6",
  single_source: "#f59e0b",
  unconfirmed: "#64748b",
};

const CONFIRMATION_LABELS: Record<string, string> = {
  corroborated: "Corroborated",
  multi_source: "Multi-Source",
  single_source: "Single Source",
  unconfirmed: "Unconfirmed",
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  maritime_anomaly: "Maritime",
  conflict: "Conflict",
  civil_unrest: "Civil Unrest",
  environmental_change: "Environmental",
  infrastructure_change: "Infrastructure",
  military_activity: "Military",
  media_report: "Media",
  natural_event: "Natural",
  unknown: "Activity",
};

const FAMILY_ABBR: Record<string, string> = {
  official_sensor: "SNR",
  curated_dataset: "CUR",
  news_media: "NWS",
  open_source: "OSS",
  crowd_sourced: "CRD",
};

export default function EventsPanel() {
  const {
    selectedEventId,
    setSelectedEventId,
    setSidebarOpen,
    setSidebarTab,
    openCountryOverview,
  } = useEchelonStore();
  const [events, setEvents] = useState<EchelonEvent[]>([]);
  const [detail, setDetail] = useState<EventDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    setLoading(true);
    eventsApi
      .list({ days: 7 })
      .then(setEvents)
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const eventId = params.get("event");
    if (!eventId) return;
    setSidebarOpen(true);
    setSidebarTab("events");
    setSelectedEventId(eventId);
  }, [setSelectedEventId, setSidebarOpen, setSidebarTab]);

  useEffect(() => {
    if (!selectedEventId) {
      setDetail(null);
      return;
    }
    eventsApi
      .getDetail(selectedEventId)
      .then((data) => {
        setDetail(data);
        syncEventParam(data.id);
      })
      .catch(() => setDetail(null));
  }, [selectedEventId]);

  const filtered = useMemo(
    () => (filter === "all" ? events : events.filter((e) => e.confirmationStatus === filter)),
    [events, filter]
  );

  if (detail) {
    return (
      <EventDetailView
        detail={detail}
        onBack={() => {
          setSelectedEventId(null);
          clearEventParam();
        }}
        onCountryClick={openCountryOverview}
      />
    );
  }

  return (
    <div style={{ padding: "12px 0" }}>
      <div style={{ display: "flex", gap: 4, padding: "0 12px 10px", flexWrap: "wrap" }}>
        {["all", "corroborated", "multi_source", "single_source"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: "3px 10px",
              borderRadius: 4,
              border: "1px solid",
              borderColor: filter === f ? "var(--color-accent)" : "var(--color-border)",
              background: filter === f ? "var(--color-accent-muted)" : "transparent",
              color: filter === f ? "var(--color-accent)" : "var(--color-text-secondary)",
              cursor: "pointer",
              fontSize: 11,
              fontWeight: 500,
            }}
          >
            {f === "all" ? "All" : CONFIRMATION_LABELS[f]}
          </button>
        ))}
      </div>

      {loading && (
        <div style={{ padding: "20px 12px", color: "var(--color-text-muted)", fontSize: 12 }}>
          Loading events...
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div style={{ padding: "20px 12px", color: "var(--color-text-muted)", fontSize: 12 }}>
          No events in the last 7 days.
        </div>
      )}

      {filtered.map((event) => {
        const severity = severityFromConfirmationStatus(event.confirmationStatus);
        const country = countryForCoordinates(event.location.lat, event.location.lng);
        return (
          <button
            key={event.id}
            onClick={() => setSelectedEventId(event.id)}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              padding: "10px 12px",
              background: "transparent",
              border: "none",
              borderBottom: "1px solid var(--color-border)",
              cursor: "pointer",
              color: "var(--color-text-primary)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <span
                style={{
                  display: "inline-block",
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: CONFIRMATION_COLORS[event.confirmationStatus] || "#64748b",
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 12, fontWeight: 600, flex: 1, lineHeight: 1.3 }}>
                {EVENT_TYPE_LABELS[event.eventType] || event.eventType}
              </span>
              <SeverityPill label={severity.label} color={severity.color} />
            </div>

            <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 6, lineHeight: 1.4 }}>
              {event.title}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 6, minHeight: 18 }}>
              <CorroborationBadge meta={corroborationBadgeFromCount(event.corroborationCount)} />
              {country && (
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(ev) => {
                    ev.stopPropagation();
                    openCountryOverview(country.name);
                  }}
                  onKeyDown={(ev) => {
                    if (ev.key === "Enter" || ev.key === " ") {
                      ev.preventDefault();
                      ev.stopPropagation();
                      openCountryOverview(country.name);
                    }
                  }}
                  style={countryButtonStyle}
                >
                  {country.flag} {country.name}
                </span>
              )}
              <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                {event.lastSeen ? formatDistanceToNow(new Date(event.lastSeen), { addSuffix: true }) : ""}
              </span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              {event.sourceFamilies.map((fam) => (
                <span
                  key={fam}
                  style={{
                    padding: "1px 5px",
                    borderRadius: 3,
                    background: "var(--color-surface-raised)",
                    border: "1px solid var(--color-border)",
                    fontSize: 9,
                    fontFamily: "var(--font-mono)",
                    color: "var(--color-text-secondary)",
                    fontWeight: 600,
                  }}
                >
                  {FAMILY_ABBR[fam] || fam}
                </span>
              ))}
              <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--color-text-muted)" }}>
                {event.signalCount} signals
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function EventDetailView({
  detail,
  onBack,
  onCountryClick,
}: {
  detail: EventDetail;
  onBack: () => void;
  onCountryClick: (country: string) => void;
}) {
  const country = countryForCoordinates(detail.location.lat, detail.location.lng);
  const confidence = corroborationBadgeFromCount(detail.corroborationCount);

  return (
    <div style={{ padding: 12 }}>
      <button
        onClick={onBack}
        style={{
          background: "none",
          border: "none",
          color: "var(--color-accent)",
          cursor: "pointer",
          fontSize: 12,
          padding: "0 0 8px",
          fontWeight: 500,
        }}
      >
        &larr; Back to events
      </button>

      <div style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
          <span
            style={{
              padding: "2px 8px",
              borderRadius: 999,
              border: `1px solid ${(CONFIRMATION_COLORS[detail.confirmationStatus] || "#64748b")}66`,
              color: CONFIRMATION_COLORS[detail.confirmationStatus] || "#64748b",
              background: `${CONFIRMATION_COLORS[detail.confirmationStatus] || "#64748b"}1f`,
              fontSize: 10,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              fontFamily: "var(--font-mono)",
            }}
          >
            {CONFIRMATION_LABELS[detail.confirmationStatus] || detail.confirmationStatus}
          </span>
          <CorroborationBadge meta={confidence} />
          {country && (
            <button type="button" onClick={() => onCountryClick(country.name)} style={countryButtonStyle}>
              {country.flag} {country.name}
            </button>
          )}
          <button
            onClick={() => navigator.clipboard.writeText(`${window.location.origin}?event=${detail.id}`)}
            style={{
              marginLeft: "auto",
              border: "1px solid var(--color-border)",
              borderRadius: 4,
              background: "transparent",
              color: "var(--color-text-secondary)",
              padding: "2px 8px",
              fontSize: 10,
              fontFamily: "var(--font-mono)",
              cursor: "pointer",
            }}
          >
            LINK
          </button>
        </div>

        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, lineHeight: 1.4 }}>
          {EVENT_TYPE_LABELS[detail.eventType] || detail.eventType}
        </h3>

        <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 4 }}>
          {detail.title}
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "6px 16px",
            marginTop: 10,
            fontSize: 11,
            color: "var(--color-text-muted)",
            fontFamily: "var(--font-mono)",
          }}
        >
          <div>
            First seen: {detail.firstSeen ? new Date(detail.firstSeen).toLocaleString() : "?"}
          </div>
          <div>
            Last seen: {detail.lastSeen ? new Date(detail.lastSeen).toLocaleString() : "?"}
          </div>
          <div>
            Location: {detail.location.lat.toFixed(4)}, {detail.location.lng.toFixed(4)}
          </div>
          <div>
            H3: {detail.h3Index}
          </div>
        </div>

        <div style={{ display: "flex", gap: 4, marginTop: 8 }}>
          {detail.sourceFamilies.map((fam) => (
            <span
              key={fam}
              style={{
                padding: "2px 8px",
                borderRadius: 4,
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
                fontSize: 10,
                fontFamily: "var(--font-mono)",
                color: "var(--color-text-secondary)",
              }}
            >
              {fam.replace("_", " ")}
            </span>
          ))}
        </div>
      </div>

      <h4
        style={{
          fontSize: 12,
          fontWeight: 600,
          borderBottom: "1px solid var(--color-border)",
          paddingBottom: 6,
          marginBottom: 8,
        }}
      >
        Supporting Signals ({detail.signals.length})
      </h4>

      {detail.signals.map((sig) => (
        <div
          key={sig.id}
          style={{
            padding: "6px 0",
            borderBottom: "1px solid var(--color-border)",
            fontSize: 11,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontWeight: 500 }}>
              {sig.source} / {sig.signalType}
            </span>
            <span style={{ color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", fontSize: 10 }}>
              {sig.occurredAt ? new Date(sig.occurredAt).toLocaleString() : "?"}
            </span>
          </div>
          {sig.provenanceFamily && (
            <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
              {sig.provenanceFamily}
              {sig.confirmationPolicy ? ` / ${sig.confirmationPolicy}` : ""}
            </span>
          )}
        </div>
      ))}

      {detail.evidence.length > 0 && (
        <>
          <h4
            style={{
              fontSize: 12,
              fontWeight: 600,
              borderBottom: "1px solid var(--color-border)",
              paddingBottom: 6,
              marginTop: 16,
              marginBottom: 8,
            }}
          >
            Evidence ({detail.evidence.length})
          </h4>

          {detail.evidence.map((ev) => (
            <div
              key={ev.id}
              style={{
                padding: "6px 0",
                borderBottom: "1px solid var(--color-border)",
                fontSize: 11,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontWeight: 500 }}>
                  {ev.type} {ev.platform ? `(${ev.platform})` : ""}
                </span>
                {ev.graphicFlag && (
                  <span style={{ color: "var(--color-danger)", fontSize: 10, fontWeight: 600 }}>
                    GRAPHIC
                  </span>
                )}
              </div>
              {ev.title && (
                <div style={{ color: "var(--color-text-secondary)", marginTop: 2 }}>
                  {ev.title}
                </div>
              )}
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function SeverityPill({ label, color }: { label: string; color: string }) {
  return (
    <span
      style={{
        padding: "1px 6px",
        borderRadius: 999,
        border: `1px solid ${color}`,
        color,
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: "0.06em",
        fontFamily: "var(--font-mono)",
        textTransform: "uppercase",
      }}
    >
      {label}
    </span>
  );
}

function CorroborationBadge({ meta }: { meta: CorroborationMeta }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 8px",
        borderRadius: 999,
        border: `1px solid ${meta.color}88`,
        color: meta.color,
        background: `${meta.color}1a`,
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: "0.05em",
        fontFamily: "var(--font-mono)",
      }}
    >
      <span aria-hidden>{meta.icon}</span>
      <span>{meta.label}</span>
    </span>
  );
}

const countryButtonStyle: CSSProperties = {
  border: "1px solid var(--color-border)",
  borderRadius: 999,
  background: "transparent",
  color: "var(--color-text-secondary)",
  padding: "1px 7px",
  cursor: "pointer",
  fontSize: 9,
  fontFamily: "var(--font-mono)",
};

function syncEventParam(eventId: string) {
  const url = new URL(window.location.href);
  url.searchParams.set("event", eventId);
  window.history.replaceState({}, "", url.toString());
}

function clearEventParam() {
  const url = new URL(window.location.href);
  url.searchParams.delete("event");
  window.history.replaceState({}, "", url.toString());
}
