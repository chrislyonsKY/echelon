/**
 * Echelon Global State Store
 *
 * Central Zustand store for all application state. Map state, layer visibility,
 * copilot session, alerts, and user auth all live here.
 *
 * Convention: Components read from the store via selectors. They never maintain
 * local state for anything shared across the component tree.
 */
import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import type { MapViewState } from "@deck.gl/core";

// ── Types ─────────────────────────────────────────────────────────────────────

export type H3Resolution = 5 | 7 | 9;

export interface LayerVisibility {
  convergenceHeatmap: boolean;
  gdeltEvents: boolean;
  gfwVessels: boolean;
  sentinel2: boolean;
  osmInfrastructure: boolean;
  landscanPopulation: boolean;
}

export interface SignalWeights {
  gfw_ais_gap: number;
  gdelt_conflict: number;
  sentinel2_nbr_anomaly: number;
  newsdata_article: number;
  gfw_loitering: number;
  osm_change: number;
}

export interface CopilotMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: Array<{ toolName: string; status: "pending" | "complete" | "error" }>;
  mapAction?: MapAction;
  timestamp: Date;
}

export interface MapAction {
  type: "fly_to" | "highlight_cells" | "set_layers";
  center?: [number, number];
  zoom?: number;
  highlightCells?: string[];
  activeLayers?: Partial<LayerVisibility>;
}

export interface SelectedCell {
  h3Index: string;
  resolution: H3Resolution;
  zScore: number;
  center: [number, number];
}

export interface User {
  id: string;
  githubUsername: string;
  email?: string;
  byokStorageMode: "browser" | "server";
}

// ── Default values ─────────────────────────────────────────────────────────────

const DEFAULT_LAYER_VISIBILITY: LayerVisibility = {
  convergenceHeatmap: true,
  gdeltEvents: false,
  gfwVessels: false,
  sentinel2: false,
  osmInfrastructure: false,
  landscanPopulation: false,
};

const DEFAULT_SIGNAL_WEIGHTS: SignalWeights = {
  gfw_ais_gap: 0.35,
  gdelt_conflict: 0.30,
  sentinel2_nbr_anomaly: 0.25,
  newsdata_article: 0.12,
  gfw_loitering: 0.10,
  osm_change: 0.08,
};

// ── Store ──────────────────────────────────────────────────────────────────────

interface EchelonState {
  // Map state
  viewState: MapViewState;
  activeResolution: H3Resolution;
  selectedCell: SelectedCell | null;
  layerVisibility: LayerVisibility;
  signalWeights: SignalWeights;
  dateRange: { from: Date; to: Date };

  // Copilot state
  copilotMessages: CopilotMessage[];
  copilotOpen: boolean;
  byokKey: string | null; // Browser-side key — never sent to server unless opt-in

  // Alerts state
  unreadAlertCount: number;
  alertPanelOpen: boolean;

  // Sidebar state
  sidebarOpen: boolean;
  sidebarTab: "activity" | "events" | "layers";

  // Basemap
  basemapStyle: string;

  // UI panels
  showMethodology: boolean;
  selectedEventId: string | null;
  theaterMode: boolean;
  countryOverviewOpen: boolean;
  countryOverviewCountry: string | null;

  // Auth state
  user: User | null;
  authLoading: boolean;

  // Actions
  setViewState: (viewState: MapViewState) => void;
  setSelectedCell: (cell: SelectedCell | null) => void;
  toggleLayer: (layer: keyof LayerVisibility) => void;
  setSignalWeight: (signal: keyof SignalWeights, value: number) => void;
  setBasemapStyle: (style: string) => void;
  setDateRange: (from: Date, to: Date) => void;
  applyMapAction: (action: MapAction) => void;
  addCopilotMessage: (message: CopilotMessage) => void;
  setCopilotOpen: (open: boolean) => void;
  setByokKey: (key: string | null) => void;
  setSidebarTab: (tab: "activity" | "events" | "layers") => void;
  setSidebarOpen: (open: boolean) => void;
  setUser: (user: User | null) => void;
  setShowMethodology: (show: boolean) => void;
  setSelectedEventId: (id: string | null) => void;
  setTheaterMode: (enabled: boolean) => void;
  openCountryOverview: (country: string) => void;
  closeCountryOverview: () => void;
}

