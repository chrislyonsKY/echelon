/**
 * EvidenceTab — displays video/media evidence attached to a signal event.
 *
 * Core policy: "Video is evidence attached to an event; provenance determines
 * trust, graphic classification determines presentation."
 *
 * Graphic filtering:
 * - Blur or hide graphic thumbnails by default
 * - No autoplay
 * - Click-through warning for graphic content
 * - User can set preference: hide | blur | show
 * - Model-flagged content is always reviewable, never permanently discarded
 */
import { useState, useEffect } from "react";
import { apiClient } from "@/services/api";
import { format } from "date-fns";

interface EvidenceItem {
  id: string;
  signalId: string;
  type: string;
  url: string;
  platform: string | null;
  thumbnailUrl: string | null;
  title: string | null;
  description: string | null;
  author: string | null;
  language: string | null;
  publishedAt: string | null;
  attachedAt: string | null;
  provenanceFamily: string | null;
  confirmationPolicy: string | null;
  geolocationStatus: string;
  timeVerificationStatus: string;
  graphicFlag: boolean;
  graphicConfidence: number | null;
  graphicReason: string | null;
  reviewStatus: string;
  restricted: boolean;
  restrictedReason: string | null;
  contentHash: string | null;
}

type GraphicPref = "hide" | "blur" | "show";

const PROVENANCE_BADGES: Record<string, { label: string; color: string }> = {
  official: { label: "OFFICIAL", color: "#00c48c" },
  ugc: { label: "UGC", color: "#e5a400" },
  aggregator: { label: "AGG", color: "#7c8db5" },
  context_only: { label: "CTX", color: "#94a3b8" },
};

const STATUS_BADGES: Record<string, { label: string; color: string }> = {
  geolocated: { label: "GEO", color: "#2d8cf0" },
  verified: { label: "TIME-OK", color: "#00c48c" },
  unverified: { label: "UNVERIFIED", color: "#94a3b8" },
  disputed: { label: "DISPUTED", color: "#f04444" },
};

interface Props {
  signalId: string;
}

