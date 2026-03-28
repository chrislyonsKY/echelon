/**
 * EventTimeline — chronological signal feed for the selected H3 cell.
 */
import { useSignalEvents } from "@/hooks/useConvergenceTiles";
import type { SelectedCell } from "@/store/echelonStore";
import type { SignalEvent } from "@/services/api";
import { format } from "date-fns";
import { getDisplayTitle, hasTranslation, textDirectionForRecord } from "@/utils/language";

const SOURCE_LABELS: Record<string, string> = {
  acled:     "ACLED",
  gfw:       "Global Fishing Watch",
  sentinel2: "Sentinel-2",
  osm:       "OpenStreetMap",
  gdelt:     "GDELT",
  newsdata:  "NewsData.io",
};

const SOURCE_COLORS: Record<string, string> = {
  acled:     "#ef4444",
  gfw:       "#3b82f6",
  sentinel2: "#10b981",
  osm:       "#f59e0b",
  gdelt:     "#8b5cf6",
  newsdata:  "#ec4899",
};

export function EventTimeline({ cell }: { cell: SelectedCell }) {
  const { events, isLoading, error } = useSignalEvents(cell.h3Index);

  if (isLoading) return <StatusMessage>Loading events…</StatusMessage>;
  if (error) return <StatusMessage error>Failed to load events.</StatusMessage>;
  if (!events.length) return <StatusMessage>No events found for this cell in the selected date range.</StatusMessage>;

  return (
    <div style={{ padding: "12px 16px" }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
        {events.length} event{events.length !== 1 ? "s" : ""}
      </div>
      {events.map((event) => (
        <TimelineEvent key={event.id} event={event} />
      ))}
    </div>
  );
}

function TimelineEvent({ event }: { event: SignalEvent }) {
  const color = SOURCE_COLORS[event.source] ?? "#9ca3af";
  const title = getDisplayTitle(event, event.signalType.replace(/_/g, " "));
  const titleDirection = hasTranslation(event) ? "ltr" : textDirectionForRecord(event);
  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        marginBottom: 12,
        paddingBottom: 12,
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      <div style={{ width: 3, borderRadius: 2, background: color, flexShrink: 0, alignSelf: "stretch" }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 4, marginBottom: 2 }}>
          <span style={{ fontSize: 11, color, fontWeight: 600 }}>
            {SOURCE_LABELS[event.source] ?? event.source}
          </span>
          <span style={{ fontSize: 10, color: "var(--color-text-secondary)", flexShrink: 0 }}>
            {format(new Date(event.occurredAt), "MMM d HH:mm")}
          </span>
        </div>
        <div dir={titleDirection} style={{ fontSize: 12, color: "var(--color-text-primary)" }}>
          {title}
        </div>
      </div>
    </div>
  );
}

/**
 * SignalCards — evidence cards with source attribution per event.
 */
export function SignalCards({ cell }: { cell: SelectedCell }) {
  const { events, isLoading, error } = useSignalEvents(cell.h3Index);

  if (isLoading) return <StatusMessage>Loading signals…</StatusMessage>;
  if (error) return <StatusMessage error>Failed to load signals.</StatusMessage>;
  if (!events.length) return <StatusMessage>No signals found for this cell.</StatusMessage>;

  return (
    <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
      {events.map((event) => (
        <SignalCard key={event.id} event={event} />
      ))}
    </div>
  );
}

function SignalCard({ event }: { event: SignalEvent }) {
  const color = SOURCE_COLORS[event.source] ?? "#9ca3af";
  const title = getDisplayTitle(event, event.signalType.replace(/_/g, " "));
  const titleDirection = hasTranslation(event) ? "ltr" : textDirectionForRecord(event);
  return (
    <article
      aria-label={`${SOURCE_LABELS[event.source] ?? event.source} signal card`}
      style={{
        background: "var(--color-surface-raised)",
        border: `1px solid ${color}44`,
        borderRadius: 8,
        padding: "10px 12px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            color,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          {SOURCE_LABELS[event.source] ?? event.source}
        </span>
        <span style={{ fontSize: 10, color: "var(--color-text-secondary)", fontFamily: "var(--font-mono)" }}>
          {format(new Date(event.occurredAt), "yyyy-MM-dd HH:mm")} UTC
        </span>
      </div>
      <div dir={titleDirection} style={{ fontSize: 12, color: "var(--color-text-primary)", marginBottom: 4 }}>
        {title}
      </div>
      <div style={{ fontSize: 10, color: "var(--color-text-secondary)", display: "flex", justifyContent: "space-between" }}>
        <span>
          Weight: <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text-primary)" }}>{event.weight.toFixed(2)}</span>
        </span>
        {event.sourceId && (
          <span style={{ fontFamily: "var(--font-mono)" }}>ID: {event.sourceId}</span>
        )}
      </div>
      {/* Attribution notice per data source requirements */}
      {event.source === "acled" && (
        <div style={{ marginTop: 6, fontSize: 9, color: "var(--color-text-secondary)", borderTop: "1px solid var(--color-border)", paddingTop: 4 }}>
          Data: ACLED — acleddata.com
        </div>
      )}
      {event.source === "gfw" && (
        <div style={{ marginTop: 6, fontSize: 9, color: "var(--color-text-secondary)", borderTop: "1px solid var(--color-border)", paddingTop: 4 }}>
          Data: Global Fishing Watch — globalfishingwatch.org
        </div>
      )}
    </article>
  );
}

function StatusMessage({ children, error }: { children: React.ReactNode; error?: boolean }) {
  return (
    <div
      style={{
        padding: "24px 16px",
        textAlign: "center",
        fontSize: 12,
        color: error ? "var(--color-danger)" : "var(--color-text-secondary)",
      }}
    >
      {children}
    </div>
  );
}
