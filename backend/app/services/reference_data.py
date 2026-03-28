"""
Reference data enrichment service.

Loads static geospatial reference datasets on startup for:
  1. City-level geocoding (GeoNames cities15000)
  2. Country/admin lookups (GeoNames countryInfo + admin1 codes)
  3. Military airfield identification (OurAirports)
  4. ADM1 boundary normalization (geoBoundaries simplified polygons)

Data is loaded once into memory and used to enrich signals and improve AOI
normalization. All sources are free and open.
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import math
import zipfile
from typing import Any

import httpx
from shapely.geometry import Point, box, shape as shapely_shape

logger = logging.getLogger(__name__)

GEONAMES_URL = "https://download.geonames.org/export/dump/cities15000.zip"
COUNTRY_INFO_URL = "https://download.geonames.org/export/dump/countryInfo.txt"
ADMIN1_CODES_URL = "https://download.geonames.org/export/dump/admin1CodesASCII.txt"
OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
GEOBOUNDARIES_ADM1_URL = "https://www.geoboundaries.org/api/current/gbOpen/ALL/ADM1/"

# Singleton state loaded once at startup.
_cities: list[dict[str, Any]] = []
_military_airfields: list[dict[str, Any]] = []
_country_info_by_iso2: dict[str, dict[str, str]] = {}
_admin1_name_by_key: dict[str, str] = {}
_adm1_boundaries: list[dict[str, Any]] = []
_loaded = False


async def load_reference_data() -> None:
    """Download and parse reference datasets into memory."""
    global _loaded
    if _loaded:
        return

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        await _load_country_info(client)
        await _load_admin1_codes(client)
        await _load_cities(client)
        await _load_airfields(client)
        await scrape_geoboundaries(client)

    _loaded = True


async def scrape_geoboundaries(client: httpx.AsyncClient) -> None:
    """Load simplified geoBoundaries ADM1 polygons for AOI normalization."""
    global _adm1_boundaries

    if _adm1_boundaries:
        return

    try:
        response = await client.get(GEOBOUNDARIES_ADM1_URL)
        response.raise_for_status()
        manifest = response.json()
    except Exception:
        logger.warning("Failed to load geoBoundaries ADM1 manifest", exc_info=True)
        return

    if not isinstance(manifest, list):
        logger.warning("geoBoundaries manifest returned unexpected payload")
        return

    semaphore = asyncio.Semaphore(12)
    tasks = [
        _fetch_adm1_country(client, semaphore, entry)
        for entry in manifest
        if isinstance(entry, dict)
    ]

    boundary_sets = await asyncio.gather(*tasks, return_exceptions=True)
    loaded_boundaries: list[dict[str, Any]] = []

    for result in boundary_sets:
        if isinstance(result, Exception):
            logger.warning("geoBoundaries country load failed", exc_info=result)
            continue
        loaded_boundaries.extend(result)

    _adm1_boundaries = loaded_boundaries
    logger.info("Reference: loaded %d ADM1 boundaries from geoBoundaries", len(_adm1_boundaries))


def geocode_text(text: str) -> tuple[float | None, float | None, str | None]:
    """Geocode text by matching GeoNames cities with country/admin weighting."""
    if not _cities:
        return None, None, None

    text_lower = text.lower()
    best_match: dict[str, Any] | None = None
    best_score = -1

    for city in _cities:
        if city["name"].lower() not in text_lower:
            continue

        score = int(city["population"])
        country_name = str(city.get("country_name", "")).lower()
        admin1_name = str(city.get("admin1_name", "")).lower()

        if country_name and country_name in text_lower:
            score += 10_000_000
        if admin1_name and admin1_name in text_lower:
            score += 5_000_000

        if best_match is None or score > best_score:
            best_match = city
            best_score = score

    if best_match:
        return best_match["lat"], best_match["lon"], best_match["name"]
    return None, None, None


def find_nearest_city(lat: float, lon: float, max_km: float = 100) -> dict[str, Any] | None:
    """Find the nearest city to a coordinate."""
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


def find_nearby_airfields(lat: float, lon: float, max_km: float = 200) -> list[dict[str, Any]]:
    """Find military airfields near a coordinate."""
    results = []
    for airfield in _military_airfields:
        dist = _haversine_km(lat, lon, airfield["lat"], airfield["lon"])
        if dist <= max_km:
            results.append({**airfield, "distance_km": round(dist, 1)})

    results.sort(key=lambda item: item["distance_km"])
    return results


def find_admin1_for_point(lat: float, lon: float) -> dict[str, Any] | None:
    """Return the ADM1 polygon covering a point, if any."""
    if not _adm1_boundaries:
        return None

    point = Point(lon, lat)
    matches: list[dict[str, Any]] = []

    for boundary in _adm1_boundaries:
        min_lon, min_lat, max_lon, max_lat = boundary["bbox"]
        if lon < min_lon or lon > max_lon or lat < min_lat or lat > max_lat:
            continue
        if boundary["geometry"].covers(point):
            matches.append(boundary)

    if not matches:
        return None

    matches.sort(key=lambda item: item["geometry"].area)
    return _serialize_boundary(matches[0])


def find_admin1s_for_bbox(
    west: float,
    south: float,
    east: float,
    north: float,
) -> list[dict[str, Any]]:
    """Return ADM1 boundaries that intersect a bounding box."""
    if not _adm1_boundaries:
        return []

    query_box = box(west, south, east, north)
    matches: list[dict[str, Any]] = []

    for boundary in _adm1_boundaries:
        min_lon, min_lat, max_lon, max_lat = boundary["bbox"]
        if max_lon < west or min_lon > east or max_lat < south or min_lat > north:
            continue
        if boundary["geometry"].intersects(query_box):
            matches.append(_serialize_boundary(boundary))

    matches.sort(key=lambda item: (item["country_iso3"], item["name"]))
    return matches


def get_stats() -> dict[str, Any]:
    """Return reference data statistics."""
    return {
        "cities": len(_cities),
        "military_airfields": len(_military_airfields),
        "countries": len(_country_info_by_iso2),
        "adm1_boundaries": len(_adm1_boundaries),
        "loaded": _loaded,
    }


async def _load_country_info(client: httpx.AsyncClient) -> None:
    """Load GeoNames country metadata for ISO2/ISO3 normalization."""
    try:
        response = await client.get(COUNTRY_INFO_URL)
        response.raise_for_status()
    except Exception:
        logger.warning("Failed to load GeoNames countryInfo", exc_info=True)
        return

    for line in response.text.splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 5:
            continue
        iso2 = cols[0].strip()
        iso3 = cols[1].strip()
        country_name = cols[4].strip()
        if not iso2:
            continue
        _country_info_by_iso2[iso2] = {"iso3": iso3, "name": country_name}

    logger.info("Reference: loaded %d countries from GeoNames", len(_country_info_by_iso2))


async def _load_admin1_codes(client: httpx.AsyncClient) -> None:
    """Load GeoNames admin1 code to human-readable name mappings."""
    try:
        response = await client.get(ADMIN1_CODES_URL)
        response.raise_for_status()
    except Exception:
        logger.warning("Failed to load GeoNames admin1 codes", exc_info=True)
        return

    for line in response.text.splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 2:
            continue
        key = cols[0].strip()
        admin_name = cols[1].strip()
        if key and admin_name:
            _admin1_name_by_key[key] = admin_name

    logger.info("Reference: loaded %d admin1 code mappings", len(_admin1_name_by_key))


async def _load_cities(client: httpx.AsyncClient) -> None:
    """Load GeoNames cities15000 with country/admin context for geocoding."""
    try:
        response = await client.get(GEONAMES_URL)
        response.raise_for_status()
    except Exception:
        logger.warning("Failed to load GeoNames cities", exc_info=True)
        return

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        with archive.open("cities15000.txt") as handle:
            for line in handle.read().decode("utf-8").strip().split("\n"):
                cols = line.split("\t")
                if len(cols) < 15:
                    continue

                country_iso2 = cols[8].strip()
                admin1_code = cols[10].strip()
                country_info = _country_info_by_iso2.get(country_iso2, {})
                admin_key = f"{country_iso2}.{admin1_code}" if admin1_code else ""

                _cities.append({
                    "name": cols[1],
                    "country": country_iso2,
                    "country_iso2": country_iso2,
                    "country_iso3": country_info.get("iso3", ""),
                    "country_name": country_info.get("name", ""),
                    "admin1_code": admin1_code,
                    "admin1_name": _admin1_name_by_key.get(admin_key, ""),
                    "lat": float(cols[4]),
                    "lon": float(cols[5]),
                    "population": int(cols[14]) if cols[14].isdigit() else 0,
                })

    logger.info("Reference: loaded %d cities from GeoNames", len(_cities))


async def _load_airfields(client: httpx.AsyncClient) -> None:
    """Load military-relevant airfields from OurAirports."""
    try:
        response = await client.get(OURAIRPORTS_URL)
        response.raise_for_status()
    except Exception:
        logger.warning("Failed to load OurAirports data", exc_info=True)
        return

    reader = csv.DictReader(io.StringIO(response.text))
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
        except (KeyError, TypeError, ValueError):
            continue

    logger.info("Reference: loaded %d military airfields from OurAirports", len(_military_airfields))


async def _fetch_adm1_country(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    entry: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fetch and parse one country's simplified ADM1 GeoJSON file."""
    url = str(entry.get("simplifiedGeometryGeoJSON") or entry.get("gjDownloadURL") or "").strip()
    if not url:
        return []

    country_iso3 = str(entry.get("boundaryISO", "")).strip()
    country_name = str(entry.get("boundaryName", "")).strip()

    async with semaphore:
        response = await client.get(url)
        response.raise_for_status()
        body = response.json()

    features = body.get("features", [])
    boundaries: list[dict[str, Any]] = []

    for feature in features:
        if not isinstance(feature, dict):
            continue
        geometry = feature.get("geometry")
        properties = feature.get("properties", {})
        if not isinstance(properties, dict):
            continue

        try:
            geom = shapely_shape(geometry)
        except Exception:
            continue

        if geom.is_empty:
            continue

        boundaries.append({
            "name": str(properties.get("shapeName", "")).strip(),
            "shape_iso": str(properties.get("shapeISO", "")).strip(),
            "shape_id": str(properties.get("shapeID", "")).strip(),
            "country_iso3": country_iso3 or str(properties.get("shapeGroup", "")).strip(),
            "country_name": country_name,
            "boundary_type": str(properties.get("shapeType", "ADM1")).strip(),
            "bbox": geom.bounds,
            "geometry": geom,
        })

    return boundaries


def _serialize_boundary(boundary: dict[str, Any]) -> dict[str, Any]:
    """Return boundary metadata without the Shapely geometry object."""
    return {
        "name": boundary["name"],
        "shape_iso": boundary["shape_iso"],
        "shape_id": boundary["shape_id"],
        "country_iso3": boundary["country_iso3"],
        "country_name": boundary["country_name"],
        "boundary_type": boundary["boundary_type"],
        "bbox": boundary["bbox"],
    }


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute distance between two points using the Haversine formula."""
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
