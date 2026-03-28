"""
Maritime reference data service.

Loads maritime geospatial reference datasets on startup for:
  1. Marine Regions EEZ boundaries (Exclusive Economic Zones)
  2. Major world ports (NGA World Port Index with hardcoded fallback)

Data is loaded once into memory and used to enrich signals,
provide maritime context for the copilot, and label vessel
activity relative to ports and EEZ boundaries.
"""
import logging
import math
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MARINE_REGIONS_URL = (
    "https://www.marineregions.org/rest/getGazetteerRecordsByType.json/EEZ/"
)
NGA_PORTS_URL = (
    "https://msi.nga.mil/api/publications/download"
    "?type=view&key=16920959/SFH00000/UpdatePub150.csv"
)

# ---------------------------------------------------------------------------
# Singleton state — loaded once at startup
# ---------------------------------------------------------------------------
_eez_zones: list[dict[str, Any]] = []
_ports: list[dict[str, Any]] = []
_loaded: bool = False

# ---------------------------------------------------------------------------
# Hardcoded major world ports (fallback when NGA is unreachable)
# ---------------------------------------------------------------------------
_FALLBACK_PORTS: list[dict[str, Any]] = [
    # Red Sea / Horn of Africa
    {"name": "Aden", "country": "YE", "lat": 12.80, "lon": 45.03, "type": "both"},
    {"name": "Djibouti", "country": "DJ", "lat": 11.59, "lon": 43.15, "type": "both"},
    {"name": "Bab-el-Mandeb", "country": "YE", "lat": 12.58, "lon": 43.33, "type": "military"},
    {"name": "Jeddah", "country": "SA", "lat": 21.49, "lon": 39.17, "type": "commercial"},
    {"name": "Port Sudan", "country": "SD", "lat": 19.62, "lon": 37.22, "type": "commercial"},
    {"name": "Massawa", "country": "ER", "lat": 15.61, "lon": 39.45, "type": "commercial"},
    # Persian Gulf / Arabian Sea
    {"name": "Hormuz", "country": "IR", "lat": 27.06, "lon": 56.46, "type": "military"},
    {"name": "Bandar Abbas", "country": "IR", "lat": 27.18, "lon": 56.28, "type": "both"},
    {"name": "Dubai (Jebel Ali)", "country": "AE", "lat": 25.00, "lon": 55.06, "type": "commercial"},
    {"name": "Muscat", "country": "OM", "lat": 23.63, "lon": 58.57, "type": "commercial"},
    {"name": "Karachi", "country": "PK", "lat": 24.85, "lon": 66.98, "type": "both"},
    {"name": "Mumbai (Nhava Sheva)", "country": "IN", "lat": 18.95, "lon": 72.95, "type": "commercial"},
    # Suez / Eastern Mediterranean
    {"name": "Suez", "country": "EG", "lat": 29.97, "lon": 32.55, "type": "commercial"},
    {"name": "Port Said", "country": "EG", "lat": 31.26, "lon": 32.30, "type": "commercial"},
    {"name": "Haifa", "country": "IL", "lat": 32.82, "lon": 35.00, "type": "both"},
    {"name": "Tartus", "country": "SY", "lat": 34.89, "lon": 35.87, "type": "both"},
    {"name": "Latakia", "country": "SY", "lat": 35.52, "lon": 35.78, "type": "commercial"},
    {"name": "Piraeus", "country": "GR", "lat": 37.94, "lon": 23.64, "type": "commercial"},
    {"name": "Istanbul", "country": "TR", "lat": 41.01, "lon": 28.98, "type": "commercial"},
    {"name": "Izmir", "country": "TR", "lat": 38.44, "lon": 27.14, "type": "commercial"},
    {"name": "Mersin", "country": "TR", "lat": 36.80, "lon": 34.63, "type": "commercial"},
    # Black Sea
    {"name": "Sevastopol", "country": "UA", "lat": 44.62, "lon": 33.53, "type": "military"},
    {"name": "Odessa", "country": "UA", "lat": 46.49, "lon": 30.74, "type": "commercial"},
    {"name": "Novorossiysk", "country": "RU", "lat": 44.72, "lon": 37.77, "type": "both"},
    {"name": "Constanta", "country": "RO", "lat": 44.17, "lon": 28.66, "type": "commercial"},
    # Northern Europe
    {"name": "Rotterdam", "country": "NL", "lat": 51.91, "lon": 4.49, "type": "commercial"},
    {"name": "Hamburg", "country": "DE", "lat": 53.55, "lon": 9.93, "type": "commercial"},
    {"name": "Antwerp", "country": "BE", "lat": 51.26, "lon": 4.40, "type": "commercial"},
    {"name": "Felixstowe", "country": "GB", "lat": 51.96, "lon": 1.33, "type": "commercial"},
    {"name": "Bremerhaven", "country": "DE", "lat": 53.55, "lon": 8.58, "type": "commercial"},
    {"name": "Gdansk", "country": "PL", "lat": 54.40, "lon": 18.67, "type": "commercial"},
    {"name": "Murmansk", "country": "RU", "lat": 68.97, "lon": 33.07, "type": "both"},
    {"name": "Kaliningrad", "country": "RU", "lat": 54.71, "lon": 20.45, "type": "both"},
    # Asia-Pacific
    {"name": "Singapore", "country": "SG", "lat": 1.26, "lon": 103.84, "type": "commercial"},
    {"name": "Busan", "country": "KR", "lat": 35.10, "lon": 129.04, "type": "commercial"},
    {"name": "Yokohama", "country": "JP", "lat": 35.44, "lon": 139.64, "type": "commercial"},
    {"name": "Yokosuka", "country": "JP", "lat": 35.28, "lon": 139.67, "type": "military"},
    {"name": "Shanghai", "country": "CN", "lat": 31.23, "lon": 121.47, "type": "commercial"},
    {"name": "Shenzhen (Yantian)", "country": "CN", "lat": 22.57, "lon": 114.28, "type": "commercial"},
    {"name": "Hong Kong", "country": "HK", "lat": 22.30, "lon": 114.17, "type": "commercial"},
    {"name": "Kaohsiung", "country": "TW", "lat": 22.61, "lon": 120.29, "type": "commercial"},
    {"name": "Cam Ranh Bay", "country": "VN", "lat": 11.95, "lon": 109.22, "type": "military"},
    {"name": "Subic Bay", "country": "PH", "lat": 14.79, "lon": 120.28, "type": "military"},
    {"name": "Colombo", "country": "LK", "lat": 6.94, "lon": 79.84, "type": "commercial"},
    # Pacific (US)
    {"name": "Pearl Harbor", "country": "US", "lat": 21.35, "lon": -157.97, "type": "military"},
    {"name": "Guam (Apra Harbor)", "country": "US", "lat": 13.44, "lon": 144.65, "type": "military"},
    {"name": "San Diego", "country": "US", "lat": 32.69, "lon": -117.15, "type": "both"},
    {"name": "Long Beach", "country": "US", "lat": 33.75, "lon": -118.19, "type": "commercial"},
    # Atlantic (US)
    {"name": "Norfolk", "country": "US", "lat": 36.85, "lon": -76.29, "type": "both"},
    {"name": "Jacksonville", "country": "US", "lat": 30.41, "lon": -81.63, "type": "both"},
    {"name": "Savannah", "country": "US", "lat": 32.08, "lon": -81.09, "type": "commercial"},
    {"name": "Houston", "country": "US", "lat": 29.76, "lon": -95.27, "type": "commercial"},
    {"name": "New Orleans", "country": "US", "lat": 29.93, "lon": -90.03, "type": "commercial"},
    # Indian Ocean
    {"name": "Diego Garcia", "country": "IO", "lat": -7.32, "lon": 72.42, "type": "military"},
    {"name": "Mombasa", "country": "KE", "lat": -4.04, "lon": 39.67, "type": "commercial"},
    {"name": "Dar es Salaam", "country": "TZ", "lat": -6.83, "lon": 39.29, "type": "commercial"},
    # West Africa
    {"name": "Lagos (Apapa)", "country": "NG", "lat": 6.45, "lon": 3.38, "type": "commercial"},
    {"name": "Abidjan", "country": "CI", "lat": 5.26, "lon": -3.97, "type": "commercial"},
    {"name": "Dakar", "country": "SN", "lat": 14.69, "lon": -17.45, "type": "both"},
    {"name": "Tema", "country": "GH", "lat": 5.63, "lon": -0.02, "type": "commercial"},
    {"name": "Douala", "country": "CM", "lat": 4.05, "lon": 9.70, "type": "commercial"},
]


