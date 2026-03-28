/**
 * SearchBar — location search with fly-to.
 * Uses Nominatim (free, open geocoder) to resolve place names to coordinates.
 */
import { useState, useCallback } from "react";
import { useEchelonStore } from "@/store/echelonStore";

const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";

interface SearchResult {
  display_name: string;
  lat: string;
  lon: string;
  type: string;
}

export default function SearchBar() {
  const { setViewState } = useEchelonStore();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await fetch(
        `${NOMINATIM_URL}?q=${encodeURIComponent(query)}&format=json&limit=5`,
        { headers: { "User-Agent": "Echelon GEOINT Dashboard" } }
      );
      const data: SearchResult[] = await res.json();
      setResults(data);
      setOpen(data.length > 0);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, [query]);

  const flyTo = useCallback(
    (lat: number, lon: number) => {
      setViewState({
        longitude: lon,
        latitude: lat,
        zoom: 8,
        pitch: 0,
        bearing: 0,
      });
      setOpen(false);
      setQuery("");
      setResults([]);
    },
    [setViewState]
  );

  return (
    <div style={{ position: "relative" }}>
      <div style={{ display: "flex", gap: 0 }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Search location..."
          aria-label="Search for a location"
          style={{
            width: 180,
            padding: "5px 10px",
            borderRadius: "4px 0 0 4px",
            border: "1px solid var(--color-border)",
            borderRight: "none",
            background: "var(--color-surface-raised)",
            color: "var(--color-text-primary)",
            fontSize: 11,
            outline: "none",
          }}
        />
        <button
          onClick={handleSearch}
          disabled={searching}
          style={{
            padding: "5px 10px",
            borderRadius: "0 4px 4px 0",
            border: "1px solid var(--color-border)",
            background: "var(--color-surface-raised)",
            color: "var(--color-text-secondary)",
            cursor: "pointer",
            fontSize: 11,
          }}
        >
          {searching ? "..." : "Go"}
        </button>
      </div>

      {/* Results dropdown */}
      {open && results.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            marginTop: 4,
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            overflow: "hidden",
            zIndex: 100,
            boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
            minWidth: 280,
          }}
        >
          {results.map((r, i) => (
            <button
              key={i}
              onClick={() => flyTo(parseFloat(r.lat), parseFloat(r.lon))}
              style={{
                display: "block",
                width: "100%",
                padding: "8px 12px",
                background: "none",
                border: "none",
                borderBottom: i < results.length - 1 ? "1px solid var(--color-border)" : "none",
                color: "var(--color-text-primary)",
                fontSize: 11,
                textAlign: "left",
                cursor: "pointer",
                lineHeight: 1.4,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-surface-hover)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
            >
              {r.display_name.length > 60 ? r.display_name.slice(0, 60) + "..." : r.display_name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
