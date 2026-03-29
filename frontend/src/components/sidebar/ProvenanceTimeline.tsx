/**
 * ProvenanceTimeline
 *
 * Displays the provenance timeline for an event: every contributing signal
 * in chronological order, with source color-coding, weight, and policy badges.
 */
import { useEffect, useState } from "react";
import { provenanceApi, type ProvenanceEntry } from "@/services/api";
import { format } from "date-fns";

// ── Source color map (mirrors InvestigationSidebar / EchelonMap) ──────────────

const SOURCE_COLORS: Record<string, { label: string; color: string }> = {
  gdelt:     { label: "GDELT",               color: "#ef4444" },
  gfw:       { label: "Global Fishing Watch", color: "#3b82f6" },
  newsdata:  { label: "News",                color: "#f59e0b" },
  osm:       { label: "Infrastructure",      color: "#10b981" },
  sentinel2: { label: "Sentinel-2",          color: "#9333ea" },
  opensky:   { label: "Air Traffic",         color: "#06b6d4" },
};

function sourceColor(source: string): string {
  return SOURCE_COLORS[source]?.color ?? "#94a3b8";
}

function sourceLabel(source: string): string {
  return SOURCE_COLORS[source]?.label ?? source;
}

// ── Badge helpers ────────────────────────────────────────────────────────────

function provenanceFamilyColor(family: string): string {
  switch (family) {
    case "official":       return "#3b82f6";
    case "media":          return "#f59e0b";
    case "social":         return "#ef4444";
    case "sensor":         return "#9333ea";
    case "infrastructure": return "#10b981";
    default:               return "#94a3b8";
  }
}

function confirmationPolicyColor(policy: string): string {
  switch (policy) {
    case "wire_confirmed":
    case "western_wire":         return "#10b981";
    case "context_only":         return "#f59e0b";
    case "aggregated_context":   return "#94a3b8";
    default:                     return "#94a3b8";
  }
}

function confirmationPolicyLabel(policy: string): string {
  switch (policy) {
    case "wire_confirmed":
    case "western_wire":       return "WIRE";
    case "context_only":       return "CTX";
    case "aggregated_context": return "AGG";
    default:                   return policy.slice(0, 4).toUpperCase();
  }
}

// ── Summary computation ──────────────────────────────────────────────────────

interface TimelineSummary {
  totalSignals: number;
  distinctSources: number;
  timeSpan: string;
}

function computeSummary(entries: ProvenanceEntry[]): TimelineSummary {
  const sources = new Set(entries.map((e) => e.source));
  let timeSpan = "--";

  if (entries.length >= 2) {
    const sorted = [...entries].sort(
      (a, b) => new Date(a.occurredAt).getTime() - new Date(b.occurredAt).getTime()
    );
    const first = new Date(sorted[0].occurredAt);
    const last = new Date(sorted[sorted.length - 1].occurredAt);
    const diffMs = last.getTime() - first.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);

    if (diffHours < 1) {
      timeSpan = `${Math.round(diffMs / (1000 * 60))}m`;
    } else if (diffHours < 48) {
      timeSpan = `${Math.round(diffHours)}h`;
    } else {
      timeSpan = `${Math.round(diffHours / 24)}d`;
    }
  } else if (entries.length === 1) {
    timeSpan = "single point";
  }

  return { totalSignals: entries.length, distinctSources: sources.size, timeSpan };
}

