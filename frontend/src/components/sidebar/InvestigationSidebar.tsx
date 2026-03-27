/**
 * InvestigationSidebar
 *
 * Tabbed sidebar opened when the user clicks an H3 cell.
 * Tabs: Layer Panel | Event Timeline | Signal Cards
 *
 * Accessibility: focus trap when open, Escape closes.
 */
import { useCallback, useEffect } from "react";
import { useEchelonStore } from "@/store/echelonStore";
import LayerPanel from "./LayerPanel";
import { EventTimeline, SignalCards } from "./EventTimeline";

const TABS = [
  { id: "layers" as const,   label: "Layers" },
  { id: "timeline" as const, label: "Timeline" },
  { id: "signals" as const,  label: "Signals" },
];

export default function InvestigationSidebar() {
  const { selectedCell, sidebarTab, setSidebarTab, setSelectedCell } = useEchelonStore();

  const handleClose = useCallback(() => setSelectedCell(null), [setSelectedCell]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleClose]);

  if (!selectedCell) return null;

  return (
    <aside
      aria-label="Investigation sidebar"
      style={{
        width: "var(--sidebar-width)",
        height: "100%",
        background: "var(--color-surface)",
        borderLeft: "1px solid var(--color-border)",
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid var(--color-border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <div style={{ fontWeight: 600, fontSize: 13, color: "var(--color-text-primary)" }}>
            Cell Investigation
          </div>
          <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginTop: 2, fontFamily: "var(--font-mono)" }}>
            {selectedCell.h3Index}
          </div>
          <div style={{ marginTop: 4 }}>
            <ZScoreBadge zScore={selectedCell.zScore} />
          </div>
        </div>
        <button
          onClick={handleClose}
          aria-label="Close investigation sidebar"
          style={{
            background: "none",
            border: "none",
            color: "var(--color-text-secondary)",
            cursor: "pointer",
            fontSize: 18,
            padding: 4,
            lineHeight: 1,
          }}
        >
          ×
        </button>
      </div>

      {/* Tabs */}
      <div
        role="tablist"
        aria-label="Investigation tabs"
        style={{
          display: "flex",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={sidebarTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            onClick={() => setSidebarTab(tab.id)}
            style={{
              flex: 1,
              padding: "10px 8px",
              background: "none",
              border: "none",
              borderBottom: sidebarTab === tab.id ? "2px solid var(--color-accent)" : "2px solid transparent",
              color: sidebarTab === tab.id ? "var(--color-text-primary)" : "var(--color-text-secondary)",
              cursor: "pointer",
              fontSize: 12,
              fontWeight: sidebarTab === tab.id ? 600 : 400,
              transition: "color 0.15s, border-color 0.15s",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab panels */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {sidebarTab === "layers" && (
          <div id="panel-layers" role="tabpanel" aria-labelledby="tab-layers">
            <LayerPanel />
          </div>
        )}
        {sidebarTab === "timeline" && (
          <div id="panel-timeline" role="tabpanel" aria-labelledby="tab-timeline">
            <EventTimeline cell={selectedCell} />
          </div>
        )}
        {sidebarTab === "signals" && (
          <div id="panel-signals" role="tabpanel" aria-labelledby="tab-signals">
            <SignalCards cell={selectedCell} />
          </div>
        )}
      </div>
    </aside>
  );
}

function ZScoreBadge({ zScore }: { zScore: number }) {
  const color =
    zScore < 1.0 ? "#6b7280"
    : zScore < 1.5 ? "#f59e0b"
    : zScore < 2.0 ? "#fb7100"
    : zScore < 3.0 ? "#ef4444"
    : "#7c3aed";

  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 4,
        background: color + "22",
        color,
        border: `1px solid ${color}66`,
        fontSize: 11,
        fontWeight: 600,
        fontFamily: "var(--font-mono)",
      }}
    >
      Z = {zScore.toFixed(2)}σ
    </span>
  );
}