# ---------------------------------------------------------------------------
# Startup loader
# ---------------------------------------------------------------------------
async def load_maritime_data() -> None:
    """Load maritime reference data at startup. Subsequent calls are no-ops."""
    global _eez_zones, _ports, _loaded
    if _loaded:
        return

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        # 1. Marine Regions EEZ boundaries
        try:
            r = await client.get(
                MARINE_REGIONS_URL,
                headers={"Accept": "application/json"},
            )
            r.raise_for_status()
            records = r.json()
            for rec in records:
                try:
                    _eez_zones.append({
                        "name": rec.get("preferredGazetteerName", ""),
                        "country": rec.get("country", ""),
                        "center_lat": float(rec["latitude"]),
                        "center_lon": float(rec["longitude"]),
                        "mrgid": rec.get("MRGID"),
                    })
                except (KeyError, ValueError, TypeError):
                    continue
            logger.info(
                "Maritime: loaded %d EEZ zones from Marine Regions",
                len(_eez_zones),
            )
        except Exception:
            logger.warning("Failed to load Marine Regions EEZ data", exc_info=True)

        # 2. World Ports — try NGA first, fall back to hardcoded
        try:
            r = await client.get(NGA_PORTS_URL)
            r.raise_for_status()
            import csv
            import io

            reader = csv.DictReader(io.StringIO(r.text))
            for row in reader:
                try:
                    lat_val = row.get("Latitude") or row.get("latitude") or ""
                    lon_val = row.get("Longitude") or row.get("longitude") or ""
                    name_val = (
                        row.get("Main Port Name")
                        or row.get("Port Name")
                        or row.get("port_name")
                        or ""
                    )
                    country_val = row.get("Country Code") or row.get("country") or ""
                    if not lat_val or not lon_val or not name_val:
                        continue
                    _ports.append({
                        "name": name_val.strip(),
                        "country": country_val.strip(),
                        "lat": float(lat_val),
                        "lon": float(lon_val),
                        "type": "commercial",
                    })
                except (ValueError, KeyError):
                    continue
            logger.info(
                "Maritime: loaded %d ports from NGA World Port Index",
                len(_ports),
            )
        except Exception:
            logger.warning(
                "NGA port data unavailable — using hardcoded major ports",
                exc_info=True,
            )
            _ports.extend(_FALLBACK_PORTS)
            logger.info(
                "Maritime: loaded %d hardcoded major ports", len(_ports),
            )

    _loaded = True


