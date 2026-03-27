# Echelon — Field Schema Reference

Reference for all data models, API request/response shapes, and copilot tool schemas.

---

## Signal Type Registry

| signal_type | source | Weight | Description |
|-------------|--------|--------|-------------|
| `gfw_ais_gap` | gfw | 0.35 | AIS transmission gap (dark vessel) |
| `acled_battle` | acled | 0.30 | Armed clash between organized groups |
| `acled_explosion` | acled | 0.30 | Remote violence, IED, airstrike |
| `sentinel2_nbr_anomaly` | sentinel2 | 0.25 | Delta NBR > 0.1 |
| `acled_other` | acled | 0.15 | Protest, riot, strategic development |
| `gdelt_conflict` | gdelt | 0.12 | CAMEO 19x/20x coded event |
| `newsdata_article` | newsdata | 0.12 | Conflict-keyword article |
| `gfw_loitering` | gfw | 0.10 | Vessel loitering anomaly |
| `osm_change` | osm | 0.08 | Military/infrastructure OSM change |

---

## ConvergenceTile (API response)

```typescript
interface ConvergenceTile {
  h3Index: string;
  resolution: 5 | 7 | 9;
  zScore: number;
  rawScore: number;
  signalBreakdown: Record<string, number>;
  lowConfidence: boolean;
  computedAt: string;  // ISO 8601
}
```

## SignalEvent (API response)

```typescript
interface SignalEvent {
  id: string;
  source: string;
  signalType: string;
  location: { lat: number; lng: number };
  occurredAt: string;
  weight: number;
  rawPayload: Record<string, unknown>;
  sourceId?: string;
}
```

## CopilotRequest / CopilotResponse

```typescript
interface CopilotRequest {
  messages: Array<{ role: "user" | "assistant"; content: string }>;
  mapContext: {
    viewport: { center: [number, number]; zoom: number };
    dateRange: { from: string; to: string };
    selectedCell?: string;
  };
}

interface CopilotResponse {
  content: string;
  toolCallsSummary?: Array<{ toolName: string; resultSummary: string }>;
  mapAction?: {
    type: "fly_to" | "highlight_cells" | "set_layers";
    center?: [number, number];
    zoom?: number;
    highlightCells?: string[];
    activeLayers?: Record<string, boolean>;
  };
}
```

---

## H3 Index Computation (Python)

```python
import h3

def get_h3_indexes(lat: float, lon: float) -> tuple[str, str, str]:
    return (
        h3.geo_to_h3(lat, lon, 5),
        h3.geo_to_h3(lat, lon, 7),
        h3.geo_to_h3(lat, lon, 9),
    )
```

## Dedup Hash

```python
import hashlib

def build_dedup_hash(source: str, source_id: str, occurred_at: str) -> str:
    key = f"{source}:{source_id}:{occurred_at}"
    return hashlib.sha256(key.encode()).hexdigest()
```

---

## ACLED Raw Payload (key fields)

```json
{ "data_id": "12345678", "event_date": "2025-03-15", "event_type": "Battles",
  "country": "Ukraine", "latitude": "48.1362", "longitude": "37.7492",
  "fatalities": "3", "actor1": "Military Forces of Russia", "notes": "..." }
```

## GFW AIS Gap Event (key fields)

```json
{ "id": "abc123", "type": "gap",
  "vessel": { "id": "v1", "name": "VESSEL", "flag": "RU" },
  "start": { "timestamp": "2025-03-15T08:00:00Z", "lat": 44.5, "lon": 33.2 },
  "end":   { "timestamp": "2025-03-15T14:30:00Z", "lat": 44.8, "lon": 33.5 },
  "durationHours": 6.5, "distanceKm": 42.1 }
```

## GDELT Export Columns (key)

```
GlobalEventID | SQLDATE | EventCode | Actor1Geo_Lat | Actor1Geo_Long | ActionGeo_Lat | ActionGeo_Long | SOURCEURL
```

CAMEO codes of interest: 190-196 (Fight), 200-204 (Use conventional military force)
