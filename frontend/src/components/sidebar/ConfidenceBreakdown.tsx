/**
 * ConfidenceBreakdown — decomposes a convergence Z-score into trust dimensions.
 *
 * Shows 5 independent confidence axes so analysts know what KIND of trust
 * to place in a score, not just the magnitude.
 */
import { useEffect, useState } from "react";
import { investigationsApi, type ScoringExplanation } from "@/services/api";

interface Props {
  h3Index: string;
}

const DIMENSIONS: {
  key: keyof Pick<ScoringExplanation, "confidenceStatistical" | "confidenceDiversity" | "confidenceSensor" | "confidenceMedia" | "confidenceReviewed">;
  label: string;
  description: string;
  color: string;
}[] = [
  {
    key: "confidenceStatistical",
    label: "Statistical Anomaly",
    description: "Z-score magnitude — how far above the baseline",
    color: "#2563eb",
  },
  {
    key: "confidenceDiversity",
    label: "Source Diversity",
    description: "Number of independent source families contributing",
    color: "#059669",
  },
  {
    key: "confidenceSensor",
    label: "Sensor-Backed",
    description: "Fraction from sensor sources (GFW, OpenSky, FIRMS, Sentinel)",
    color: "#0891b2",
  },
  {
    key: "confidenceMedia",
    label: "Media-Only",
    description: "Fraction from media sources (GDELT, news, OSINT)",
    color: "#d97706",
  },
  {
    key: "confidenceReviewed",
    label: "Human-Reviewed",
    description: "Fraction of signals that have been human-reviewed",
    color: "#7c3aed",
  },
];

export default function ConfidenceBreakdown({ h3Index }: Props) {
  const [data, setData] = useState<ScoringExplanation | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    investigationsApi
      .getScoring(h3Index)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [h3Index]);

  if (loading) {
    return (
      <div style={{ padding: 16, fontSize: 11, color: "var(--color-text-muted)" }}>
        Loading scoring explanation...
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ padding: 16, fontSize: 11, color: "var(--color-text-muted)" }}>
        No scoring data available for this cell.
      </div>
    );
  }

  return (
    <div style={{ padding: "12px 16px" }}>
      {/* Z-score header */}
      <div style={{
        display: "flex", alignItems: "baseline", gap: 8, marginBottom: 12,
        paddingBottom: 8, borderBottom: "1px solid var(--color-border)",
      }}>
        <span style={{
          fontSize: 24, fontWeight: 700, fontFamily: "var(--font-mono)",
          color: data.zScore >= 3 ? "#dc2626" : data.zScore >= 2 ? "#eab308" : "#2563eb",
        }}>
          {data.zScore.toFixed(2)}
        </span>
        <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Z-score</span>
        <span style={{ fontSize: 11, color: "var(--color-text-muted)", marginLeft: "auto" }}>
          Raw: {data.rawScore.toFixed(4)}
        </span>
      </div>

      {/* Confidence dimensions — horizontal bar chart */}
      <div style={{ fontSize: 9, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
        Confidence Breakdown
      </div>

      {DIMENSIONS.map((dim) => {
        const value = data[dim.key] ?? 0;
        const pct = Math.min(100, Math.max(0, value * 100));
        return (
          <div key={dim.key} style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 2 }}>
              <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{dim.label}</span>
              <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: dim.color }}>
                {pct.toFixed(0)}%
              </span>
            </div>
            <div style={{ height: 6, background: "var(--color-surface)", borderRadius: 3, overflow: "hidden" }}>
              <div style={{
                height: "100%", width: `${pct}%`,
                background: dim.color, borderRadius: 3,
                transition: "width 0.3s ease",
              }} />
            </div>
            <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 1 }}>
              {dim.description}
            </div>
          </div>
        );
      })}

      {/* Signal breakdown by source */}
      {data.signalBreakdown && Object.keys(data.signalBreakdown).length > 0 && (
        <>
          <div style={{ fontSize: 9, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginTop: 12, marginBottom: 6 }}>
            Signal Breakdown
          </div>
          {Object.entries(data.signalBreakdown).map(([source, count]) => (
            <div key={source} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", fontSize: 11 }}>
              <span style={{ color: "var(--color-text-secondary)" }}>{source}</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text-primary)" }}>{String(count)}</span>
            </div>
          ))}
        </>
      )}

      {/* Low confidence warning */}
      {data.lowConfidence && (
        <div style={{
          marginTop: 10, padding: "6px 10px", fontSize: 10,
          color: "#eab308", background: "rgba(234,179,8,0.08)",
          border: "1px solid rgba(234,179,8,0.2)", borderRadius: 4,
        }}>
          Low confidence — fewer than 30 baseline observations. Z-score may be unreliable.
        </div>
      )}
    </div>
  );
}
