import { type CSSProperties, useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { apiClient, type SignalEvent } from "@/services/api";
import { useEchelonStore } from "@/store/echelonStore";
import { getDisplayTitle, truncateText } from "@/utils/language";

export default function TheaterOverlay() {
  const { dateRange, unreadAlertCount, setTheaterMode } = useEchelonStore();
  const [latest, setLatest] = useState<SignalEvent[]>([]);

  useEffect(() => {
    const load = () => {
      apiClient
        .get<SignalEvent[]>("/signals/latest?limit=18")
        .then(setLatest)
        .catch(() => setLatest([]));
    };
    load();
    const interval = setInterval(load, 60_000);
    return () => clearInterval(interval);
  }, []);

  const tickerText = useMemo(
    () =>
      latest
        .map((signal) => {
          const stamp = signal.occurredAt ? format(new Date(signal.occurredAt), "HH:mm") : "--:--";
          const title = truncateText(getDisplayTitle(signal, signal.signalType.replace(/_/g, " ")), 70);
          return `${stamp} ${title}`;
        })
        .join("   •   "),
    [latest]
  );

  return (
    <>
      <div
        style={{
          position: "absolute",
          top: 12,
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 40,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "7px 12px",
          borderRadius: 8,
          border: "1px solid var(--color-border)",
          background: "rgba(15,23,42,0.9)",
          backdropFilter: "blur(8px)",
        }}
      >
        <button
          onClick={() => setTheaterMode(false)}
          style={{
            border: "1px solid #f59e0b",
            borderRadius: 4,
            background: "rgba(245,158,11,0.14)",
            color: "#fbbf24",
            fontSize: 10,
            fontFamily: "var(--font-mono)",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            padding: "3px 8px",
            cursor: "pointer",
          }}
        >
          Exit
        </button>
        <span style={controlText}>
          {format(dateRange.from, "MMM d")} - {format(dateRange.to, "MMM d, yyyy")}
        </span>
        <span style={controlText}>Alerts: {unreadAlertCount}</span>
      </div>

      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          zIndex: 39,
          borderTop: "1px solid var(--color-border)",
          background: "rgba(2,6,23,0.9)",
          overflow: "hidden",
          height: 28,
          display: "flex",
          alignItems: "center",
        }}
      >
        <div
          style={{
            whiteSpace: "nowrap",
            fontSize: 11,
            color: "var(--color-text-secondary)",
            fontFamily: "var(--font-mono)",
            paddingLeft: "100%",
            animation: "theaterTicker 48s linear infinite",
          }}
        >
          {tickerText || "No recent events in ticker window."}
        </div>
      </div>
    </>
  );
}

const controlText: CSSProperties = {
  fontSize: 10,
  color: "var(--color-text-secondary)",
  fontFamily: "var(--font-mono)",
  letterSpacing: "0.05em",
  textTransform: "uppercase",
};
