/**
 * TimelineScrubber — horizontal time slider for scrubbing through signal history.
 * Adjusts the global date range, which triggers map + feed + trend updates.
 */
import { useState, useCallback } from "react";
import { useEchelonStore } from "@/store/echelonStore";
import { format, subHours } from "date-fns";

const STEPS = [
  { label: "6h", hours: 6 },
  { label: "12h", hours: 12 },
  { label: "24h", hours: 24 },
  { label: "3d", hours: 72 },
  { label: "7d", hours: 168 },
  { label: "14d", hours: 336 },
  { label: "30d", hours: 720 },
  { label: "90d", hours: 2160 },
];

export default function TimelineScrubber() {
  const { dateRange, setDateRange } = useEchelonStore();
  const [expanded, setExpanded] = useState(false);

  // Compute current step index based on date range width
  const rangeHours = (dateRange.to.getTime() - dateRange.from.getTime()) / (1000 * 60 * 60);
  const currentStep = STEPS.reduce((best, step, i) =>
    Math.abs(step.hours - rangeHours) < Math.abs(STEPS[best].hours - rangeHours) ? i : best
  , 0);

  const handleSlider = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const idx = parseInt(e.target.value);
    const step = STEPS[idx];
    const now = new Date();
    setDateRange(subHours(now, step.hours), now);
  }, [setDateRange]);

  return (
    <div style={{
      position: "absolute", bottom: 32, left: "50%", transform: "translateX(-50%)",
      zIndex: 5, display: "flex", flexDirection: "column", alignItems: "center", gap: 4,
    }}>
      {expanded && (
        <div style={{
          background: "rgba(17,24,39,0.92)", border: "1px solid var(--color-border)",
          borderRadius: 8, padding: "8px 16px", backdropFilter: "blur(8px)",
          display: "flex", alignItems: "center", gap: 12, minWidth: 360,
        }}>
          <span style={{ fontSize: 9, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", flexShrink: 0 }}>
            {format(dateRange.from, "MMM d HH:mm")}
          </span>

          <input
            type="range"
            min={0}
            max={STEPS.length - 1}
            value={currentStep}
            onChange={handleSlider}
            style={{
              flex: 1, height: 4, appearance: "none", background: "var(--color-border)",
              borderRadius: 2, outline: "none", cursor: "pointer",
            }}
          />

          <span style={{ fontSize: 9, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", flexShrink: 0 }}>
            {format(dateRange.to, "MMM d HH:mm")}
          </span>

          <span style={{
            fontSize: 10, fontWeight: 600, color: "var(--color-accent)",
            fontFamily: "var(--font-mono)", minWidth: 28, textAlign: "center",
          }}>
            {STEPS[currentStep].label}
          </span>
        </div>
      )}

      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: "4px 12px", borderRadius: 12,
          border: "1px solid var(--color-border)",
          background: "rgba(17,24,39,0.85)", cursor: "pointer",
          fontSize: 9, color: "var(--color-text-muted)",
          fontFamily: "var(--font-mono)", backdropFilter: "blur(8px)",
        }}
      >
        {expanded ? "Hide timeline" : `Timeline: ${STEPS[currentStep].label}`}
      </button>
    </div>
  );
}
