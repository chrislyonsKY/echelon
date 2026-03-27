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
};

// ── Copilot API ───────────────────────────────────────────────────────────────

export const copilotApi = {
  chat: (request: CopilotRequest, byokKey: string) =>
    apiClient.post<CopilotResponse>("/copilot/chat", request, { byokKey }),
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

// ── Auth API ──────────────────────────────────────────────────────────────────

export const authApi = {
  getMe: () =>
    apiClient
      .get<{ id: string; githubUsername: string; email?: string; byokStorageMode: "browser" | "server" } | null>("/auth/me")
      .catch(() => null),
  logout: () => apiClient.post<void>("/auth/logout", {}),
};
