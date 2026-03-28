/**
 * TopBar — branding, date range selector, auth state, copilot toggle.
 */
import { useEchelonStore } from "@/store/echelonStore";
import { authApi } from "@/services/api";
import { format, subDays } from "date-fns";
import SearchBar from "./SearchBar";
import RegionalMonitors from "./RegionalMonitors";
import ExportMenu from "./ExportMenu";

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
        boxShadow: "0 1px 8px rgba(0, 0, 0, 0.4)",
        display: "flex",
        alignItems: "center",
        padding: "0 20px",
        gap: 16,
        flexShrink: 0,
        zIndex: 10,
      }}
    >
      {/* Branding */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <svg width="20" height="20" viewBox="0 0 32 32" style={{ flexShrink: 0 }}>
          <path d="M16 4 L28 10 L28 22 L16 28 L4 22 L4 10 Z" fill="none" stroke="var(--color-accent)" strokeWidth="2"/>
          <circle cx="16" cy="16" r="3" fill="var(--color-danger)"/>
        </svg>
        <span style={{
          fontWeight: 700,
          fontSize: 14,
          letterSpacing: "0.12em",
          color: "var(--color-text-primary)",
          fontFamily: "var(--font-mono)",
        }}>
          ECHELON
        </span>
      </div>

      <div style={{ width: 1, height: 20, background: "var(--color-border)" }} />

      {/* Date range presets */}
      <nav aria-label="Date range presets" style={{ display: "flex", gap: 3 }}>
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
                padding: "4px 10px",
                borderRadius: 4,
                border: "1px solid",
                borderColor: active ? "var(--color-accent)" : "transparent",
                background: active ? "var(--color-accent-muted)" : "transparent",
                color: active ? "var(--color-accent)" : "var(--color-text-secondary)",
                cursor: "pointer",
                fontSize: 11,
                fontWeight: 500,
                fontFamily: "var(--font-mono)",
              }}
            >
              {preset.label}
            </button>
          );
        })}
      </nav>

      <span style={{
        fontSize: 11,
        color: "var(--color-text-muted)",
        fontFamily: "var(--font-mono)",
      }}>
        {format(dateRange.from, "MMM d")} — {format(dateRange.to, "MMM d, yyyy")}
      </span>

      <div style={{ width: 1, height: 20, background: "var(--color-border)" }} />

      {/* Regional monitors */}
      <RegionalMonitors />

      <div style={{ width: 1, height: 20, background: "var(--color-border)" }} />

      {/* Search */}
      <SearchBar />

      <div style={{ width: 1, height: 20, background: "var(--color-border)" }} />

      {/* Export */}
      <ExportMenu />

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Copilot toggle */}
      <button
        onClick={() => setCopilotOpen(!copilotOpen)}
        aria-pressed={copilotOpen}
        aria-label="Toggle copilot panel"
        style={{
          padding: "5px 14px",
          borderRadius: 6,
          border: "1px solid",
          borderColor: copilotOpen ? "var(--color-accent)" : "var(--color-border)",
          background: copilotOpen ? "var(--color-accent-muted)" : "transparent",
          color: copilotOpen ? "var(--color-accent)" : "var(--color-text-secondary)",
          cursor: "pointer",
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.02em",
        }}
      >
        Copilot
      </button>

      {/* Auth */}
      {user ? (
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{
            fontSize: 11,
            color: "var(--color-text-secondary)",
            fontFamily: "var(--font-mono)",
          }}>
            @{user.githubUsername}
          </span>
          <button
            onClick={handleLogout}
            style={{
              padding: "4px 12px",
              borderRadius: 4,
              border: "1px solid var(--color-border)",
              background: "transparent",
              color: "var(--color-text-secondary)",
              cursor: "pointer",
              fontSize: 11,
            }}
          >
            Sign out
          </button>
        </div>
      ) : (
        <a
          href="/api/auth/login"
          style={{
            padding: "5px 14px",
            borderRadius: 6,
            background: "var(--color-accent)",
            color: "#fff",
            textDecoration: "none",
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: "0.02em",
          }}
        >
          Sign in
        </a>
      )}
    </header>
  );
}
