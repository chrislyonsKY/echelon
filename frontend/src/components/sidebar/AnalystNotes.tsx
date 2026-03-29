/**
 * AnalystNotes
 *
 * Thread view for analyst notes attached to an event.
 * Fetches from GET /api/investigations/notes/{eventId} and
 * submits new notes via POST /api/investigations/notes.
 */
import { useCallback, useEffect, useState } from "react";
import { notesApi, type AnalystNote, type NoteType, type ConfidenceLevel } from "@/services/api";
import { format } from "date-fns";

// ---------------------------------------------------------------------------
// Badge config
// ---------------------------------------------------------------------------

const NOTE_TYPE_OPTIONS: { value: NoteType; label: string }[] = [
  { value: "observation", label: "Observation" },
  { value: "assessment", label: "Assessment" },
  { value: "review", label: "Review" },
  { value: "correction", label: "Correction" },
  { value: "question", label: "Question" },
];

const NOTE_TYPE_COLORS: Record<NoteType, string> = {
  observation: "#3b82f6",
  assessment:  "#10b981",
  review:      "#a855f7",
  correction:  "#f97316",
  question:    "#94a3b8",
};

const CONFIDENCE_OPTIONS: { value: ConfidenceLevel; label: string }[] = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
  { value: "uncertain", label: "Uncertain" },
];

