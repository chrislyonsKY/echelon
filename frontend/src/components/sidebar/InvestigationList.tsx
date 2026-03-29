/**
 * InvestigationList
 *
 * Scrollable panel showing saved investigations. Clicking an item loads its
 * saved state (viewport, date range, layers) into the Zustand store. Each
 * item has a delete button with confirmation.
 */
import { useCallback, useEffect, useState } from "react";
import { useEchelonStore } from "@/store/echelonStore";
import { investigationsApi, type Investigation } from "@/services/api";
import { format } from "date-fns";

export default function InvestigationList() {
  const { setViewState, setDateRange, toggleLayer, layerVisibility } = useEchelonStore();

  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const fetchList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await investigationsApi.list();
      setInvestigations(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load investigations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const handleLoad = useCallback(
    async (id: string) => {
      setLoadingId(id);
      try {
        const inv = await investigationsApi.get(id);

        // Apply saved viewport
        setViewState({
          longitude: inv.viewState.longitude,
          latitude: inv.viewState.latitude,
          zoom: inv.viewState.zoom,
          pitch: inv.viewState.pitch ?? 0,
          bearing: inv.viewState.bearing ?? 0,
        });

        // Apply saved date range
        setDateRange(new Date(inv.dateRange.from), new Date(inv.dateRange.to));

        // Apply saved layer visibility — toggle layers to match saved state
        const savedLayers = inv.layerVisibility as Record<string, boolean>;
        for (const [layer, active] of Object.entries(savedLayers)) {
          const key = layer as keyof typeof layerVisibility;
          if (key in layerVisibility && layerVisibility[key] !== active) {
            toggleLayer(key);
          }
        }
      } catch {
        // Silently handle — the user can retry
      } finally {
        setLoadingId(null);
      }
    },
    [setViewState, setDateRange, toggleLayer, layerVisibility]
  );

  const handleDelete = useCallback(
    async (id: string) => {
      setDeletingId(id);
      try {
        await investigationsApi.delete(id);
        setInvestigations((prev) => prev.filter((inv) => inv.id !== id));
      } catch {
        // Deletion failed — keep the item
      } finally {
        setDeletingId(null);
        setConfirmDeleteId(null);
      }
    },
    []
  );

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div style={emptyStyle}>
        <span style={{ animation: "pulse 1.5s infinite" }}>Loading investigations...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div style={emptyStyle}>
        <span style={{ color: "var(--color-error, #ef4444)" }}>{error}</span>
        <button onClick={fetchList} style={retryButtonStyle}>
          Retry
        </button>
      </div>
    );
  }

  if (investigations.length === 0) {
    return (
      <div style={emptyStyle}>
        No saved investigations yet. Use the save button to capture the current map state.
      </div>
    );
  }

  return (
    <div style={{ overflow: "auto", flex: 1 }}>
      {investigations.map((inv) => {
        const isDeleting = deletingId === inv.id;
        const isConfirming = confirmDeleteId === inv.id;
        const isLoading = loadingId === inv.id;

        return (
          <div
            key={inv.id}
            style={{
              padding: "12px 16px",
              borderBottom: "1px solid var(--color-border)",
              cursor: "pointer",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.03)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "transparent";
            }}
            onClick={() => handleLoad(inv.id)}
          >
            {/* Title row */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: isLoading ? "var(--color-accent)" : "var(--color-text-primary)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {isLoading ? "Loading..." : inv.title}
                </div>
                {inv.description && (
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--color-text-secondary)",
                      marginTop: 3,
                      lineHeight: 1.4,
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {inv.description}
                  </div>
                )}
              </div>

              {/* Delete button */}
              <div
                onClick={(e) => e.stopPropagation()}
                style={{ flexShrink: 0 }}
              >
                {isConfirming ? (
                  <div style={{ display: "flex", gap: 4 }}>
                    <button
                      onClick={() => handleDelete(inv.id)}
                      disabled={isDeleting}
                      style={{
                        ...deleteButtonStyle,
                        color: "var(--color-error, #ef4444)",
                        borderColor: "var(--color-error, #ef4444)",
                      }}
                    >
                      {isDeleting ? "..." : "Yes"}
                    </button>
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      style={deleteButtonStyle}
                    >
                      No
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDeleteId(inv.id)}
                    aria-label="Delete investigation"
                    title="Delete"
                    style={deleteButtonStyle}
                  >
                    ×
                  </button>
                )}
              </div>
            </div>

            {/* Tags */}
            {inv.tags.length > 0 && (
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6 }}>
                {inv.tags.map((tag) => (
                  <span
                    key={tag}
                    style={{
                      fontSize: 9,
                      fontWeight: 600,
                      padding: "2px 6px",
                      borderRadius: 3,
                      background: "var(--color-accent-muted, rgba(45,140,240,0.12))",
                      color: "var(--color-accent, #2d8cf0)",
                      border: "1px solid rgba(45,140,240,0.2)",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}

            {/* Metadata row */}
            <div
              style={{
                marginTop: 6,
                fontSize: 10,
                color: "var(--color-text-muted)",
                fontFamily: "var(--font-mono)",
                display: "flex",
                gap: 10,
              }}
            >
              <span>{format(new Date(inv.createdAt), "MMM d, yyyy HH:mm")}</span>
              <span>z{inv.viewState.zoom.toFixed(1)}</span>
              <span>
                {inv.dateRange.from.split("T")[0]} to {inv.dateRange.to.split("T")[0]}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────

const emptyStyle: React.CSSProperties = {
  padding: 24,
  textAlign: "center",
  color: "var(--color-text-muted)",
  fontSize: 12,
  lineHeight: 1.6,
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: 10,
};

const deleteButtonStyle: React.CSSProperties = {
  background: "none",
  border: "1px solid var(--color-border)",
  borderRadius: 3,
  color: "var(--color-text-muted)",
  cursor: "pointer",
  fontSize: 12,
  padding: "2px 6px",
  lineHeight: 1,
};

const retryButtonStyle: React.CSSProperties = {
  padding: "5px 14px",
  fontSize: 11,
  fontWeight: 600,
  borderRadius: 4,
  border: "1px solid var(--color-border)",
  cursor: "pointer",
  background: "transparent",
  color: "var(--color-text-secondary)",
};
