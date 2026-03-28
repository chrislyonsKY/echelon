import { type CSSProperties, type ReactNode, useEffect, useMemo, useState } from "react";
import { format, subDays } from "date-fns";
import { eventsApi, signalsApi, type EchelonEvent, type SignalEvent } from "@/services/api";
import { useEchelonStore } from "@/store/echelonStore";
import { findCountryByName } from "@/utils/countries";

export default function CountryOverview() {
  const {
    countryOverviewOpen,
    countryOverviewCountry,
    closeCountryOverview,
    setViewState,
    setSidebarOpen,
    setSidebarTab,
    setSelectedEventId,
  } = useEchelonStore();
  const [loading, setLoading] = useState(false);
  const [signals24h, setSignals24h] = useState<SignalEvent[]>([]);
  const [signals7d, setSignals7d] = useState<SignalEvent[]>([]);
  const [events, setEvents] = useState<EchelonEvent[]>([]);

  const country = findCountryByName(countryOverviewCountry);

  useEffect(() => {
    if (!countryOverviewOpen || !country) return;
    const now = new Date();
    const to = format(now, "yyyy-MM-dd");
    const from24h = format(subDays(now, 1), "yyyy-MM-dd");
    const from7d = format(subDays(now, 7), "yyyy-MM-dd");
    setLoading(true);
    Promise.all([
      signalsApi.getForBbox(country.bbox, "", from24h, to),
      signalsApi.getForBbox(country.bbox, "", from7d, to),
      eventsApi.list({ bbox: country.bbox.join(","), days: 7 }),
    ])
      .then(([s24, s7, ev]) => {
        setSignals24h(s24);
        setSignals7d(s7);
        setEvents(ev);
      })
      .catch(() => {
        setSignals24h([]);
        setSignals7d([]);
        setEvents([]);
      })
      .finally(() => setLoading(false));
  }, [countryOverviewOpen, country?.name]);

  const activeSourceCount = useMemo(
    () => new Set(signals7d.map((signal) => signal.source)).size,
    [signals7d]
  );

  const topSignalTypes = useMemo(() => {
    const counts = new Map<string, number>();
    for (const signal of signals7d) {
      counts.set(signal.signalType, (counts.get(signal.signalType) || 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  }, [signals7d]);

  const trend = useMemo(() => buildTrend(signals7d), [signals7d]);

  if (!countryOverviewOpen || !country) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: "var(--topbar-height)",
        right: 0,
        bottom: 0,
        width: 380,
        background: "var(--color-surface)",
        borderLeft: "1px solid var(--color-border)",
        zIndex: 32,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "12px 16px",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <div>
          <div style={{ fontSize: 10, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 700 }}>
            Country Overview
          </div>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2 }}>
            {country.flag} {country.name}
          </div>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            onClick={() => {
              const [minLng, minLat, maxLng, maxLat] = country.bbox;
              setViewState({
                longitude: (minLng + maxLng) / 2,
                latitude: (minLat + maxLat) / 2,
                zoom: 5,
                pitch: 0,
                bearing: 0,
              });
            }}
            style={miniButton}
          >
            FLY TO
          </button>
          <button onClick={closeCountryOverview} style={miniButton}>
            CLOSE
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: 24, color: "var(--color-text-muted)", fontSize: 12 }}>Loading country metrics...</div>
      ) : (
        <div style={{ padding: 14, overflow: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 8 }}>
            <StatTile label="Signals 24h" value={String(signals24h.length)} />
            <StatTile label="Signals 7d" value={String(signals7d.length)} />
            <StatTile label="Active Sources" value={String(activeSourceCount)} />
            <StatTile label="Events 7d" value={String(events.length)} />
          </div>

          <Section title="Z-Score Trend (7d)">
            <Sparkline values={trend} />
          </Section>

          <Section title="Top Signal Types">
            {topSignalTypes.length === 0 ? (
              <span style={emptyText}>No signals in window.</span>
            ) : (
              topSignalTypes.map(([signalType, count]) => (
                <div key={signalType} style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 11, padding: "2px 0" }}>
                  <span style={{ color: "var(--color-text-secondary)" }}>{signalType.replace(/_/g, " ")}</span>
                  <span style={{ color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>{count}</span>
                </div>
              ))
            )}
          </Section>

          <Section title="Recent Events">
            {events.length === 0 ? (
              <span style={emptyText}>No clustered events in this window.</span>
            ) : (
              events.slice(0, 8).map((event) => (
                <button
                  key={event.id}
                  onClick={() => {
                    setSidebarOpen(true);
                    setSidebarTab("events");
                    setSelectedEventId(event.id);
                    closeCountryOverview();
                  }}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    background: "none",
                    border: "none",
                    borderBottom: "1px solid rgba(51,65,85,0.5)",
                    padding: "7px 0",
                    color: "var(--color-text-primary)",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 500, lineHeight: 1.4 }}>{event.title}</div>
                  <div style={{ fontSize: 9, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", marginTop: 2 }}>
                    {event.lastSeen ? format(new Date(event.lastSeen), "MMM d HH:mm") : ""}
                  </div>
                </button>
              ))
            )}
          </Section>
        </div>
      )}
    </div>
  );
}

function buildTrend(signals: SignalEvent[]): number[] {
  const bucket = Array.from({ length: 7 }, () => 0);
  const now = Date.now();
  for (const signal of signals) {
    if (!signal.occurredAt) continue;
    const ts = new Date(signal.occurredAt).getTime();
    const ageDays = Math.floor((now - ts) / (24 * 60 * 60 * 1000));
    if (ageDays < 0 || ageDays > 6) continue;
    const index = 6 - ageDays;
    bucket[index] = Math.max(bucket[index], signalScore(signal));
  }
  return bucket;
}

function signalScore(signal: SignalEvent): number {
  const payload = signal.rawPayload || {};
  const z =
    asNumber(payload.z_score) ??
    asNumber(payload.zScore) ??
    asNumber(payload.zscore) ??
    asNumber(payload.cell_zscore);
  return z ?? Math.max(0, signal.weight * 4);
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        border: "1px solid var(--color-border)",
        borderRadius: 6,
        background: "var(--color-surface-raised)",
        padding: "8px 10px",
      }}
    >
      <div style={{ fontSize: 10, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontFamily: "var(--font-mono)" }}>
        {label}
      </div>
      <div style={{ fontSize: 16, fontWeight: 700, marginTop: 2 }}>{value}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ border: "1px solid var(--color-border)", borderRadius: 6, padding: 10, background: "rgba(15,23,42,0.42)" }}>
      <div style={{ fontSize: 10, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 700, marginBottom: 8, fontFamily: "var(--font-mono)" }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function Sparkline({ values }: { values: number[] }) {
  const width = 320;
  const height = 56;
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const range = Math.max(0.01, max - min);
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(1, values.length - 1)) * (width - 4) + 2;
      const normalized = (value - min) / range;
      const y = height - 4 - normalized * (height - 8);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <line x1="0" y1={height - 3} x2={width} y2={height - 3} stroke="rgba(100,116,139,0.5)" strokeWidth="1" />
      <polyline points={points} fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

const miniButton: CSSProperties = {
  border: "1px solid var(--color-border)",
  borderRadius: 4,
  background: "transparent",
  color: "var(--color-text-secondary)",
  fontSize: 10,
  fontFamily: "var(--font-mono)",
  letterSpacing: "0.04em",
  padding: "3px 8px",
  cursor: "pointer",
};

const emptyText: CSSProperties = {
  fontSize: 11,
  color: "var(--color-text-muted)",
};
