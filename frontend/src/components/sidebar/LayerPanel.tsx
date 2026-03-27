/**
 * LayerPanel — sidebar tab for toggling individual signal feed overlays.
 */
import { useEchelonStore, type LayerVisibility } from "@/store/echelonStore";

const LAYERS: Array<{ id: keyof LayerVisibility; label: string; description: string }> = [
  { id: "convergenceHeatmap",  label: "Convergence Heatmap",   description: "Z-score overlay across all signals" },
  { id: "gdeltEvents",          label: "GDELT Conflict Events",  description: "CAMEO-coded conflict and threat signals" },
  { id: "gfwVessels",          label: "GFW Vessel Anomalies",   description: "AIS gaps, loitering, port avoidance" },
  { id: "sentinel2",           label: "Sentinel-2 EO",          description: "Change detection (NBR anomalies)" },
  { id: "osmInfrastructure",   label: "OSM Infrastructure",     description: "Military sites, airfields, pipelines" },
  { id: "landscanPopulation",  label: "LandScan Population",    description: "NGA population density context" },
];

export default function LayerPanel() {
  const { layerVisibility, toggleLayer, signalWeights, setSignalWeight } = useEchelonStore();

  return (
    <div style={{ padding: 16 }}>
      <section aria-label="Layer visibility controls">
        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10 }}>
          Layers
        </div>
        {LAYERS.map((layer) => (
          <label
            key={layer.id}
            style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 12, cursor: "pointer" }}
          >
            <input
              type="checkbox"
              checked={layerVisibility[layer.id]}
              onChange={() => toggleLayer(layer.id)}
              aria-label={`Toggle ${layer.label} layer`}
              style={{ marginTop: 2, cursor: "pointer", accentColor: "var(--color-accent)" }}
            />
            <div>
              <div style={{ fontSize: 12, color: "var(--color-text-primary)" }}>{layer.label}</div>
              <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{layer.description}</div>
            </div>
          </label>
        ))}
      </section>

      {/* Advanced weight controls */}
      <details style={{ marginTop: 16 }}>
        <summary
          style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", cursor: "pointer", userSelect: "none" }}
        >
          Advanced: Signal Weights
        </summary>
        <div style={{ marginTop: 10 }}>
          {Object.entries(signalWeights).map(([key, value]) => (
            <div key={key} style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 3 }}>
                <span>{key.replace(/_/g, " ")}</span>
                <span style={{ fontFamily: "var(--font-mono)" }}>{value.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={value}
                onChange={(e) => setSignalWeight(key as keyof typeof signalWeights, parseFloat(e.target.value))}
                aria-label={`Weight for ${key} signal`}
                style={{ width: "100%", accentColor: "var(--color-accent)" }}
              />
            </div>
          ))}
          <p style={{ fontSize: 10, color: "var(--color-text-secondary)", marginTop: 8 }}>
            Weight adjustments affect the visual preview. Server-side scoring always uses validated defaults.
          </p>
        </div>
      </details>
    </div>
  );
}
