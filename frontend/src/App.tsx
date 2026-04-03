import { useEffect, lazy, Suspense } from "react";
import TopBar from "@/components/TopBar";
import DisclaimerFooter from "@/components/DisclaimerFooter";
import AlertBell from "@/components/alerts/AlertBell";
import { useEchelonStore } from "@/store/echelonStore";
import { apiClient } from "@/services/api";

// Lazy-load heavy components — EchelonMap pulls in MapLibre (~800KB) and Deck.gl
const EchelonMap = lazy(() => import("@/components/map/EchelonMap"));
const InvestigationSidebar = lazy(() => import("@/components/sidebar/InvestigationSidebar"));
const CopilotPanel = lazy(() => import("@/components/copilot/CopilotPanel"));
const EventFeed = lazy(() => import("@/components/EventFeed"));
const AlertsPanel = lazy(() => import("@/components/alerts/AlertsPanel"));
const MethodologyPage = lazy(() => import("@/components/MethodologyPage"));
const SourceHealth = lazy(() => import("@/components/SourceHealth"));
const TrendTable = lazy(() => import("@/components/TrendTable"));
const EventDetail = lazy(() => import("@/components/EventDetail"));
const CountryOverview = lazy(() => import("@/components/CountryOverview"));
const TheaterOverlay = lazy(() => import("@/components/TheaterOverlay"));

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

  // Restore state from permalink on initial load.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);

    // Event permalink
    const eventId = params.get("event");
    if (eventId) {
      useEchelonStore.setState({
        sidebarOpen: true,
        sidebarTab: "events",
        selectedEventId: eventId,
      });
    }

    // Map view permalink (from copilot share)
    const lng = params.get("lng");
    const lat = params.get("lat");
    const zoom = params.get("z");
    if (lng && lat) {
      const store = useEchelonStore.getState();
      store.setViewState({
        ...store.viewState,
        longitude: parseFloat(lng),
        latitude: parseFloat(lat),
        zoom: zoom ? parseFloat(zoom) : store.viewState.zoom ?? 2,
      });
    }
    const dateFrom = params.get("from");
    const dateTo = params.get("to");
    if (dateFrom && dateTo) {
      useEchelonStore.getState().setDateRange(new Date(dateFrom), new Date(dateTo));
    }
  }, []);

  return (
    <div className="echelon-root">
      {!theaterMode && <TopBar />}
      <Suspense fallback={
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--color-bg)", color: "var(--color-text-secondary)", fontSize: 13 }}>
          Loading Echelon...
        </div>
      }>
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
      </Suspense>
    </div>
  );
}
