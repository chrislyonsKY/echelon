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
  sidebarTab: "layers" | "timeline" | "signals";

  // Auth state
  user: User | null;
  authLoading: boolean;

  // Actions
  setViewState: (viewState: MapViewState) => void;
  setSelectedCell: (cell: SelectedCell | null) => void;
  toggleLayer: (layer: keyof LayerVisibility) => void;
  setSignalWeight: (signal: keyof SignalWeights, value: number) => void;
  setDateRange: (from: Date, to: Date) => void;
  applyMapAction: (action: MapAction) => void;
  addCopilotMessage: (message: CopilotMessage) => void;
  setCopilotOpen: (open: boolean) => void;
  setByokKey: (key: string | null) => void;
  setSidebarTab: (tab: "layers" | "timeline" | "signals") => void;
  setUser: (user: User | null) => void;
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
    sidebarTab: "layers",
    user: null,
    authLoading: true,

    // ── Actions ─────────────────────────────────────────────────────────────
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

    applyMapAction: (_action) => {
      // TODO: implement — fly map to coordinates, highlight cells, toggle layers
    },

    addCopilotMessage: (message) =>
      set((state) => ({ copilotMessages: [...state.copilotMessages, message] })),

    setCopilotOpen: (open) => set({ copilotOpen: open }),

    setByokKey: (key) => set({ byokKey: key }),

    setSidebarTab: (tab) => set({ sidebarTab: tab }),

    setUser: (user) => set({ user, authLoading: false }),
  }))
);
