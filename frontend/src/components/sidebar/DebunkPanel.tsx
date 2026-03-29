/**
 * DebunkPanel
 *
 * Allows analysts to mark an event's debunk status with a reason.
 * Submits a PATCH to /api/events/{eventId} with debunk_status and debunk_reason.
 *
 * NOTE: The backend PATCH endpoint for events does not yet exist.
 * A PATCH /api/events/{eventId} route accepting { debunk_status, debunk_reason }
 * needs to be added to backend/app/routers/events.py.
 */
import { useCallback, useState } from "react";
import { eventsApi, type DebunkStatus } from "@/services/api";

const DEBUNK_STATUSES: { value: DebunkStatus; label: string }[] = [
  { value: "not_assessed", label: "Not assessed" },
  { value: "false", label: "False" },
  { value: "duplicate", label: "Duplicate" },
  { value: "spoofed", label: "Spoofed" },
  { value: "mislocated", label: "Mislocated" },
  { value: "satire", label: "Satire" },
  { value: "propaganda", label: "Propaganda" },
  { value: "old_imagery", label: "Old imagery" },
  { value: "stale_repost", label: "Stale repost" },
  { value: "debunked", label: "Debunked" },
];

const STATUS_COLORS: Record<DebunkStatus, { bg: string; fg: string }> = {
  not_assessed:  { bg: "rgba(148,163,184,0.15)", fg: "#94a3b8" },
  false:         { bg: "rgba(239,68,68,0.15)",   fg: "#ef4444" },
  duplicate:     { bg: "rgba(234,179,8,0.15)",   fg: "#eab308" },
  spoofed:       { bg: "rgba(249,115,22,0.15)",  fg: "#f97316" },
  mislocated:    { bg: "rgba(249,115,22,0.15)",  fg: "#f97316" },
  satire:        { bg: "rgba(148,163,184,0.15)", fg: "#94a3b8" },
  propaganda:    { bg: "rgba(249,115,22,0.15)",  fg: "#f97316" },
  old_imagery:   { bg: "rgba(234,179,8,0.15)",   fg: "#eab308" },
  stale_repost:  { bg: "rgba(234,179,8,0.15)",   fg: "#eab308" },
  debunked:      { bg: "rgba(239,68,68,0.15)",   fg: "#ef4444" },
};

interface DebunkPanelProps {
  eventId: string;
  debunkStatus: string | null;
  onStatusUpdated?: (status: DebunkStatus, reason: string) => void;
}

export default function DebunkPanel({ eventId, debunkStatus, onStatusUpdated }: DebunkPanelProps) {
  const currentStatus = (debunkStatus as DebunkStatus) || "not_assessed";
  const [selected, setSelected] = useState<DebunkStatus>(currentStatus);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const statusColor = STATUS_COLORS[currentStatus] || STATUS_COLORS.not_assessed;
  const currentLabel = DEBUNK_STATUSES.find((s) => s.value === currentStatus)?.label ?? "Not assessed";

  const handleSubmit = useCallback(async () => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    setSuccess(false);

    try {
      await eventsApi.patchDebunkStatus(eventId, selected, reason);
      setSuccess(true);
      onStatusUpdated?.(selected, reason);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update debunk status";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }, [eventId, selected, reason, submitting, onStatusUpdated]);

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
      {/* Section header */}
      <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--color-text-muted)", fontWeight: 600 }}>
        Debunk Assessment
      </div>

      {/* Current status badge */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>Current:</span>
        <span
          style={{
            display: "inline-block",
            padding: "2px 10px",
            borderRadius: 4,
            fontSize: 11,
            fontWeight: 600,
            background: statusColor.bg,
            color: statusColor.fg,
            border: `1px solid ${statusColor.fg}33`,
          }}
        >
          {currentLabel}
        </span>
      </div>

      {/* Status selector */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <label
          htmlFor="debunk-status-select"
          style={{ fontSize: 11, color: "var(--color-text-secondary)", fontWeight: 500 }}
        >
          Set status
        </label>
        <select
          id="debunk-status-select"
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value as DebunkStatus);
            setSuccess(false);
          }}
          style={{
            padding: "6px 8px",
            fontSize: 12,
            background: "var(--color-surface-raised, #1e293b)",
            color: "var(--color-text-primary)",
            border: "1px solid var(--color-border)",
            borderRadius: 4,
            outline: "none",
            cursor: "pointer",
          }}
        >
          {DEBUNK_STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {/* Reason input */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <label
          htmlFor="debunk-reason-input"
          style={{ fontSize: 11, color: "var(--color-text-secondary)", fontWeight: 500 }}
        >
          Reason
        </label>
        <input
          id="debunk-reason-input"
          type="text"
          value={reason}
          onChange={(e) => {
            setReason(e.target.value);
            setSuccess(false);
          }}
          placeholder="Explain why this status was assigned..."
          style={{
            padding: "6px 8px",
            fontSize: 12,
            background: "var(--color-surface-raised, #1e293b)",
            color: "var(--color-text-primary)",
            border: "1px solid var(--color-border)",
            borderRadius: 4,
            outline: "none",
          }}
        />
      </div>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={submitting}
        style={{
          padding: "7px 14px",
          fontSize: 12,
          fontWeight: 600,
          background: submitting ? "var(--color-border)" : "var(--color-accent)",
          color: "#fff",
          border: "none",
          borderRadius: 4,
          cursor: submitting ? "not-allowed" : "pointer",
          opacity: submitting ? 0.6 : 1,
          alignSelf: "flex-start",
        }}
      >
        {submitting ? "Submitting..." : "Update Status"}
      </button>

      {/* Feedback */}
      {error && (
        <div style={{ fontSize: 11, color: "#ef4444", padding: "4px 0" }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{ fontSize: 11, color: "#10b981", padding: "4px 0" }}>
          Debunk status updated.
        </div>
      )}
    </div>
  );
}
