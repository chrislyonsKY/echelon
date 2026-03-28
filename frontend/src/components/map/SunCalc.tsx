/**
 * SunCalc — built-in shadow trajectory calculator for OSINT.
 * Drop a pin, set date/time, see exact sun position and shadow direction.
 * Replaces the need for external SunCalc tools.
 *
 * Math: standard solar position algorithm (NOAA).
 */
import { useState, useEffect, type RefObject } from "react";
import type { MapRef } from "react-map-gl/maplibre";
import { format } from "date-fns";

interface SunPosition {
  altitude: number;  // degrees above horizon
  azimuth: number;   // degrees from north
  shadowLength: number; // relative (1 = same as object height)
  shadowDirection: number; // degrees from north
}

interface Props {
  mapRef: RefObject<MapRef | null>;
}

export default function SunCalcTool({ mapRef }: Props) {
  const [active, setActive] = useState(false);
  const [pin, setPin] = useState<{ lng: number; lat: number } | null>(null);
  const [date, setDate] = useState(format(new Date(), "yyyy-MM-dd"));
  const [time, setTime] = useState(format(new Date(), "HH:mm"));
  const [sunPos, setSunPos] = useState<SunPosition | null>(null);

  // Handle map click when active
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map || !active) return;

    const handler = (e: maplibregl.MapMouseEvent) => {
      setPin({ lng: e.lngLat.lng, lat: e.lngLat.lat });
    };
    map.on("click", handler);
    map.getCanvas().style.cursor = "crosshair";
    return () => {
      map.off("click", handler);
      map.getCanvas().style.cursor = "";
    };
  }, [mapRef, active]);

  // Compute sun position when pin/date/time change
  useEffect(() => {
    if (!pin) return;
    const dt = new Date(`${date}T${time}:00`);
    const pos = computeSunPosition(pin.lat, pin.lng, dt);
    setSunPos(pos);
  }, [pin, date, time]);

  // Draw shadow line on map
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map || !pin || !sunPos) return;

    if (map.getLayer("sun-shadow")) map.removeLayer("sun-shadow");
    if (map.getLayer("sun-pin")) map.removeLayer("sun-pin");
    if (map.getSource("sun-data")) map.removeSource("sun-data");

    if (sunPos.altitude <= 0) return; // Sun below horizon

    // Shadow line from pin in shadow direction
    const shadowLen = 0.005 * Math.min(sunPos.shadowLength, 10);
    const rad = sunPos.shadowDirection * Math.PI / 180;
    const endLng = pin.lng + shadowLen * Math.sin(rad) / Math.cos(pin.lat * Math.PI / 180);
    const endLat = pin.lat + shadowLen * Math.cos(rad);

    map.addSource("sun-data", {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: [
          { type: "Feature", geometry: { type: "Point", coordinates: [pin.lng, pin.lat] }, properties: {} },
          { type: "Feature", geometry: { type: "LineString", coordinates: [[pin.lng, pin.lat], [endLng, endLat]] }, properties: {} },
        ],
      },
    });

    map.addLayer({
      id: "sun-shadow",
      type: "line",
      source: "sun-data",
      paint: { "line-color": "#f59e0b", "line-width": 3, "line-opacity": 0.7 },
      filter: ["==", "$type", "LineString"],
    });

    map.addLayer({
      id: "sun-pin",
      type: "circle",
      source: "sun-data",
      paint: { "circle-radius": 7, "circle-color": "#f59e0b", "circle-stroke-color": "#fff", "circle-stroke-width": 2 },
      filter: ["==", "$type", "Point"],
    });

    return () => {
      if (map.getLayer("sun-shadow")) map.removeLayer("sun-shadow");
      if (map.getLayer("sun-pin")) map.removeLayer("sun-pin");
      if (map.getSource("sun-data")) map.removeSource("sun-data");
    };
  }, [mapRef, pin, sunPos]);

  return (
    <div style={{ position: "absolute", top: 48, left: 12, zIndex: 5 }}>
      <button
        onClick={() => { setActive(!active); if (active) { setPin(null); setSunPos(null); } }}
        title="Sun/Shadow Calculator"
        style={{
          padding: "6px 10px", borderRadius: 6, border: "none", fontSize: 10, fontWeight: 600,
          cursor: "pointer",
          background: active ? "var(--color-accent-muted)" : "var(--color-surface)",
          color: active ? "#f59e0b" : "var(--color-text-muted)",
          boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
        }}
      >
        Sun
      </button>

      {active && pin && sunPos && (
        <div style={{
          marginTop: 4, padding: "10px 12px", borderRadius: 6,
          background: "rgba(17,24,39,0.92)", border: "1px solid var(--color-border)",
          backdropFilter: "blur(8px)", minWidth: 200,
        }}>
          <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={inputStyle} />
            <input type="time" value={time} onChange={(e) => setTime(e.target.value)} style={inputStyle} />
          </div>

          <div style={{ fontSize: 10, color: "var(--color-text-primary)" }}>
            <Row label="Altitude" value={`${sunPos.altitude.toFixed(1)} deg`} />
            <Row label="Azimuth" value={`${sunPos.azimuth.toFixed(1)} deg`} />
            <Row label="Shadow dir" value={`${sunPos.shadowDirection.toFixed(1)} deg`} />
            <Row label="Shadow len" value={sunPos.altitude > 0 ? `${sunPos.shadowLength.toFixed(1)}x` : "no shadow"} />
          </div>

          {sunPos.altitude <= 0 && (
            <div style={{ fontSize: 9, color: "var(--color-danger)", marginTop: 4 }}>
              Sun is below the horizon at this time.
            </div>
          )}

          <div style={{ fontSize: 8, color: "var(--color-text-muted)", marginTop: 6, fontFamily: "var(--font-mono)" }}>
            {pin.lat.toFixed(5)}, {pin.lng.toFixed(5)}
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "1px 0" }}>
      <span style={{ color: "var(--color-text-muted)" }}>{label}</span>
      <span style={{ fontFamily: "var(--font-mono)", color: "#f59e0b" }}>{value}</span>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "3px 6px", borderRadius: 4, border: "1px solid var(--color-border)",
  background: "var(--color-bg)", color: "var(--color-text-primary)", fontSize: 10, flex: 1,
};

