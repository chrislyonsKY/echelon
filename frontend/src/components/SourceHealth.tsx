/**
 * SourceHealth — collapsible panel showing ingestion source status.
 * Helps operators quickly spot when a feed has silently died.
 */
import { useState, useEffect } from "react";
import { apiClient } from "@/services/api";
import { formatDistanceToNow } from "date-fns";

interface SourceStatus {
  key: string;
  name: string;
  schedule: string;
  status: "healthy" | "degraded" | "inactive";
  lastRunAt: string | null;
  lastSignalAt: string | null;
  count24h: number;
  count7d: number;
}

interface HealthSummary {
  totalSignals7d: number;
  signals24h: number;
  activeSources: number;
  activeCells: number;
  scoredCells: number;
  avgZScore: number;
  maxZScore: number;
}

const STATUS_COLORS = {
  healthy: "#00c48c",
  degraded: "#e5a400",
  inactive: "#f04444",
};

export default function SourceHealth() {
  const [open, setOpen] = useState(false);
  const [sources, setSources] = useState<SourceStatus[]>([]);
  const [summary, setSummary] = useState<HealthSummary | null>(null);

  useEffect(() => {
    if (!open) return;
    Promise.all([
      apiClient.get<SourceStatus[]>("/health/sources"),
      apiClient.get<HealthSummary>("/health/summary"),
    ]).then(([s, h]) => { setSources(s); setSummary(h); }).catch(() => {});
  }, [open]);

  const healthyCount = sources.filter((s) => s.status === "healthy").length;
  const totalCount = sources.length;

  return (
    <div style={{
      position: "fixed", bottom: 24, left: 16, zIndex: 20,
    }}>
      {/* Toggle button */}
      <button
        onClick={() => setOpen(!open)}
        style={{
          padding: "6px 12px", borderRadius: 6,
          border: "1px solid var(--color-border)",
          background: "var(--color-surface)", cursor: "pointer",
          fontSize: 10, fontWeight: 600, fontFamily: "var(--font-mono)",
          color: healthyCount === totalCount && totalCount > 0
            ? STATUS_COLORS.healthy
            : healthyCount > 0 ? STATUS_COLORS.degraded : "var(--color-text-muted)",
          display: "flex", alignItems: "center", gap: 6,
        }}
      >
        <span style={{
          width: 6, height: 6, borderRadius: "50%",
          background: healthyCount === totalCount && totalCount > 0
            ? STATUS_COLORS.healthy
            : healthyCount > 0 ? STATUS_COLORS.degraded : STATUS_COLORS.inactive,
        }} />
        {open ? "Sources" : `${healthyCount}/${totalCount} sources`}
      </button>

      {/* Panel */}
      {open && (
        <div style={{
          position: "absolute", bottom: "100%", left: 0, marginBottom: 8,
          width: 340, maxHeight: 420, overflow: "auto",
          background: "var(--color-surface)", border: "1px solid var(--color-border)",
          borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
        }}>
          {/* Summary */}
          {summary && (
            <div style={{
              padding: "10px 14px", borderBottom: "1px solid var(--color-border)",
              display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8,
            }}>
              <StatBox label="24h signals" value={summary.signals24h.toLocaleString()} />
              <StatBox label="7d signals" value={summary.totalSignals7d.toLocaleString()} />
              <StatBox label="Active cells" value={summary.activeCells.toLocaleString()} />
              <StatBox label="Sources" value={`${summary.activeSources}`} />
              <StatBox label="Max Z" value={summary.maxZScore.toFixed(2)} />
              <StatBox label="Scored cells" value={summary.scoredCells.toLocaleString()} />
            </div>
          )}

          {/* Source list */}
          {sources.map((src) => (
            <div key={src.key} style={{
              padding: "8px 14px", borderBottom: "1px solid rgba(30,45,70,0.3)",
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                background: STATUS_COLORS[src.status],
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, fontWeight: 500, color: "var(--color-text-primary)" }}>
                  {src.name}
                </div>
                <div style={{ fontSize: 9, color: "var(--color-text-muted)", display: "flex", gap: 8 }}>
                  <span>{src.schedule}</span>
                  {src.lastRunAt && (
                    <span>{formatDistanceToNow(new Date(src.lastRunAt), { addSuffix: true })}</span>
                  )}
                </div>
              </div>
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                <div style={{ fontSize: 11, fontWeight: 600, fontFamily: "var(--font-mono)", color: "var(--color-text-primary)" }}>
                  {src.count24h}
                </div>
                <div style={{ fontSize: 9, color: "var(--color-text-muted)" }}>24h</div>
              </div>
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)" }}>
                  {src.count7d}
                </div>
                <div style={{ fontSize: 9, color: "var(--color-text-muted)" }}>7d</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-text-primary)" }}>
        {value}
      </div>
      <div style={{ fontSize: 8, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </div>
    </div>
  );
}
