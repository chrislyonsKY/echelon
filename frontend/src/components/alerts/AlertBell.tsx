/**
 * AlertBell — notification bell with unread count badge.
 * Polls for unread alerts every 60 seconds when user is authenticated.
 */
import { useEffect } from "react";
import { useEchelonStore } from "@/store/echelonStore";
import { alertsApi } from "@/services/api";

export default function AlertBell() {
  const { user, unreadAlertCount, alertPanelOpen } = useEchelonStore();

  useEffect(() => {
    if (!user) return;

    const poll = async () => {
      try {
        const alerts = await alertsApi.getUnread();
        useEchelonStore.setState({ unreadAlertCount: alerts.length });
      } catch {
        // Silently fail — alert polling is non-critical
      }
    };

    poll();
    const interval = setInterval(poll, 60_000);
    return () => clearInterval(interval);
  }, [user]);

  if (!user) return null;

  return (
    <button
      aria-label={`Alerts — ${unreadAlertCount} unread`}
      onClick={() => useEchelonStore.setState({ alertPanelOpen: !alertPanelOpen })}
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        width: 44,
        height: 44,
        borderRadius: "50%",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        color: "var(--color-text-primary)",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 18,
        zIndex: 20,
      }}
    >
      🔔
      {unreadAlertCount > 0 && (
        <span
          aria-label={`${unreadAlertCount} unread alerts`}
          style={{
            position: "absolute",
            top: -4,
            right: -4,
            background: "var(--color-danger)",
            color: "#fff",
            borderRadius: "50%",
            width: 18,
            height: 18,
            fontSize: 10,
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {unreadAlertCount > 9 ? "9+" : unreadAlertCount}
        </span>
      )}
    </button>
  );
}
