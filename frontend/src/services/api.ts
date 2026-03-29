/**
 * Echelon API Client
 *
 * Typed fetch wrapper for all backend API calls.
 * Components NEVER call fetch() directly — use this module.
 *
 * All requests include credentials (HttpOnly session cookie).
 * BYOK key is passed as X-Anthropic-Key header only on copilot requests.
 */

const BASE_URL = "/api";

class APIError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message: string
  ) {
    super(message);
    this.name = "APIError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { byokKey?: string } = {}
): Promise<T> {
  const { byokKey, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers as Record<string, string>),
  };

  // SECURITY: BYOK key — pass in header only for copilot requests, never stored
  if (byokKey) {
    headers["X-Anthropic-Key"] = byokKey;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...fetchOptions,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new APIError(response.status, response.statusText, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string, options?: RequestInit) =>
    request<T>(path, { ...options, method: "GET" }),

  post: <T>(path: string, body: unknown, options?: RequestInit & { byokKey?: string }) =>
    request<T>(path, { ...options, method: "POST", body: JSON.stringify(body) }),

  delete: <T>(path: string, options?: RequestInit) =>
    request<T>(path, { ...options, method: "DELETE" }),

  patch: <T>(path: string, body: unknown, options?: RequestInit) =>
    request<T>(path, { ...options, method: "PATCH", body: JSON.stringify(body) }),
};

// ── Typed API surface ─────────────────────────────────────────────────────────

export interface ConvergenceTile {
  h3Index: string;
  resolution: 5 | 7 | 9;
  zScore: number;
  rawScore: number;
  signalBreakdown: Record<string, number>;
  lowConfidence: boolean;
  computedAt: string;
}

export interface SignalEvent {
  id: string;
  source: string;
  signalType: string;
  location: { lat: number; lng: number };
  occurredAt: string;
  weight: number;
  rawPayload: Record<string, unknown>;
  sourceId?: string;
  provenanceFamily?: string;
  confirmationPolicy?: string;
  language?: string;
  textDirection?: string;
  translationStatus?: string;
  titleOriginal?: string | null;
  descriptionOriginal?: string | null;
  titleTranslated?: string | null;
  descriptionTranslated?: string | null;
  displayTitle?: string | null;
  displayDescription?: string | null;
}

export interface TrackFeatureCollection extends GeoJSON.FeatureCollection<GeoJSON.LineString> {}

export interface ImageryScene {
  id: string;
  provider: "capella" | "maxar";
  title: string;
  capturedAt: string | null;
  bbox: [number, number, number, number] | null;
  geometry: GeoJSON.Geometry | null;
  thumbnailUrl?: string | null;
  previewUrl?: string | null;
  assetUrl?: string | null;
  itemUrl: string;
  license: string;
  metadata: Record<string, unknown>;
}

export interface ImageryAnalysis {
  provider: "capella" | "maxar";
  sceneId: string;
  itemUrl: string;
  processor: string;
  analysisType: string;
  sarkitAvailable: boolean;
  metadata: Record<string, unknown>;
  summary: {
    window: {
      width: number;
      height: number;
      bandCount: number;
    };
    bands: Array<{
      pixelCount: number;
      min: number | null;
      max: number | null;
      mean: number | null;
      std: number | null;
      p50: number | null;
      p95: number | null;
    }>;
    assetHref: string;
    sar?: {
      strongScatterFraction: number;
      edgeFraction: number;
    };
  };
}

export interface AOI {
  id: string;
  name: string;
  geometry: GeoJSON.Polygon;
  alertThreshold: number;
  alertEmail: boolean;
  createdAt: string;
}

export interface AlertRecord {
  id: string;
  aoiId: string;
  aoiName: string;
  triggerType: string;
  triggerDetail: Record<string, unknown>;
  h3Index: string;
  zScore?: number;
  firedAt: string;
  readAt?: string;
}

export interface CopilotRequest {
  messages: Array<{ role: "user" | "assistant"; content: string }>;
  mapContext: {
    viewport: { center: [number, number]; zoom: number };
    dateRange: { from: string; to: string };
    selectedCell?: string;
  };
  provider?: "anthropic" | "openai" | "google" | "ollama";
}

export interface CopilotResponse {
  content: string;
  toolCallsSummary?: Array<{ toolName: string; resultSummary: string }>;
  mapAction?: {
    type: string;
    center?: [number, number];
    zoom?: number;
    highlightCells?: string[];
    activeLayers?: Record<string, boolean>;
  };
}

// ── Convergence API ───────────────────────────────────────────────────────────