// ── Solar position math (simplified NOAA algorithm) ──────────────────────────

function computeSunPosition(lat: number, lng: number, dt: Date): SunPosition {
  const dayOfYear = getDayOfYear(dt);
  const hour = dt.getHours() + dt.getMinutes() / 60;

  // Equation of time (minutes)
  const B = (360 / 365) * (dayOfYear - 81) * Math.PI / 180;
  const EoT = 9.87 * Math.sin(2 * B) - 7.53 * Math.cos(B) - 1.5 * Math.sin(B);

  // Solar declination
  const declination = 23.45 * Math.sin((360 / 365) * (dayOfYear - 81) * Math.PI / 180);

  // Solar time
  const solarNoon = 12 - lng / 15 - EoT / 60;
  const hourAngle = (hour - solarNoon) * 15;

  // Solar altitude
  const latRad = lat * Math.PI / 180;
  const decRad = declination * Math.PI / 180;
  const haRad = hourAngle * Math.PI / 180;

  const altitude = Math.asin(
    Math.sin(latRad) * Math.sin(decRad) +
    Math.cos(latRad) * Math.cos(decRad) * Math.cos(haRad)
  ) * 180 / Math.PI;

  // Solar azimuth
  const azimuthRad = Math.atan2(
    Math.sin(haRad),
    Math.cos(haRad) * Math.sin(latRad) - Math.tan(decRad) * Math.cos(latRad)
  );
  const azimuth = ((azimuthRad * 180 / Math.PI) + 180) % 360;

  // Shadow
  const shadowLength = altitude > 0 ? 1 / Math.tan(altitude * Math.PI / 180) : Infinity;
  const shadowDirection = (azimuth + 180) % 360;

  return { altitude, azimuth, shadowLength, shadowDirection };
}

function getDayOfYear(dt: Date): number {
  const start = new Date(dt.getFullYear(), 0, 0);
  return Math.floor((dt.getTime() - start.getTime()) / 86400000);
}
