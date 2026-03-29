/**
 * SaveInvestigationModal
 *
 * Fixed overlay modal for saving the current map state (viewport, date range,
 * active layers) as a named investigation. Dark theme, consistent with
 * Echelon sidebar styling.
 */
import { useCallback, useEffect, useState } from "react";
import { useEchelonStore } from "@/store/echelonStore";
import { investigationsApi, type InvestigationCreate } from "@/services/api";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function SaveInvestigationModal({ open, onClose }: Props) {
  const { viewState, dateRange, layerVisibility, selectedCell } = useEchelonStore();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setTitle("");
      setDescription("");
      setNotes("");
      setTagsInput("");
      setError(null);
      setSuccess(false);
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const handleSave = useCallback(async () => {
    const trimmed = title.trim();
    if (!trimmed) {
      setError("Title is required.");
      return;
    }

    setSaving(true);
    setError(null);

    const tags = tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    const body: InvestigationCreate = {
      title: trimmed,
      description: description.trim() || undefined,
      notes: notes.trim() || undefined,
      tags,
      viewState: {
        longitude: viewState.longitude ?? 0,
        latitude: viewState.latitude ?? 20,
        zoom: viewState.zoom ?? 2,
        pitch: viewState.pitch ?? 0,
        bearing: viewState.bearing ?? 0,
      },
      dateRange: {
        from: dateRange.from.toISOString(),
        to: dateRange.to.toISOString(),
      },
      layerVisibility: { ...layerVisibility },
      selectedCellH3: selectedCell?.h3Index,
    };

    try {
      await investigationsApi.create(body);
      setSuccess(true);
      setTimeout(() => onClose(), 800);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save investigation.");
    } finally {
      setSaving(false);
    }
  }, [title, description, notes, tagsInput, viewState, dateRange, layerVisibility, selectedCell, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Save investigation"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0, 0, 0, 0.6)",
        backdropFilter: "blur(4px)",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 420,
          maxHeight: "80vh",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 8,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 16px 48px rgba(0, 0, 0, 0.4)",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "var(--color-text-primary)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            Save Investigation
          </span>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: "none",
              border: "none",
              color: "var(--color-text-muted)",
              cursor: "pointer",
              fontSize: 18,
              padding: 4,
            }}
          >
            ×
          </button>
        </div>

        {/* Form */}
        <div style={{ padding: "16px 20px", overflow: "auto", display: "flex", flexDirection: "column", gap: 14 }}>
          <Field label="Title *">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Black Sea AIS anomalies"
              autoFocus
              style={inputStyle}
            />
          </Field>

          <Field label="Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief summary of what you are tracking"
              rows={2}
              style={{ ...inputStyle, resize: "vertical", minHeight: 48 }}
            />
          </Field>

          <Field label="Notes">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Internal notes, hypotheses, next steps..."
              rows={3}
              style={{ ...inputStyle, resize: "vertical", minHeight: 56 }}
            />
          </Field>

          <Field label="Tags (comma-separated)">
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="e.g. maritime, dark-fleet, ukraine"
              style={inputStyle}
            />
          </Field>

          {/* State preview */}
          <div
            style={{
              padding: "10px 12px",
              borderRadius: 6,
              background: "rgba(255,255,255,0.03)",
              border: "1px solid var(--color-border)",
              fontSize: 10,
              color: "var(--color-text-muted)",
              fontFamily: "var(--font-mono)",
              lineHeight: 1.7,
            }}
          >
            <div>Viewport: {(viewState.latitude ?? 0).toFixed(2)}, {(viewState.longitude ?? 0).toFixed(2)} z{(viewState.zoom ?? 2).toFixed(1)}</div>
            <div>Date range: {dateRange.from.toISOString().split("T")[0]} to {dateRange.to.toISOString().split("T")[0]}</div>
            <div>
              Active layers:{" "}
              {Object.entries(layerVisibility)
                .filter(([, v]) => v)
                .map(([k]) => k)
                .join(", ") || "none"}
            </div>
            {selectedCell && <div>Selected cell: {selectedCell.h3Index}</div>}
          </div>

          {/* Feedback */}
          {error && (
            <div style={{ fontSize: 11, color: "var(--color-error, #ef4444)", padding: "4px 0" }}>
              {error}
            </div>
          )}
          {success && (
            <div style={{ fontSize: 11, color: "var(--color-success, #10b981)", padding: "4px 0" }}>
              Investigation saved.
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 20px",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 10,
          }}
        >
          <button onClick={onClose} style={secondaryButtonStyle}>
            Cancel
          </button>
          <button onClick={handleSave} disabled={saving || success} style={primaryButtonStyle}>
            {saving ? "Saving..." : success ? "Saved" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span
        style={{
          fontSize: 10,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: "var(--color-text-muted)",
        }}
      >
        {label}
      </span>
      {children}
    </label>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  fontSize: 12,
  color: "var(--color-text-primary)",
  background: "rgba(255,255,255,0.04)",
  border: "1px solid var(--color-border)",
  borderRadius: 4,
  outline: "none",
  fontFamily: "inherit",
  boxSizing: "border-box",
};

const primaryButtonStyle: React.CSSProperties = {
  padding: "7px 18px",
  fontSize: 11,
  fontWeight: 600,
  borderRadius: 4,
  border: "none",
  cursor: "pointer",
  background: "var(--color-accent, #2d8cf0)",
  color: "#fff",
};

const secondaryButtonStyle: React.CSSProperties = {
  padding: "7px 18px",
  fontSize: 11,
  fontWeight: 600,
  borderRadius: 4,
  border: "1px solid var(--color-border)",
  cursor: "pointer",
  background: "transparent",
  color: "var(--color-text-secondary)",
};