export const useEchelonStore = create<EchelonState>()(
  subscribeWithSelector((set, _get) => ({
    // ── Initial state ───────────────────────────────────────────────────────
    viewState: {
      longitude: 0,
      latitude: 20,
      zoom: 2,
      pitch: 0,
      bearing: 0,
    },
    activeResolution: 5,
    selectedCell: null,
    layerVisibility: DEFAULT_LAYER_VISIBILITY,
    signalWeights: DEFAULT_SIGNAL_WEIGHTS,
    dateRange: {
      from: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
      to: new Date(),
    },
    copilotMessages: [],
    copilotOpen: false,
    byokKey: null,
    unreadAlertCount: 0,
    alertPanelOpen: false,
    sidebarOpen: false,
    sidebarTab: "activity",
    basemapStyle: "dark",
    user: null,
    authLoading: true,
    showMethodology: false,
    selectedEventId: null,
    theaterMode: false,
    countryOverviewOpen: false,
    countryOverviewCountry: null,

    // ── Actions ─────────────────────────────────────────────────────────────
    setBasemapStyle: (style) => set({ basemapStyle: style }),

    setViewState: (viewState) => {
      // Derive active H3 resolution from zoom level
      const zoom = viewState.zoom ?? 2;
      const activeResolution: H3Resolution = zoom < 5 ? 5 : zoom < 10 ? 7 : 9;
      set({ viewState, activeResolution });
    },

    setSelectedCell: (cell) => set({ selectedCell: cell, sidebarOpen: cell !== null }),

    toggleLayer: (layer) =>
      set((state) => ({
        layerVisibility: {
          ...state.layerVisibility,
          [layer]: !state.layerVisibility[layer],
        },
      })),

    setSignalWeight: (signal, value) =>
      set((state) => ({
        signalWeights: { ...state.signalWeights, [signal]: value },
      })),

    setDateRange: (from, to) => set({ dateRange: { from, to } }),

    applyMapAction: (action) => {
      set((state) => {
        const updates: Partial<EchelonState> = {};

        if (action.type === "fly_to" && action.center) {
          updates.viewState = {
            ...state.viewState,
            longitude: action.center[0],
            latitude: action.center[1],
            zoom: action.zoom ?? state.viewState.zoom ?? 8,
          };
        }

        if (action.type === "set_layers" && action.activeLayers) {
          updates.layerVisibility = {
            ...state.layerVisibility,
            ...action.activeLayers,
          };
        }

        if (action.type === "highlight_cells" && action.highlightCells?.length) {
          // Select the first highlighted cell for investigation
          const h3Index = action.highlightCells[0];
          updates.selectedCell = {
            h3Index,
            resolution: 7,
            zScore: 0,
            center: action.center ?? [state.viewState.longitude ?? 0, state.viewState.latitude ?? 20],
          };
          updates.sidebarOpen = true;
        }

        return updates;
      });
    },

    addCopilotMessage: (message) =>
      set((state) => ({ copilotMessages: [...state.copilotMessages, message] })),

    setCopilotOpen: (open) => set({ copilotOpen: open }),

    setByokKey: (key) => set({ byokKey: key }),

    setSidebarTab: (tab) => set({ sidebarTab: tab }),
    setSidebarOpen: (open) => set({ sidebarOpen: open }),

    setUser: (user) => set({ user, authLoading: false }),

    setShowMethodology: (show) => set({ showMethodology: show }),

    setSelectedEventId: (id) => set({ selectedEventId: id }),

    setTheaterMode: (enabled) =>
      set({
        theaterMode: enabled,
        countryOverviewOpen: enabled ? false : _get().countryOverviewOpen,
        sidebarOpen: enabled ? false : _get().sidebarOpen,
        alertPanelOpen: enabled ? false : _get().alertPanelOpen,
        copilotOpen: enabled ? false : _get().copilotOpen,
      }),

    openCountryOverview: (country) => set({ countryOverviewOpen: true, countryOverviewCountry: country }),
    closeCountryOverview: () => set({ countryOverviewOpen: false }),
  }))
);
