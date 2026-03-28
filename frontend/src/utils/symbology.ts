export type SeverityLevel = "high" | "medium" | "low";

export interface SeverityMeta {
  level: SeverityLevel;
  label: "HIGH" | "MEDIUM" | "LOW";
  color: string;
}

export interface CorroborationMeta {
  label: "CORROBORATED" | "MULTI-SOURCE" | "SINGLE SOURCE";
  color: string;
  icon: string;
}

const SEVERITY_META: Record<SeverityLevel, SeverityMeta> = {
  high: { level: "high", label: "HIGH", color: "#ef4444" },
  medium: { level: "medium", label: "MEDIUM", color: "#f59e0b" },
  low: { level: "low", label: "LOW", color: "#3b82f6" },
};

export function severityFromZScore(value?: number | null): SeverityMeta {
  const z = Number.isFinite(value) ? Number(value) : 0;
  if (z > 5) return SEVERITY_META.high;
  if (z >= 2) return SEVERITY_META.medium;
  return SEVERITY_META.low;
}

export function severityFromConfirmationStatus(status?: string | null): SeverityMeta {
  if (status === "corroborated") return SEVERITY_META.high;
  if (status === "multi_source") return SEVERITY_META.medium;
  return SEVERITY_META.low;
}

export function corroborationBadgeFromCount(count: number): CorroborationMeta {
  if (count >= 3) return { label: "CORROBORATED", color: "#10b981", icon: "✓" };
  if (count === 2) return { label: "MULTI-SOURCE", color: "#3b82f6", icon: "⊚" };
  return { label: "SINGLE SOURCE", color: "#f59e0b", icon: "•" };
}

