import type { CSSProperties } from "react";
import { format } from "date-fns";
import type { ImageryAnalysis, ImageryScene } from "@/services/api";

interface ImageryPanelProps {
  open: boolean;
  provider: "capella" | "maxar";
  loading: boolean;
  scenes: ImageryScene[];
  selectedSceneId: string | null;
  analysis: ImageryAnalysis | null;
  analyzingSceneId: string | null;
  onClose: () => void;
  onProviderChange: (provider: "capella" | "maxar") => void;
  onRefresh: () => void;
  onSelectScene: (sceneId: string) => void;
  onAnalyze: (scene: ImageryScene) => void;
}

export default function ImageryPanel({
  open,
  provider,
  loading,
  scenes,
  selectedSceneId,
  analysis,
  analyzingSceneId,
  onClose,
  onProviderChange,
  onRefresh,
  onSelectScene,
  onAnalyze,
}: ImageryPanelProps) {
  if (!open) return null;

  const selectedScene = scenes.find((scene) => scene.id === selectedSceneId) ?? scenes[0] ?? null;

  return (
    <div style={{
      position: "absolute",
      top: 72,
      right: 12,
      width: 340,
      maxHeight: "calc(100% - 140px)",
      display: "flex",
      flexDirection: "column",
      gap: 12,
      padding: 14,
      borderRadius: 12,
      border: "1px solid var(--color-border)",
      background: "rgba(15,23,42,0.94)",
      backdropFilter: "blur(10px)",
      boxShadow: "0 20px 60px rgba(2,6,23,0.35)",
      overflow: "hidden",
      zIndex: 20,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--color-text-muted)" }}>
            Public Imagery
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text-primary)" }}>
            {provider === "capella" ? "Capella SAR" : "Maxar Open Data"}
          </div>
        </div>
        <button onClick={onClose} style={iconButtonStyle}>Close</button>
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={() => onProviderChange("capella")}
          style={tabButtonStyle(provider === "capella")}
        >
          Capella
        </button>
        <button
          onClick={() => onProviderChange("maxar")}
          style={tabButtonStyle(provider === "maxar")}
        >
          Maxar
        </button>
        <button onClick={onRefresh} style={{ ...iconButtonStyle, marginLeft: "auto" }}>
          Refresh
        </button>
      </div>

      <div style={{ fontSize: 11, color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
        Searches the current map viewport and active date range. Capella scenes can be analyzed as SAR intensity windows directly from the panel.
      </div>

      <div style={{ overflowY: "auto", display: "flex", flexDirection: "column", gap: 8, paddingRight: 2 }}>
        {loading && (
          <div style={emptyStateStyle}>
            Querying {provider === "capella" ? "Capella" : "Maxar"} catalog...
          </div>
        )}

        {!loading && scenes.length === 0 && (
          <div style={emptyStateStyle}>
            No scenes matched this viewport and date range.
          </div>
        )}

        {!loading && scenes.map((scene) => {
          const isSelected = scene.id === selectedSceneId;
          return (
            <button
              key={`${scene.provider}:${scene.id}`}
              onClick={() => onSelectScene(scene.id)}
              style={{
                display: "grid",
                gridTemplateColumns: "88px 1fr",
                gap: 10,
                alignItems: "start",
                width: "100%",
                padding: 10,
                borderRadius: 10,
                border: isSelected ? "1px solid rgba(56,189,248,0.6)" : "1px solid rgba(148,163,184,0.18)",
                background: isSelected ? "rgba(15,118,110,0.16)" : "rgba(15,23,42,0.55)",
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <div style={{
                width: 88,
                height: 66,
                borderRadius: 8,
                overflow: "hidden",
                background: "rgba(30,41,59,0.65)",
                border: "1px solid rgba(148,163,184,0.12)",
              }}>
                {scene.thumbnailUrl ? (
                  <img
                    src={scene.thumbnailUrl}
                    alt={scene.title}
                    style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                  />
                ) : (
                  <div style={{ ...emptyStateStyle, height: "100%", border: "none", borderRadius: 0 }}>
                    No preview
                  </div>
                )}
              </div>

              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "var(--color-text-primary)", marginBottom: 4 }}>
                  {scene.title}
                </div>
                <MetaLine label="Captured" value={formatSceneDate(scene.capturedAt)} />
                <MetaLine
                  label="Mode"
                  value={stringValue(scene.metadata["instrumentMode"]) || stringValue(scene.metadata["platform"]) || "n/a"}
                />
                <MetaLine
                  label="Type"
                  value={stringValue(scene.metadata["productType"]) || stringValue(scene.metadata["eventTitle"]) || "n/a"}
                />

                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      onAnalyze(scene);
                    }}
                    style={actionButtonStyle}
                  >
                    {analyzingSceneId === scene.id ? "Analyzing..." : provider === "capella" ? "Analyze SAR" : "Analyze Scene"}
                  </button>
                  {scene.previewUrl && (
                    <a
                      href={scene.previewUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(event) => event.stopPropagation()}
                      style={linkButtonStyle}
                    >
                      Preview
                    </a>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {selectedScene && analysis && analysis.sceneId === selectedScene.id && (
        <div style={{
          borderTop: "1px solid rgba(148,163,184,0.14)",
          paddingTop: 12,
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--color-text-muted)" }}>
            Scene Analysis
          </div>
          <MetaLine label="Processor" value={analysis.processor} />
          <MetaLine label="Window" value={`${analysis.summary.window.width} x ${analysis.summary.window.height}`} />
          <MetaLine label="Bands" value={String(analysis.summary.window.bandCount)} />
          <MetaLine label="Mean" value={formatNumber(analysis.summary.bands[0]?.mean)} />
          <MetaLine label="P95" value={formatNumber(analysis.summary.bands[0]?.p95)} />
          {analysis.summary.sar && (
            <>
              <MetaLine label="Strong Scatter" value={formatPercent(analysis.summary.sar.strongScatterFraction)} />
              <MetaLine label="Edge Fraction" value={formatPercent(analysis.summary.sar.edgeFraction)} />
            </>
          )}
          {analysis.provider === "capella" && (
            <MetaLine label="SARKit Ready" value={analysis.sarkitAvailable ? "yes" : "not installed"} />
          )}
        </div>
      )}
    </div>
  );
}

function MetaLine({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 11 }}>
      <span style={{ color: "var(--color-text-muted)" }}>{label}</span>
      <span style={{ color: "var(--color-text-secondary)", textAlign: "right" }}>{value}</span>
    </div>
  );
}

function formatSceneDate(value: string | null) {
  if (!value) return "n/a";
  try {
    return format(new Date(value), "MMM d, yyyy HH:mm");
  } catch {
    return value;
  }
}

function formatNumber(value: number | null | undefined) {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}

function formatPercent(value: number | null | undefined) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

function stringValue(value: unknown) {
  return typeof value === "string" && value.trim() ? value : "";
}

const emptyStateStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: 76,
  padding: 12,
  borderRadius: 10,
  border: "1px dashed rgba(148,163,184,0.24)",
  color: "var(--color-text-muted)",
  fontSize: 11,
  textAlign: "center",
};

const iconButtonStyle: CSSProperties = {
  padding: "7px 10px",
  borderRadius: 8,
  border: "1px solid rgba(148,163,184,0.18)",
  background: "rgba(30,41,59,0.55)",
  color: "var(--color-text-secondary)",
  fontSize: 11,
  cursor: "pointer",
};

const actionButtonStyle: CSSProperties = {
  padding: "6px 9px",
  borderRadius: 8,
  border: "1px solid rgba(56,189,248,0.28)",
  background: "rgba(14,116,144,0.18)",
  color: "#bae6fd",
  fontSize: 11,
  cursor: "pointer",
};

const linkButtonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "6px 9px",
  borderRadius: 8,
  border: "1px solid rgba(148,163,184,0.18)",
  background: "rgba(30,41,59,0.4)",
  color: "var(--color-text-secondary)",
  fontSize: 11,
  textDecoration: "none",
};

function tabButtonStyle(active: boolean): CSSProperties {
  return {
    padding: "8px 12px",
    borderRadius: 8,
    border: active ? "1px solid rgba(56,189,248,0.5)" : "1px solid rgba(148,163,184,0.18)",
    background: active ? "rgba(8,145,178,0.18)" : "rgba(30,41,59,0.5)",
    color: active ? "#e0f2fe" : "var(--color-text-secondary)",
    fontSize: 11,
    fontWeight: 700,
    cursor: "pointer",
  };
}
