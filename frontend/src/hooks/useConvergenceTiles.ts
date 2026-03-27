/**
 * useConvergenceTiles
 *
 * Fetches H3 convergence score tiles for the current resolution.
 * Refreshes every 15 minutes (matching the server-side recompute cadence).
 */
import { useState, useEffect, useCallback } from "react";
import { convergenceApi, type ConvergenceTile } from "@/services/api";
import type { H3Resolution } from "@/store/echelonStore";

const REFRESH_INTERVAL_MS = 15 * 60 * 1000; // 15 minutes

export function useConvergenceTiles(resolution: H3Resolution) {
  const [tiles, setTiles] = useState<ConvergenceTile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await convergenceApi.getTiles(resolution);
      setTiles(data);
      setLastFetched(new Date());
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch convergence tiles"));
    } finally {
      setIsLoading(false);
    }
  }, [resolution]);

  useEffect(() => {
    fetch();
    const interval = setInterval(fetch, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetch]);

  return { tiles, isLoading, error, lastFetched, refresh: fetch };
}

/**
 * useSignalLayer
 *
 * Fetches signal events for a specific source to render as a map layer.
 * Refreshes when the date range changes.
 */
import { useEchelonStore } from "@/store/echelonStore";
import { signalsApi, type SignalEvent } from "@/services/api";

export function useSignalLayer(source: string) {
  const { dateRange, viewState } = useEchelonStore();
  const [events, setEvents] = useState<SignalEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!viewState.longitude || !viewState.latitude) return;

    const zoom = viewState.zoom ?? 2;
    if (zoom < 4) return; // Don't fetch individual events at global zoom

    // Approximate viewport bbox from center + zoom
    const span = 360 / Math.pow(2, zoom);
    const bbox: [number, number, number, number] = [
      (viewState.longitude ?? 0) - span / 2,
      (viewState.latitude ?? 0) - span / 2,
      (viewState.longitude ?? 0) + span / 2,
      (viewState.latitude ?? 0) + span / 2,
    ];

    setIsLoading(true);
    signalsApi
      .getForBbox(
        bbox,
        source,
        dateRange.from.toISOString().split("T")[0],
        dateRange.to.toISOString().split("T")[0]
      )
      .then((data) => setEvents(data))
      .catch(() => setEvents([]))
      .finally(() => setIsLoading(false));
  }, [source, dateRange, viewState.longitude, viewState.latitude, viewState.zoom]);

  return { [`${source}Events`]: events, isLoading } as Record<string, SignalEvent[]> & { isLoading: boolean };
}

/**
 * useSignalEvents
 *
 * Fetches all signal events for a selected H3 cell (used by investigation sidebar).
 */
export function useSignalEvents(h3Index: string) {
  const { dateRange } = useEchelonStore();
  const [events, setEvents] = useState<SignalEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    signalsApi
      .getForCell(
        h3Index,
        dateRange.from.toISOString().split("T")[0],
        dateRange.to.toISOString().split("T")[0]
      )
      .then((data) => {
        setEvents(data.sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime()));
      })
      .catch((err) => setError(err))
      .finally(() => setIsLoading(false));
  }, [h3Index, dateRange]);

  return { events, isLoading, error };
}
