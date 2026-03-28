/**
 * MeasureTools — distance measurement, radius, and coordinate readout.
 * Essential OSINT toolkit for calculating distances between points.
 *
 * Uses Haversine formula for spherical distance (no external deps).
 */
import { useState, useEffect, type RefObject } from "react";
import type { MapRef } from "react-map-gl/maplibre";

interface Point {
  lng: number;
  lat: number;
}

interface Props {
  mapRef: RefObject<MapRef | null>;
}

export default function MeasureTools({ mapRef }: Props) {
  const [mode, setMode] = useState<"off" | "distance" | "radius">("off");
  const [points, setPoints] = useState<Point[]>([]);
  const [cursor, setCursor] = useState<Point | null>(null);

  // Handle map clicks when measuring
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map || mode === "off") return;

    const handleClick = (e: maplibregl.MapMouseEvent) => {
      const pt: Point = { lng: e.lngLat.lng, lat: e.lngLat.lat };
      setPoints((prev) => [...prev, pt]);
    };

    const handleMove = (e: maplibregl.MapMouseEvent) => {
      setCursor({ lng: e.lngLat.lng, lat: e.lngLat.lat });
    };

    map.on("click", handleClick);
    map.on("mousemove", handleMove);
    map.getCanvas().style.cursor = "crosshair";

    return () => {
      map.off("click", handleClick);
      map.off("mousemove", handleMove);
      map.getCanvas().style.cursor = "";
    };
  }, [mapRef, mode]);

  // Draw measurement lines/circles on the map
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;

    // Clean up previous drawings
    if (map.getLayer("measure-line")) map.removeLayer("measure-line");
    if (map.getLayer("measure-points")) map.removeLayer("measure-points");
    if (map.getSource("measure-data")) map.removeSource("measure-data");

    if (mode === "off" || points.length === 0) return;

    const allPoints = cursor ? [...points, cursor] : points;
    const features: GeoJSON.Feature[] = [];

    // Point markers
    allPoints.forEach((p) => {
      features.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: [p.lng, p.lat] },
        properties: {},
      });
    });

    // Line connecting points
    if (allPoints.length >= 2) {
      features.push({
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: allPoints.map((p) => [p.lng, p.lat]),
        },
        properties: {},
      });
    }

    map.addSource("measure-data", {
      type: "geojson",
      data: { type: "FeatureCollection", features },
    });

    map.addLayer({
      id: "measure-line",
      type: "line",
      source: "measure-data",
      paint: {
        "line-color": "#f59e0b",
        "line-width": 2,
        "line-dasharray": [4, 2],
      },
      filter: ["==", "$type", "LineString"],
    });

    map.addLayer({
      id: "measure-points",
      type: "circle",
      source: "measure-data",
      paint: {
        "circle-radius": 5,
        "circle-color": "#f59e0b",
        "circle-stroke-color": "#fff",
        "circle-stroke-width": 1,
      },
      filter: ["==", "$type", "Point"],
    });

    return () => {
      if (map.getLayer("measure-line")) map.removeLayer("measure-line");
      if (map.getLayer("measure-points")) map.removeLayer("measure-points");
      if (map.getSource("measure-data")) map.removeSource("measure-data");
    };
  }, [mapRef, mode, points, cursor]);

  const totalDistance = computeTotalDistance(cursor ? [...points, cursor] : points);

  const clear = () => {
    setPoints([]);
    setCursor(null);
    setMode("off");
  };

  const activate = (m: "distance" | "radius") => {
    setPoints([]);
    setCursor(null);
    setMode(m === mode ? "off" : m);
  };

  return (
    <div style={{ position: "absolute", top: 12, left: 12, zIndex: 5, display: "flex", flexDirection: "column", gap: 4 }}>
      {/* Toolbar */}
      <div style={{ display: "flex", gap: 4 }}>
        <ToolButton
          active={mode === "distance"}
          onClick={() => activate("distance")}
          title="Measure distance"
        >
          Ruler
        </ToolButton>
        <ToolButton
          active={mode === "radius"}
          onClick={() => activate("radius")}
          title="Measure radius"
        >
          Radius
        </ToolButton>
        {mode !== "off" && (
          <ToolButton active={false} onClick={clear} title="Clear measurement">
            Clear
          </ToolButton>
        )}
      </div>

      {/* Result display */}
      {mode !== "off" && points.length > 0 && (
        <div style={{
          padding: "6px 10px", borderRadius: 6,
          background: "rgba(13,19,32,0.92)", border: "1px solid var(--color-border)",
          backdropFilter: "blur(8px)", fontSize: 11, minWidth: 160,
        }}>
          <div style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "#f59e0b" }}>
            {formatDistance(totalDistance)}
          </div>
          {points.length >= 2 && (
            <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 2 }}>
              {points.length} points | bearing {computeBearing(points[0], points[points.length - 1]).toFixed(1)} deg
            </div>
          )}
          {cursor && (
            <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 2, fontFamily: "var(--font-mono)" }}>
              {cursor.lat.toFixed(5)}, {cursor.lng.toFixed(5)}
            </div>
          )}
        </div>
      )}

      {/* Coordinate readout when no tool active */}
      {mode === "off" && cursor && (
        <div style={{
          position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)",
          padding: "3px 10px", borderRadius: 4, fontSize: 9,
          background: "rgba(13,19,32,0.8)", color: "var(--color-text-muted)",
          fontFamily: "var(--font-mono)",
        }}>
          {cursor.lat.toFixed(5)}, {cursor.lng.toFixed(5)}
        </div>
      )}
    </div>
  );
}

function ToolButton({
  active, onClick, title, children,
}: { active: boolean; onClick: () => void; title: string; children: React.ReactNode }) {
  return (
    <button onClick={onClick} title={title} style={{
      padding: "6px 10px", borderRadius: 6, border: "none", fontSize: 10, fontWeight: 600,
      cursor: "pointer",
      background: active ? "var(--color-accent-muted)" : "var(--color-surface)",
      color: active ? "var(--color-accent)" : "var(--color-text-muted)",
      boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
    }}>
      {children}
    </button>
  );
}

// ── Math helpers ──────────────────────────────────────────────────────────────

function haversineDistance(a: Point, b: Point): number {
  const R = 6371000; // Earth radius in meters
  const dLat = (b.lat - a.lat) * Math.PI / 180;
  const dLng = (b.lng - a.lng) * Math.PI / 180;
  const sinLat = Math.sin(dLat / 2);
  const sinLng = Math.sin(dLng / 2);
  const h = sinLat * sinLat + Math.cos(a.lat * Math.PI / 180) * Math.cos(b.lat * Math.PI / 180) * sinLng * sinLng;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function computeTotalDistance(pts: Point[]): number {
  let total = 0;
  for (let i = 1; i < pts.length; i++) {
    total += haversineDistance(pts[i - 1], pts[i]);
  }
  return total;
}

function computeBearing(a: Point, b: Point): number {
  const dLng = (b.lng - a.lng) * Math.PI / 180;
  const lat1 = a.lat * Math.PI / 180;
  const lat2 = b.lat * Math.PI / 180;
  const y = Math.sin(dLng) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
  return ((Math.atan2(y, x) * 180 / Math.PI) + 360) % 360;
}

function formatDistance(meters: number): string {
  if (meters < 1000) return `${meters.toFixed(0)} m`;
  if (meters < 100000) return `${(meters / 1000).toFixed(2)} km`;
  return `${(meters / 1000).toFixed(0)} km (${(meters / 1609.344).toFixed(0)} mi)`;
}
