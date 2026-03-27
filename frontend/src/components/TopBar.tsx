/**
 * TopBar — branding, date range selector, auth state, copilot toggle.
 */
import { useEchelonStore } from "@/store/echelonStore";
import { authApi } from "@/services/api";
import { format, subDays } from "date-fns";

const PRESETS = [
  { label: "24h",  days: 1 },
  { label: "7d",   days: 7 },
  { label: "30d",  days: 30 },
  { label: "90d",  days: 90 },
];

export default function TopBar() {
  const { user, setUser, dateRange, setDateRange, copilotOpen, setCopilotOpen } = useEchelonStore();

  const handleLogout = async () => {
    await authApi.logout();
    setUser(null);
  };

  return (
    <header
      role="banner"
      style={{
        height: "var(--topbar-height)",
        background: "var(--color-surface)",
        borderBottom: "1px solid var(--color-border)",
        display: "flex",
        alignItems: "center",
        padding: "0 16px",
        gap: 16,
        flexShrink: 0,
        zIndex: 10,
      }}
    >
      {/* Branding */}
      <div style={{ fontWeight: 700, fontSize: 15, letterSpacing: "0.1em", color: "var(--color-text-primary)", flexShrink: 0 }}>
        ECHELON
      </div>

      <div style={{ width: 1, height: 20, background: "var(--color-border)" }} />

      {/* Date range presets */}
      <nav aria-label="Date range presets" style={{ display: "flex", gap: 4 }}>
        {PRESETS.map((preset) => {
          const from = subDays(new Date(), preset.days);
          const active =
            format(dateRange.from, "yyyy-MM-dd") === format(from, "yyyy-MM-dd");
          return (
            <button
              key={preset.label}
              onClick={() => setDateRange(from, new Date())}
              aria-pressed={active}
              style={{
                padding: "3px 10px",
                borderRadius: 4,
                border: "1px solid",
                borderColor: active ? "var(--color-accent)" : "var(--color-border)",
                background: active ? "var(--color-accent)22" : "transparent",
                color: active ? "var(--color-accent)" : "var(--color-text-secondary)",
                cursor: "pointer",
                fontSize: 11,
                fontWeight: active ? 600 : 400,
              }}
            >
              {preset.label}
            </button>
          );
        })}
      </nav>

      <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>
        {format(dateRange.from, "MMM d")} — {format(dateRange.to, "MMM d, yyyy")}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Copilot toggle */}
      <button
        onClick={() => setCopilotOpen(!copilotOpen)}
        aria-pressed={copilotOpen}
        aria-label="Toggle copilot panel"
        style={{
          padding: "5px 12px",
          borderRadius: 6,
          border: "1px solid",
          borderColor: copilotOpen ? "var(--color-accent)" : "var(--color-border)",
          background: copilotOpen ? "var(--color-accent)22" : "transparent",
          color: copilotOpen ? "var(--color-accent)" : "var(--color-text-secondary)",
          cursor: "pointer",
          fontSize: 11,
          fontWeight: 600,
        }}
      >
        ✦ Copilot
      </button>

      {/* Auth */}
      {user ? (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>
            @{user.githubUsername}
          </span>
          <button
            onClick={handleLogout}
            style={{ padding: "4px 10px", borderRadius: 4, border: "1px solid var(--color-border)", background: "transparent", color: "var(--color-text-secondary)", cursor: "pointer", fontSize: 11 }}
          >
            Sign out
          </button>
        </div>
      ) : (
        <a
          href="/api/auth/login"
          style={{ padding: "5px 12px", borderRadius: 6, background: "var(--color-accent)", color: "#fff", textDecoration: "none", fontSize: 11, fontWeight: 600 }}
        >
          Sign in with GitHub
        </a>
      )}
    </header>
  );
}
