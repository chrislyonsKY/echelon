/**
 * ExifDropZone — drag-and-drop images onto the map to extract EXIF GPS data.
 * If coordinates are found, drops a pin at the location.
 * Client-side only — no images are uploaded to the server.
 *
 * Reads EXIF GPS data from JPEG files using DataView (no external deps).
 */
import { useState, useCallback } from "react";
import { useEchelonStore } from "@/store/echelonStore";

interface ExifResult {
  lat: number | null;
  lng: number | null;
  timestamp: string | null;
  camera: string | null;
  fileName: string;
}

export default function ExifDropZone() {
  const { setViewState } = useEchelonStore();
  const [isDragging, setIsDragging] = useState(false);
  const [result, setResult] = useState<ExifResult | null>(null);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (!file || !file.type.startsWith("image/")) return;

    const buffer = await file.arrayBuffer();
    const exif = parseExifGps(buffer);

    const res: ExifResult = {
      lat: exif?.lat ?? null,
      lng: exif?.lng ?? null,
      timestamp: exif?.timestamp ?? null,
      camera: exif?.camera ?? null,
      fileName: file.name,
    };
    setResult(res);

    if (res.lat !== null && res.lng !== null) {
      setViewState({
        longitude: res.lng,
        latitude: res.lat,
        zoom: 14,
        pitch: 0,
        bearing: 0,
      });
    }
  }, [setViewState]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  return (
    <>
      {/* Invisible drop zone covering the map */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={() => setIsDragging(false)}
        style={{
          position: "absolute", inset: 0, zIndex: isDragging ? 100 : -1,
          pointerEvents: isDragging ? "auto" : "none",
        }}
      />

      {/* Drag overlay */}
      {isDragging && (
        <div style={{
          position: "absolute", inset: 0, zIndex: 99,
          background: "rgba(45,140,240,0.15)",
          border: "3px dashed var(--color-accent)",
          display: "flex", alignItems: "center", justifyContent: "center",
          pointerEvents: "none",
        }}>
          <div style={{
            padding: "16px 24px", borderRadius: 8,
            background: "rgba(17,24,39,0.95)", border: "1px solid var(--color-accent)",
            fontSize: 14, fontWeight: 600, color: "var(--color-accent)",
          }}>
            Drop image to extract EXIF location
          </div>
        </div>
      )}

      {/* Result toast */}
      {result && (
        <div style={{
          position: "absolute", top: 56, right: 12, zIndex: 20,
          padding: "10px 14px", borderRadius: 6, maxWidth: 280,
          background: "var(--color-surface-raised)", border: "1px solid var(--color-border)",
          boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-primary)" }}>
              EXIF Analysis
            </span>
            <button onClick={() => setResult(null)} style={{
              background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 12,
            }}>x</button>
          </div>

          <div style={{ fontSize: 10, color: "var(--color-text-secondary)" }}>
            <Row label="File" value={result.fileName} />
            {result.lat !== null && result.lng !== null ? (
              <>
                <Row label="GPS" value={`${result.lat.toFixed(6)}, ${result.lng.toFixed(6)}`} />
                <div style={{ fontSize: 9, color: "var(--color-success)", marginTop: 4 }}>
                  Pin dropped at GPS coordinates
                </div>
              </>
            ) : (
              <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 4 }}>
                No GPS data found in image metadata.
              </div>
            )}
            {result.timestamp && <Row label="Time" value={result.timestamp} />}
            {result.camera && <Row label="Camera" value={result.camera} />}
          </div>
        </div>
      )}
    </>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, padding: "1px 0" }}>
      <span style={{ color: "var(--color-text-muted)" }}>{label}</span>
      <span style={{ fontFamily: "var(--font-mono)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 160 }}>
        {value}
      </span>
    </div>
  );
}

// ── EXIF GPS parser (minimal, no external deps) ─────────────────────────────

interface ExifGps {
  lat: number;
  lng: number;
  timestamp: string | null;
  camera: string | null;
}

function parseExifGps(buffer: ArrayBuffer): ExifGps | null {
  const view = new DataView(buffer);

  // Check JPEG magic
  if (view.getUint16(0) !== 0xFFD8) return null;

  let offset = 2;
  while (offset < view.byteLength - 2) {
    const marker = view.getUint16(offset);
    if (marker === 0xFFE1) {
      // APP1 (EXIF)
      const length = view.getUint16(offset + 2);
      return parseExifBlock(view, offset + 4, length);
    }
    if ((marker & 0xFF00) !== 0xFF00) break;
    offset += 2 + view.getUint16(offset + 2);
  }
  return null;
}

function parseExifBlock(view: DataView, start: number, _length: number): ExifGps | null {
  // Check "Exif\0\0"
  if (view.getUint32(start) !== 0x45786966 || view.getUint16(start + 4) !== 0) return null;

  const tiffStart = start + 6;
  const byteOrder = view.getUint16(tiffStart);
  const le = byteOrder === 0x4949; // Intel byte order

  const getU16 = (o: number) => view.getUint16(o, le);
  const getU32 = (o: number) => view.getUint32(o, le);

  const ifdOffset = getU32(tiffStart + 4);
  const ifd0Start = tiffStart + ifdOffset;

  let gpsOffset = 0;
  let camera: string | null = null;
  const numEntries = getU16(ifd0Start);

  for (let i = 0; i < numEntries; i++) {
    const entryStart = ifd0Start + 2 + i * 12;
    if (entryStart + 12 > view.byteLength) break;
    const tag = getU16(entryStart);
    if (tag === 0x8825) { // GPSInfo
      gpsOffset = getU32(entryStart + 8);
    }
    if (tag === 0x0110) { // Model
      const count = getU32(entryStart + 4);
      const valOffset = count <= 4 ? entryStart + 8 : tiffStart + getU32(entryStart + 8);
      camera = readString(view, valOffset, Math.min(count, 50));
    }
  }

  if (!gpsOffset) return null;

  const gpsStart = tiffStart + gpsOffset;
  const gpsEntries = getU16(gpsStart);
  let lat = 0, lng = 0, latRef = "N", lngRef = "E";

  for (let i = 0; i < gpsEntries; i++) {
    const e = gpsStart + 2 + i * 12;
    if (e + 12 > view.byteLength) break;
    const tag = getU16(e);
    const valOff = tiffStart + getU32(e + 8);

    if (tag === 1) latRef = String.fromCharCode(view.getUint8(e + 8));
    if (tag === 3) lngRef = String.fromCharCode(view.getUint8(e + 8));
    if (tag === 2) lat = readGpsCoord(view, valOff, le);
    if (tag === 4) lng = readGpsCoord(view, valOff, le);
  }

  if (lat === 0 && lng === 0) return null;
  if (latRef === "S") lat = -lat;
  if (lngRef === "W") lng = -lng;

  return { lat, lng, timestamp: null, camera };
}

function readGpsCoord(view: DataView, offset: number, le: boolean): number {
  const getU32 = (o: number) => view.getUint32(o, le);
  const d = getU32(offset) / getU32(offset + 4);
  const m = getU32(offset + 8) / getU32(offset + 12);
  const s = getU32(offset + 16) / getU32(offset + 20);
  return d + m / 60 + s / 3600;
}

function readString(view: DataView, offset: number, length: number): string {
  let str = "";
  for (let i = 0; i < length; i++) {
    const c = view.getUint8(offset + i);
    if (c === 0) break;
    str += String.fromCharCode(c);
  }
  return str.trim();
}