export default function EvidenceTab({ signalId }: Props) {
  const [items, setItems] = useState<EvidenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [graphicPref, setGraphicPref] = useState<GraphicPref>(() => {
    return (localStorage.getItem("echelon:graphic-pref") as GraphicPref) || "blur";
  });
  const [revealedIds, setRevealedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    setLoading(true);
    apiClient
      .get<EvidenceItem[]>(`/evidence/for/${signalId}`)
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [signalId]);

  const updatePref = (pref: GraphicPref) => {
    setGraphicPref(pref);
    localStorage.setItem("echelon:graphic-pref", pref);
  };

  const revealItem = (id: string) => {
    setRevealedIds((prev) => new Set(prev).add(id));
  };

  if (loading) {
    return <div style={{ padding: 16, color: "var(--color-text-muted)", fontSize: 11 }}>Loading evidence...</div>;
  }

  return (
    <div style={{ padding: "8px 0" }}>
      {/* Header */}
      <div style={{
        padding: "6px 16px", display: "flex", justifyContent: "space-between", alignItems: "center",
        borderBottom: "1px solid var(--color-border)", marginBottom: 8,
      }}>
        <span style={{ fontSize: 10, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Evidence ({items.length})
        </span>
        <div style={{ display: "flex", gap: 2 }}>
          {(["hide", "blur", "show"] as const).map((pref) => (
            <button
              key={pref}
              onClick={() => updatePref(pref)}
              title={`Graphic content: ${pref}`}
              style={{
                padding: "2px 6px", borderRadius: 3, border: "none", fontSize: 9, cursor: "pointer",
                background: graphicPref === pref ? "var(--color-accent-muted)" : "none",
                color: graphicPref === pref ? "var(--color-accent)" : "var(--color-text-muted)",
              }}
            >
              {pref}
            </button>
          ))}
        </div>
      </div>

      {items.length === 0 ? (
        <div style={{ padding: "16px", textAlign: "center", color: "var(--color-text-muted)", fontSize: 11 }}>
          No evidence attached to this event.
        </div>
      ) : (
        items.map((item) => {
          const isGraphic = item.graphicFlag;
          const isRevealed = revealedIds.has(item.id);
          const shouldBlur = isGraphic && graphicPref === "blur" && !isRevealed;
          const shouldHide = isGraphic && graphicPref === "hide" && !isRevealed;

          return (
            <div key={item.id} style={{
              padding: "10px 16px", borderBottom: "1px solid rgba(30,45,70,0.3)",
            }}>
              {/* Restricted content — non-dismissable warning */}
              {item.restricted && (
                <div style={{
                  padding: "10px 12px", marginBottom: 8, borderRadius: 4,
                  background: "rgba(240,68,68,0.15)", border: "1px solid rgba(240,68,68,0.3)",
                }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "var(--color-danger)", marginBottom: 4 }}>
                    RESTRICTED CONTENT
                  </div>
                  <div style={{ fontSize: 9, color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                    This evidence is classified as {item.restrictedReason?.replace(/_/g, " ") || "restricted"}.
                    It is retained for investigative purposes only and is not publicly amplifiable.
                    {item.contentHash && (
                      <span style={{ display: "block", marginTop: 4, fontFamily: "var(--font-mono)", fontSize: 8, color: "var(--color-text-muted)" }}>
                        Hash: {item.contentHash.slice(0, 16)}...
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Thumbnail */}
              {item.thumbnailUrl && !shouldHide && !item.restricted && (
                <div style={{ position: "relative", marginBottom: 8 }}>
                  <img
                    src={item.thumbnailUrl}
                    alt={item.title || "Evidence thumbnail"}
                    style={{
                      width: "100%", height: 120, objectFit: "cover", borderRadius: 4,
                      filter: shouldBlur ? "blur(20px)" : "none",
                    }}
                  />
                  {shouldBlur && (
                    <button
                      onClick={() => revealItem(item.id)}
                      style={{
                        position: "absolute", inset: 0, display: "flex", alignItems: "center",
                        justifyContent: "center", background: "rgba(0,0,0,0.6)", border: "none",
                        borderRadius: 4, cursor: "pointer", color: "#fff", fontSize: 11, fontWeight: 600,
                      }}
                    >
                      Content flagged as {item.graphicReason || "graphic"}.
                      Click to reveal.
                    </button>
                  )}
                </div>
              )}

              {shouldHide && isGraphic && (
                <div style={{
                  padding: "12px", background: "rgba(240,68,68,0.1)", borderRadius: 4, marginBottom: 8,
                  fontSize: 10, color: "var(--color-danger)", textAlign: "center",
                }}>
                  Graphic content hidden ({item.graphicReason || "flagged"}).
                  <button onClick={() => revealItem(item.id)} style={{
                    marginLeft: 8, background: "none", border: "1px solid var(--color-danger)",
                    borderRadius: 3, padding: "2px 6px", color: "var(--color-danger)",
                    cursor: "pointer", fontSize: 9,
                  }}>
                    Reveal
                  </button>
                </div>
              )}

              {/* Title + metadata */}
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-primary)", marginBottom: 4 }}>
                {item.title || "Untitled evidence"}
              </div>

              {/* Badges row */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 6 }}>
                {/* Type badge */}
                <Badge label={item.type.toUpperCase()} color="#2d8cf0" />

                {/* Platform */}
                {item.platform && <Badge label={item.platform} color="#7c8db5" />}

                {/* Provenance */}
                {item.provenanceFamily && PROVENANCE_BADGES[item.provenanceFamily] && (
                  <Badge {...PROVENANCE_BADGES[item.provenanceFamily]} />
                )}

                {/* Geolocation */}
                {item.geolocationStatus !== "unverified" && STATUS_BADGES[item.geolocationStatus] && (
                  <Badge {...STATUS_BADGES[item.geolocationStatus]} />
                )}
                {item.geolocationStatus === "geolocated" && (
                  <Badge label="GEO" color="#2d8cf0" />
                )}

                {/* Time verification */}
                {item.timeVerificationStatus !== "unverified" && (
                  <Badge
                    label={item.timeVerificationStatus === "verified" ? "TIME-OK" : "TIME-?"}
                    color={item.timeVerificationStatus === "verified" ? "#00c48c" : "#e5a400"}
                  />
                )}

                {/* Restricted flag — perpetrator/terrorist content */}
                {item.restricted && <Badge label="RESTRICTED" color="#f04444" />}

                {/* Graphic flag */}
                {isGraphic && !item.restricted && <Badge label="GRAPHIC" color="#f04444" />}

                {/* Review status */}
                {item.reviewStatus === "human_approved" && <Badge label="REVIEWED" color="#00c48c" />}
                {item.reviewStatus === "auto_flagged" && <Badge label="AUTO-FLAG" color="#e5a400" />}
              </div>

              {/* Details */}
              <div style={{ fontSize: 10, color: "var(--color-text-secondary)" }}>
                {item.author && <span>{item.author} | </span>}
                {item.publishedAt && <span>{format(new Date(item.publishedAt), "MMM d, yyyy HH:mm")} | </span>}
                {item.language && <span>{item.language}</span>}
              </div>

              {/* Link — no autoplay */}
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "inline-block", marginTop: 6, fontSize: 10,
                  color: "var(--color-accent)", textDecoration: "none",
                }}
              >
                Open source {item.platform ? `on ${item.platform}` : ""} &rarr;
              </a>
            </div>
          );
        })
      )}
    </div>
  );
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span style={{
      fontSize: 8, fontWeight: 700, padding: "1px 4px", borderRadius: 3,
      background: `${color}22`, color, border: `1px solid ${color}44`,
      letterSpacing: "0.03em",
    }}>
      {label}
    </span>
  );
}