# ---------------------------------------------------------------------------
# Haversine helper
# ---------------------------------------------------------------------------
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute distance between two points using the Haversine formula.

    Args:
        lat1, lon1: First point in decimal degrees.
        lat2, lon2: Second point in decimal degrees.

    Returns:
        Distance in kilometers.
    """
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------
def find_nearest_port(
    lat: float, lon: float, max_km: float = 100,
) -> dict[str, Any] | None:
    """Find nearest port to a coordinate.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        max_km: Maximum search radius in kilometers.

    Returns:
        Port dict with distance_km, or None if nothing within range.
    """
    if not _ports:
        return None

    best: dict[str, Any] | None = None
    best_dist = max_km

    for port in _ports:
        dist = _haversine_km(lat, lon, port["lat"], port["lon"])
        if dist < best_dist:
            best_dist = dist
            best = {**port, "distance_km": round(dist, 1)}

    return best


def find_eez(
    lat: float, lon: float, max_km: float = 200,
) -> dict[str, Any] | None:
    """Find nearest EEZ to a coordinate.

    Uses distance from the EEZ center point as a proxy when full polygon
    geometry is not loaded.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        max_km: Maximum search radius in kilometers.

    Returns:
        EEZ dict with distance_km, or None if nothing within range.
    """
    if not _eez_zones:
        return None

    best: dict[str, Any] | None = None
    best_dist = max_km

    for eez in _eez_zones:
        dist = _haversine_km(lat, lon, eez["center_lat"], eez["center_lon"])
        if dist < best_dist:
            best_dist = dist
            best = {**eez, "distance_km": round(dist, 1)}

    return best


def get_maritime_context(lat: float, lon: float) -> dict[str, Any]:
    """Get full maritime context for a coordinate.

    Combines nearest port and nearest EEZ lookups into a single response
    dict. Used by the copilot router and convergence scorer to add
    maritime context to signals.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.

    Returns:
        Dict with keys: nearest_port, nearest_eez, coordinate.
    """
    return {
        "coordinate": {"lat": lat, "lon": lon},
        "nearest_port": find_nearest_port(lat, lon),
        "nearest_eez": find_eez(lat, lon),
    }


def get_stats() -> dict[str, Any]:
    """Return maritime reference data statistics."""
    return {
        "eez_zones": len(_eez_zones),
        "ports": len(_ports),
        "loaded": _loaded,
    }