const CONFIDENCE_COLORS: Record<ConfidenceLevel, string> = {
  high:      "#10b981",
  medium:    "#eab308",
  low:       "#f97316",
  uncertain: "#ef4444",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface AnalystNotesProps {
  eventId: string;
}

export default function AnalystNotes({ eventId }: AnalystNotesProps) {
  const [notes, setNotes] = useState<AnalystNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [noteType, setNoteType] = useState<NoteType>("observation");
  const [confidence, setConfidence] = useState<ConfidenceLevel>("medium");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Fetch notes
  const fetchNotes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await notesApi.getForEvent(eventId);
      setNotes(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load notes";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    fetchNotes();
  }, [fetchNotes]);

  // Submit note
  const handleSubmit = useCallback(async () => {
    if (!content.trim() || submitting) return;
    setSubmitting(true);
    setSubmitError(null);

    try {
      const created = await notesApi.create({
        event_id: eventId,
        note_type: noteType,
        content: content.trim(),
        confidence,
      });
      // Prepend the new note (API returns newest first, so prepend)
      setNotes((prev) => [created, ...prev]);
      setContent("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to submit note";
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  }, [eventId, noteType, confidence, content, submitting]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Section header */}
      <div style={{ padding: "14px 16px 10px", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--color-text-muted)", fontWeight: 600 }}>
        Analyst Notes
        {!loading && (
          <span style={{ marginLeft: 6, fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)" }}>
            {notes.length}
          </span>
        )}
      </div>

      {/* Notes thread */}
      <div style={{ flex: 1, overflow: "auto", padding: "0 16px" }}>
        {loading ? (
          <div style={{ padding: 16, textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
            <span style={{ animation: "pulse 1.5s infinite" }}>Loading notes...</span>
          </div>
        ) : error ? (
          <div style={{ padding: 16, textAlign: "center", color: "#ef4444", fontSize: 12 }}>
            {error}
          </div>
        ) : notes.length === 0 ? (
          <div style={{ padding: 16, textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
            No analyst notes for this event yet.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10, paddingBottom: 12 }}>
            {notes.map((note) => (
              <NoteCard key={note.id} note={note} />
            ))}
          </div>
        )}
      </div>

      {/* Input form */}
      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--color-border)",
          display: "flex",
          flexDirection: "column",
          gap: 8,
          flexShrink: 0,
        }}
      >
        {/* Selectors row */}
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
            <label htmlFor="note-type-select" style={{ fontSize: 10, color: "var(--color-text-muted)", fontWeight: 500 }}>
              Type
            </label>
            <select
              id="note-type-select"
              value={noteType}
              onChange={(e) => setNoteType(e.target.value as NoteType)}
              style={{
                padding: "4px 6px",
                fontSize: 11,
                background: "var(--color-surface-raised, #1e293b)",
                color: "var(--color-text-primary)",
                border: "1px solid var(--color-border)",
                borderRadius: 4,
                outline: "none",
              }}
            >
              {NOTE_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
            <label htmlFor="confidence-select" style={{ fontSize: 10, color: "var(--color-text-muted)", fontWeight: 500 }}>
              Confidence
            </label>
            <select
              id="confidence-select"
              value={confidence}
              onChange={(e) => setConfidence(e.target.value as ConfidenceLevel)}
              style={{
                padding: "4px 6px",
                fontSize: 11,
                background: "var(--color-surface-raised, #1e293b)",
                color: "var(--color-text-primary)",
                border: "1px solid var(--color-border)",
                borderRadius: 4,
                outline: "none",
              }}
            >
              {CONFIDENCE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Text area */}
        <textarea
          value={content}
          onChange={(e) => {
            setContent(e.target.value);
            setSubmitError(null);
          }}
          placeholder="Add a note..."
          rows={3}
          style={{
            padding: "6px 8px",
            fontSize: 12,
            lineHeight: 1.5,
            background: "var(--color-surface-raised, #1e293b)",
            color: "var(--color-text-primary)",
            border: "1px solid var(--color-border)",
            borderRadius: 4,
            outline: "none",
            resize: "vertical",
            fontFamily: "inherit",
          }}
        />

        {/* Submit */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            onClick={handleSubmit}
            disabled={submitting || !content.trim()}
            style={{
              padding: "6px 14px",
              fontSize: 12,
              fontWeight: 600,
              background: submitting || !content.trim() ? "var(--color-border)" : "var(--color-accent)",
              color: "#fff",
              border: "none",
              borderRadius: 4,
              cursor: submitting || !content.trim() ? "not-allowed" : "pointer",
              opacity: submitting || !content.trim() ? 0.5 : 1,
            }}
          >
            {submitting ? "Posting..." : "Add Note"}
          </button>
          {submitError && (
            <span style={{ fontSize: 11, color: "#ef4444" }}>{submitError}</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NoteCard sub-component
// ---------------------------------------------------------------------------

function NoteCard({ note }: { note: AnalystNote }) {
  const typeColor = NOTE_TYPE_COLORS[note.noteType as NoteType] || "#94a3b8";
  const confColor = note.confidence
    ? CONFIDENCE_COLORS[note.confidence as ConfidenceLevel] || "#94a3b8"
    : null;

  const typeLabel = NOTE_TYPE_OPTIONS.find((o) => o.value === note.noteType)?.label ?? note.noteType;
  const confLabel = note.confidence
    ? CONFIDENCE_OPTIONS.find((o) => o.value === note.confidence)?.label ?? note.confidence
    : null;

  return (
    <div
      style={{
        padding: "10px 12px",
        background: "var(--color-surface-raised, #1e293b)",
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        fontSize: 12,
      }}
    >
      {/* Header: author + badges + timestamp */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600, color: "var(--color-text-primary)", fontSize: 11 }}>
          {note.username || note.userId.slice(0, 8)}
        </span>

        {/* Note type badge */}
        <span
          style={{
            padding: "1px 6px",
            borderRadius: 3,
            fontSize: 9,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.04em",
            background: `${typeColor}22`,
            color: typeColor,
            border: `1px solid ${typeColor}44`,
          }}
        >
          {typeLabel}
        </span>

        {/* Confidence badge */}
        {confColor && confLabel && (
          <span
            style={{
              padding: "1px 6px",
              borderRadius: 3,
              fontSize: 9,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              background: `${confColor}22`,
              color: confColor,
              border: `1px solid ${confColor}44`,
            }}
          >
            {confLabel}
          </span>
        )}

        {/* Timestamp */}
        <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", flexShrink: 0 }}>
          {note.createdAt ? format(new Date(note.createdAt), "MMM d HH:mm") : ""}
        </span>
      </div>

      {/* Content */}
      <div style={{ color: "var(--color-text-secondary)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
        {note.content}
      </div>
    </div>
  );
}
