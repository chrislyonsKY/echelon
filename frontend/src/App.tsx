import { useEffect } from "react";
import EchelonMap from "@/components/map/EchelonMap";
import InvestigationSidebar from "@/components/sidebar/InvestigationSidebar";
import CopilotPanel from "@/components/copilot/CopilotPanel";
import EventFeed from "@/components/EventFeed";
import AlertBell from "@/components/alerts/AlertBell";
import TopBar from "@/components/TopBar";
import DisclaimerFooter from "@/components/DisclaimerFooter";
import AlertsPanel from "@/components/alerts/AlertsPanel";
import SourceHealth from "@/components/SourceHealth";
import TrendTable from "@/components/TrendTable";
import EventDetail from "@/components/EventDetail";
import { useEchelonStore } from "@/store/echelonStore";
import { apiClient } from "@/services/api";

/**
 * Root application component.
 *
 * Layout:
 *   ┌─────────────────────────────────────────┐
 *   │  TopBar (branding, date range, auth)     │
 *   ├──────────────────────┬──────────────────┤
 *   │                      │  Investigation   │
 *   │    EchelonMap        │  Sidebar         │
 *   │    (full canvas)     │  (tabs)          │
 *   │                      │                  │
 *   └──────────────────────┴──────────────────┘
 *   Copilot panel slides in from right (overlay)
 */
export default function App() {
  const { setUser, sidebarOpen, copilotOpen } = useEchelonStore();

  // Resolve auth state on mount
  useEffect(() => {
    apiClient
      .get<{ id: string; githubUsername: string; email?: string; byokStorageMode: "browser" | "server" } | null>("/auth/me")
      .then((user) => setUser(user))
      .catch(() => setUser(null));
  }, [setUser]);

  return (
    <div className="echelon-root">
      <TopBar />
      <div className="echelon-canvas">
        <EchelonMap />
        {sidebarOpen && <InvestigationSidebar />}
        {copilotOpen && <CopilotPanel />}
      </div>
      <EventFeed />
      <AlertBell />
      <AlertsPanel />
      <EventDetail />
      <SourceHealth />
      <TrendTable />
      <DisclaimerFooter />
    </div>
  );
}