// ── Badge component ──────────────────────────────────────────────────────────

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span
      style={{
        fontSize: 8,
        fontWeight: 700,
        padding: "1px 4px",
        borderRadius: 3,
        background: color + "22",
        color: color,
        border: `1px solid ${color}44`,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

interface ProvenanceTimelineProps {
  eventId: string;
}

export default function ProvenanceTimeline({ eventId }: ProvenanceTimelineProps) {
  const [entries, setEntries] = useState<ProvenanceEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    provenanceApi
      .getProvenance(eventId)
      .then((data) => {
        const sorted = [...data].sort(
          (a, b) => new Date(a.occurredAt).getTime() - new Date(b.occurredAt).getTime()
        );
        setEntries(sorted);
      })
      .catch((err: Error) => {
        setError(err.message || "Failed to load provenance data");
        setEntries([]);
      })
      .finally(() => setLoading(false));
  }, [eventId]);

  // Loading state
  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
        <span style={{ animation: "pulse 1.5s infinite" }}>Loading provenance...</span>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--color-danger, #ef4444)", fontSize: 12 }}>
        {error}
      </div>
    );
  }

  // Empty state
  if (entries.length === 0) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
        No signals found for this event.
      </div>
    );
  }

  const summary = computeSummary(entries);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {/* Summary bar */}
      <div
        style={{
          padding: "10px 16px",
          borderBottom: "1px solid var(--color-border)",
          display: "flex",
          gap: 12,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <SummaryStat label="Signals" value={String(summary.totalSignals)} />
        <SummaryStat label="Sources" value={String(summary.distinctSources)} />
        <SummaryStat label="Span" value={summary.timeSpan} />
      </div>

      {/* Timeline */}
      <div style={{ padding: "12px 16px", position: "relative" }}>
        {/* Vertical line */}
        <div
          style={{
            position: "absolute",
            left: 27,
            top: 24,
            bottom: 12,
            width: 1,
            background: "var(--color-border)",
          }}
        />

        {entries.map((entry, idx) => (
          <TimelineNode key={entry.signalId} entry={entry} isLast={idx === entries.length - 1} />
        ))}
      </div>
    </div>
  );
}

// ── Summary stat pill ────────────────────────────────────────────────────────

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
      <span
        style={{
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: "var(--color-text-muted)",
          fontWeight: 600,
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: 13,
          fontWeight: 700,
          fontFamily: "var(--font-mono)",
          color: "var(--color-text-primary)",
        }}
      >
        {value}
      </span>
    </div>
  );
}

// ── Timeline node ────────────────────────────────────────────────────────────

function TimelineNode({ entry, isLast }: { entry: ProvenanceEntry; isLast: boolean }) {
  const color = sourceColor(entry.source);

  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        paddingBottom: isLast ? 0 : 14,
        position: "relative",
      }}
    >
      {/* Dot */}
      <div
        style={{
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: color,
          flexShrink: 0,
          marginTop: 3,
          border: "2px solid var(--color-surface)",
          boxShadow: `0 0 0 1px ${color}66`,
          zIndex: 1,
        }}
      />

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* First row: source + signal type + time */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: color,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                flexShrink: 0,
              }}
            >
              {sourceLabel(entry.source)}
            </span>
            <span
              style={{
                fontSize: 10,
                color: "var(--color-text-secondary)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {entry.signalType.replace(/_/g, " ")}
            </span>
          </div>
          <span
            style={{
              fontSize: 10,
              color: "var(--color-text-muted)",
              fontFamily: "var(--font-mono)",
              flexShrink: 0,
            }}
          >
            {format(new Date(entry.occurredAt), "MMM d HH:mm")}
          </span>
        </div>

        {/* Second row: metadata */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginTop: 3,
            flexWrap: "wrap",
          }}
        >
          {/* Weight */}
          <span
            style={{
              fontSize: 9,
              color: "var(--color-text-muted)",
              fontFamily: "var(--font-mono)",
            }}
          >
            w: {entry.weight.toFixed(2)}
          </span>

          {/* Score contribution */}
          <span
            style={{
              fontSize: 9,
              color: "var(--color-accent)",
              fontFamily: "var(--font-mono)",
            }}
          >
            +{entry.scoreContribution.toFixed(2)}
          </span>

          {/* Ingested at */}
          <span style={{ fontSize: 9, color: "var(--color-text-muted)" }}>
            ingested {format(new Date(entry.ingestedAt), "MMM d HH:mm")}
          </span>

          {/* Provenance family badge */}
          {entry.provenanceFamily && (
            <Badge
              label={entry.provenanceFamily.toUpperCase()}
              color={provenanceFamilyColor(entry.provenanceFamily)}
            />
          )}

          {/* Confirmation policy badge */}
          {entry.confirmationPolicy && (
            <Badge
              label={confirmationPolicyLabel(entry.confirmationPolicy)}
              color={confirmationPolicyColor(entry.confirmationPolicy)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