export const convergenceApi = {
  getTiles: (resolution: 5 | 7 | 9, bbox?: [number, number, number, number]) =>
    apiClient.get<ConvergenceTile[]>(
      `/convergence/tiles?resolution=${resolution}${bbox ? `&bbox=${bbox.join(",")}` : ""}`
    ),

  getCell: (h3Index: string) =>
    apiClient.get<ConvergenceTile>(`/convergence/cell/${h3Index}`),
};

// ── Signals API ───────────────────────────────────────────────────────────────

export const signalsApi = {
  getForCell: (h3Index: string, dateFrom: string, dateTo: string) =>
    apiClient.get<SignalEvent[]>(
      `/signals?h3_index=${h3Index}&date_from=${dateFrom}&date_to=${dateTo}`
    ),

  getForBbox: (
    bbox: [number, number, number, number],
    source: string,
    dateFrom: string,
    dateTo: string
  ) =>
    apiClient.get<SignalEvent[]>(
      `/signals?bbox=${bbox.join(",")}&source=${source}&date_from=${dateFrom}&date_to=${dateTo}`
    ),

  getTracks: (
    bbox: [number, number, number, number],
    source: "aisstream" | "opensky",
    hours = 24
  ) =>
    apiClient.get<TrackFeatureCollection>(
      `/signals/tracks?bbox=${bbox.join(",")}&source=${source}&hours=${hours}`
    ),
};

// ── Imagery API ───────────────────────────────────────────────────────────────

export const imageryApi = {
  search: (params: {
    provider: "capella" | "maxar";
    bbox: [number, number, number, number];
    dateFrom: string;
    dateTo: string;
    limit?: number;
  }) =>
    apiClient.get<ImageryScene[]>(
      `/imagery/search?provider=${params.provider}&bbox=${params.bbox.join(",")}&date_from=${params.dateFrom}&date_to=${params.dateTo}&limit=${params.limit ?? 12}`
    ),

  analyze: (body: {
    itemUrl: string;
    bbox?: [number, number, number, number];
  }) =>
    apiClient.post<ImageryAnalysis>("/imagery/analyze", body),
};

// ── Copilot API ───────────────────────────────────────────────────────────────

export const copilotApi = {
  chat: (request: CopilotRequest, byokKey: string) =>
    apiClient.post<CopilotResponse>("/copilot/chat", request, {
      headers: { "X-LLM-Key": byokKey, "X-Anthropic-Key": byokKey } as Record<string, string>,
    }),
};

// ── Alerts API ────────────────────────────────────────────────────────────────

export const alertsApi = {
  getUnread: () => apiClient.get<AlertRecord[]>("/alerts/unread"),
  markRead: (alertId: string) => apiClient.patch<void>(`/alerts/${alertId}/read`, {}),
  getAois: () => apiClient.get<AOI[]>("/alerts/aois"),
  createAoi: (aoi: Omit<AOI, "id" | "createdAt">) =>
    apiClient.post<AOI>("/alerts/aois", aoi),
  deleteAoi: (aoiId: string) => apiClient.delete<void>(`/alerts/aois/${aoiId}`),
};

// ── Provenance API ───────────────────────────────────────────────────────

export interface ProvenanceEntry {
  signalId: string;
  source: string;
  signalType: string;
  occurredAt: string;
  ingestedAt: string;
  weight: number;
  provenanceFamily: string;
  confirmationPolicy: string;
  scoreContribution: number;
}

export const provenanceApi = {
  getProvenance: (eventId: string) =>
    apiClient.get<ProvenanceEntry[]>(`/investigations/provenance/${eventId}`),
};

// ── Events API ───────────────────────────────────────────────────────────

export interface EchelonEvent {
  id: string;
  title: string;
  eventType: string;
  location: { lat: number; lng: number };
  h3Index: string;
  firstSeen: string;
  lastSeen: string;
  sourceFamilies: string[];
  corroborationCount: number;
  confirmationStatus: string;
  signalCount: number;
  summary?: string;
}

export interface EventDetail extends EchelonEvent {
  createdAt: string;
  updatedAt: string;
  signals: Array<{
    id: string;
    source: string;
    signalType: string;
    location: { lat: number; lng: number };
    occurredAt: string;
    weight: number;
    provenanceFamily?: string;
    confirmationPolicy?: string;
    sourceId?: string;
  }>;
  evidence: Array<{
    id: string;
    signalId: string;
    type: string;
    url: string;
    platform?: string;
    thumbnailUrl?: string;
    title?: string;
    provenanceFamily?: string;
    graphicFlag: boolean;
    reviewStatus: string;
  }>;
}

export type DebunkStatus = "not_assessed" | "false" | "duplicate" | "spoofed" | "mislocated" | "satire" | "propaganda" | "old_imagery" | "stale_repost" | "debunked";

