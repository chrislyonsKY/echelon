"""
Reference data enrichment service.

Loads static geospatial reference datasets on startup for:
  1. City-level geocoding (GeoNames cities15000)
  2. Military airfield identification (OurAirports)
  3. Port proximity labeling (GeoNames + feature codes)

Data is loaded once into memory and used to enrich signals and
improve copilot responses. All sources are free and open.
"""
import csv
import io
import logging
import math
import zipfile
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GEONAMES_URL = "https://download.geonames.org/export/dump/cities15000.zip"
OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"

# Singleton — loaded once
_cities: list[dict[str, Any]] = []
_military_airfields: list[dict[str, Any]] = []
_loaded = False


async def load_reference_data() -> None:
    """Download and parse reference datasets into memory.

    Call once at application startup. Subsequent calls are no-ops.
    """
    global _cities, _military_airfields, _loaded
    if _loaded:
        return

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        # GeoNames cities with population > 15,000
        try:
            r = await client.get(GEONAMES_URL)
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                with zf.open("cities15000.txt") as f:
                    for line in f.read().decode("utf-8").strip().split("\n"):
                        cols = line.split("\t")
                        if len(cols) < 15:
                            continue
                        _cities.append({
                            "name": cols[1],
                            "country": cols[8],
                            "lat": float(cols[4]),
                            "lon": float(cols[5]),
                            "population": int(cols[14]) if cols[14].isdigit() else 0,
                        })
            logger.info("Reference: loaded %d cities from GeoNames", len(_cities))
        except Exception:
            logger.warning("Failed to load GeoNames cities", exc_info=True)

        # OurAirports — military airfields
        try:
            r = await client.get(OURAIRPORTS_URL)
            r.raise_for_status()
            reader = csv.DictReader(io.StringIO(r.text))
            for row in reader:
                if row.get("type") not in ("large_airport", "medium_airport"):
                    continue
                name = row.get("name", "").lower()
                keywords = row.get("keywords", "").lower()
                is_military = any(
                    term in name or term in keywords
                    for term in ("military", "air base", "air force", "afb", "naval air", "army airfield")
                )
                if not is_military:
                    continue
                try:
                    _military_airfields.append({
                        "name": row["name"],
                        "country": row.get("iso_country", ""),
                        "lat": float(row["latitude_deg"]),
                        "lon": float(row["longitude_deg"]),
                        "type": row.get("type", ""),
                    })
                except (ValueError, KeyError):
                    continue
            logger.info("Reference: loaded %d military airfields from OurAirports", len(_military_airfields))
        except Exception:
            logger.warning("Failed to load OurAirports data", exc_info=True)

    _loaded = True


def geocode_text(text: str) -> tuple[float | None, float | None, str | None]:
    """Geocode text by matching city names from GeoNames.

    Searches for city names mentioned in the text, preferring larger cities.
    Much more precise than country-centroid geocoding.

    Args:
        text: Article title + description.

    Returns:
        (lat, lon, city_name) or (None, None, None) if no match.
    """
    if not _cities:
        return None, None, None

    text_lower = text.lower()
    best_match: dict | None = None

    for city in _cities:
        if city["name"].lower() in text_lower:
            # Prefer larger cities to avoid false matches on common names
            if best_match is None or city["population"] > best_match["population"]:
                best_match = city

    if best_match:
        return best_match["lat"], best_match["lon"], best_match["name"]
    return None, None, None


def find_nearest_city(lat: float, lon: float, max_km: float = 100) -> dict | None:
    """Find the nearest city to a coordinate.

    Args:
        lat: Latitude.
        lon: Longitude.
        max_km: Maximum distance in kilometers.

    Returns:
        City dict with name, country, distance_km, or None.
    """
    if not _cities:
        return None

    best = None
    best_dist = max_km

    for city in _cities:
        dist = _haversine_km(lat, lon, city["lat"], city["lon"])
        if dist < best_dist:
            best_dist = dist
            best = {**city, "distance_km": round(dist, 1)}

    return best


def find_nearby_airfields(lat: float, lon: float, max_km: float = 200) -> list[dict]:
    """Find military airfields near a coordinate.

    Args:
        lat: Latitude.
        lon: Longitude.
        max_km: Maximum distance in kilometers.

    Returns:
        List of airfield dicts sorted by distance.
    """
    results = []
    for af in _military_airfields:
        dist = _haversine_km(lat, lon, af["lat"], af["lon"])
        if dist <= max_km:
            results.append({**af, "distance_km": round(dist, 1)})
    results.sort(key=lambda x: x["distance_km"])
    return results


def get_stats() -> dict:
    """Return reference data statistics."""
    return {
        "cities": len(_cities),
        "military_airfields": len(_military_airfields),
        "loaded": _loaded,
    }


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
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
