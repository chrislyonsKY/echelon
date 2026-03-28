import { useEffect } from "react";
import EchelonMap from "@/components/map/EchelonMap";
import InvestigationSidebar from "@/components/sidebar/InvestigationSidebar";
import CopilotPanel from "@/components/copilot/CopilotPanel";
import EventFeed from "@/components/EventFeed";
import AlertBell from "@/components/alerts/AlertBell";
import TopBar from "@/components/TopBar";
import DisclaimerFooter from "@/components/DisclaimerFooter";
import MethodologyPage from "@/components/MethodologyPage";
import AlertsPanel from "@/components/alerts/AlertsPanel";
import SourceHealth from "@/components/SourceHealth";
import TrendTable from "@/components/TrendTable";
import EventDetail from "@/components/EventDetail";
import CountryOverview from "@/components/CountryOverview";
import TheaterOverlay from "@/components/TheaterOverlay";
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
  const { setUser, sidebarOpen, copilotOpen, theaterMode } = useEchelonStore();

  // Resolve auth state on mount
  useEffect(() => {
    apiClient
      .get<{ id: string; githubUsername: string; email?: string; byokStorageMode: "browser" | "server" } | null>("/auth/me")
      .then((user) => setUser(user))
      .catch(() => setUser(null));
  }, [setUser]);

  // Open event-detail permalink in EventsPanel on initial load.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const eventId = params.get("event");
    if (!eventId) return;
    useEchelonStore.setState({
      sidebarOpen: true,
      sidebarTab: "events",
      selectedEventId: eventId,
    });
  }, []);

  return (
    <div className="echelon-root">
      {!theaterMode && <TopBar />}
      <div className="echelon-canvas">
        <EchelonMap />
        {sidebarOpen && !theaterMode && <InvestigationSidebar />}
        {copilotOpen && !theaterMode && <CopilotPanel />}
        {theaterMode && <TheaterOverlay />}
      </div>
      {!theaterMode && (
        <>
          <EventFeed />
          <AlertBell />
          <AlertsPanel />
          <CountryOverview />
          <EventDetail />
          <SourceHealth />
          <TrendTable />
          <DisclaimerFooter />
          <MethodologyPage />
        </>
      )}
    </div>
  );
}