export const eventsApi = {
  list: (params?: { bbox?: string; eventType?: string; confirmation?: string; days?: number }) => {
    const qs = new URLSearchParams();
    if (params?.bbox) qs.set("bbox", params.bbox);
    if (params?.eventType) qs.set("event_type", params.eventType);
    if (params?.confirmation) qs.set("confirmation", params.confirmation);
    if (params?.days) qs.set("days", String(params.days));
    const query = qs.toString();
    return apiClient.get<EchelonEvent[]>(`/events/${query ? `?${query}` : ""}`);
  },

  getDetail: (eventId: string) =>
    apiClient.get<EventDetail>(`/events/${eventId}`),

  getForCell: (h3Index: string, days?: number) =>
    apiClient.get<EchelonEvent[]>(
      `/events/for-cell/${h3Index}${days ? `?days=${days}` : ""}`
    ),

  patchDebunkStatus: (eventId: string, debunkStatus: DebunkStatus, debunkReason: string) =>
    apiClient.patch<void>(`/events/${eventId}`, { debunk_status: debunkStatus, debunk_reason: debunkReason }),
};

// ── Investigations API ───────────────────────────────────────────────────────

export interface Investigation {
  id: string;
  title: string;
  description?: string;
  notes?: string;
  tags: string[];
  viewState: {
    longitude: number;
    latitude: number;
    zoom: number;
    pitch?: number;
    bearing?: number;
  };
  dateRange: { from: string; to: string };
  layerVisibility: Record<string, boolean>;
  selectedCellH3?: string;
  createdAt: string;
  updatedAt: string;
}

export interface InvestigationCreate {
  title: string;
  description?: string;
  notes?: string;
  tags: string[];
  viewState: Investigation["viewState"];
  dateRange: Investigation["dateRange"];
  layerVisibility: Record<string, boolean>;
  selectedCellH3?: string;
}

export interface InvestigationUpdate {
  title?: string;
  description?: string;
  notes?: string;
  tags?: string[];
}

export interface ScoringExplanation {
  h3Index: string;
  zScore: number;
  rawScore: number;
  signalBreakdown: Record<string, number>;
  lowConfidence: boolean;
  confidenceStatistical: number | null;
  confidenceDiversity: number | null;
  confidenceSensor: number | null;
  confidenceMedia: number | null;
  confidenceReviewed: number | null;
  recentSignals: Array<{
    source: string;
    signalType: string;
    occurredAt: string;
    weight: number;
  }>;
}

export type NoteType = "observation" | "assessment" | "review" | "correction" | "question";
export type ConfidenceLevel = "high" | "medium" | "low" | "uncertain";

export interface AnalystNoteEntry {
  id: string;
  userId: string;
  username?: string;
  noteType: string;
  content: string;
  confidence: string | null;
  createdAt: string;
}

export const investigationsApi = {
  list: () =>
    apiClient.get<Investigation[]>("/investigations/"),

  get: (id: string) =>
    apiClient.get<Investigation>(`/investigations/${id}`),

  create: (body: InvestigationCreate) =>
    apiClient.post<Investigation>("/investigations/", body),

  update: (id: string, body: InvestigationUpdate) =>
    apiClient.patch<Investigation>(`/investigations/${id}`, body),

  delete: (id: string) =>
    apiClient.delete<void>(`/investigations/${id}`),

  getScoring: (h3Index: string) =>
    apiClient.get<ScoringExplanation>(`/investigations/scoring/${h3Index}`),

  getNotes: (eventId: string) =>
    apiClient.get<AnalystNoteEntry[]>(`/investigations/notes/${eventId}`),

  addNote: (body: { eventId?: string; h3Index?: string; noteType: string; content: string; confidence?: string }) =>
    apiClient.post<AnalystNoteEntry>("/investigations/notes", body),

  submitFeedback: (body: { eventId?: string; h3Index?: string; signalIds?: string[]; reason: string; detail?: string }) =>
    apiClient.post<{ id: string }>("/investigations/feedback", body),
};

// Type aliases for component compatibility
export type AnalystNote = AnalystNoteEntry;

export const notesApi = {
  getForEvent: (eventId: string) =>
    investigationsApi.getNotes(eventId),

  create: (body: { event_id?: string; h3_index?: string; note_type: string; content: string; confidence?: string }) =>
    apiClient.post<AnalystNote>("/investigations/notes", body),
};

// ── Auth API ──────────────────────────────────────────────────────────────────

export const authApi = {
  getMe: () =>
    apiClient
      .get<{ id: string; githubUsername: string; email?: string; byokStorageMode: "browser" | "server" } | null>("/auth/me")
      .catch(() => null),
  logout: () => apiClient.post<void>("/auth/logout", {}),
};
