"""
Cyber-GEOINT router — exposed devices, infrastructure, wireless networks.

Bridges logical networks (IPs, routing, MAC addresses) and physical
geography (coordinates, data centers, cell towers).

BYOK keys for Shodan/Censys/WiGLE are passed per-request in headers.
PeeringDB and submarine cable data are free and require no key.
"""
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.services.cyber_geo import (
    IP_GEOLOCATION_WARNING,
    CensysClient,
    PeeringDBClient,
    ShodanClient,
    SubmarineCableClient,
    WiGLEClient,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_shodan = ShodanClient()
_censys = CensysClient()
_wigle = WiGLEClient()
_peeringdb = PeeringDBClient()
_cables = SubmarineCableClient()


# ── BYOK endpoints (require API key in header) ─────────────────────────────

@router.get("/shodan/search")
async def shodan_search(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(default=50, le=500),
    query: str = Query(default=""),
    x_shodan_key: str | None = Header(default=None, alias="X-Shodan-Key"),
) -> dict:
    """Search Shodan for exposed devices near a coordinate. Requires BYOK."""
    if not x_shodan_key:
        raise HTTPException(401, "Shodan API key required (X-Shodan-Key header)")
    try:
        results = await _shodan.search_geo(x_shodan_key, lat, lng, radius_km, query)
    except Exception as exc:
        logger.exception("Shodan query failed")
        raise HTTPException(502, "External device search failed")
    return {"results": results, "count": len(results), "warning": IP_GEOLOCATION_WARNING}


@router.get("/censys/search")
async def censys_search(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(default=50, le=500),
    query: str = Query(default="services.service_name: HTTP"),
    x_censys_id: str | None = Header(default=None, alias="X-Censys-Id"),
    x_censys_secret: str | None = Header(default=None, alias="X-Censys-Secret"),
) -> dict:
    """Search Censys for hosts near a coordinate. Requires BYOK."""
    if not x_censys_id or not x_censys_secret:
        raise HTTPException(401, "Censys API credentials required (X-Censys-Id, X-Censys-Secret headers)")
    try:
        results = await _censys.search_geo(x_censys_id, x_censys_secret, query, lat, lng, radius_km)
    except Exception as exc:
        logger.exception("Censys query failed")
        raise HTTPException(502, "External host search failed")
    return {"results": results, "count": len(results), "warning": IP_GEOLOCATION_WARNING}


@router.get("/wigle/wifi")
async def wigle_wifi(
    lat_min: float = Query(...), lat_max: float = Query(...),
    lng_min: float = Query(...), lng_max: float = Query(...),
    x_wigle_name: str | None = Header(default=None, alias="X-WiGLE-Name"),
    x_wigle_token: str | None = Header(default=None, alias="X-WiGLE-Token"),
) -> dict:
    """Search WiGLE for WiFi networks in a bounding box. Requires BYOK."""
    if not x_wigle_name or not x_wigle_token:
        raise HTTPException(401, "WiGLE credentials required (X-WiGLE-Name, X-WiGLE-Token headers)")
    try:
        results = await _wigle.search_wifi(x_wigle_name, x_wigle_token, lat_min, lat_max, lng_min, lng_max)
    except Exception as exc:
        logger.exception("WiGLE WiFi query failed")
        raise HTTPException(502, "Wireless network search failed")
    return {"results": results, "count": len(results)}


@router.get("/wigle/cells")
async def wigle_cells(
    lat_min: float = Query(...), lat_max: float = Query(...),
    lng_min: float = Query(...), lng_max: float = Query(...),
    x_wigle_name: str | None = Header(default=None, alias="X-WiGLE-Name"),
    x_wigle_token: str | None = Header(default=None, alias="X-WiGLE-Token"),
) -> dict:
    """Search WiGLE for cell towers in a bounding box. Requires BYOK."""
    if not x_wigle_name or not x_wigle_token:
        raise HTTPException(401, "WiGLE credentials required (X-WiGLE-Name, X-WiGLE-Token headers)")
    try:
        results = await _wigle.search_cell_towers(x_wigle_name, x_wigle_token, lat_min, lat_max, lng_min, lng_max)
    except Exception as exc:
        logger.exception("WiGLE cell tower query failed")
        raise HTTPException(502, "Cell tower search failed")
    return {"results": results, "count": len(results)}


# ── Free endpoints (no key required) ───────────────────────────────────────

@router.get("/infrastructure/data-centers")
async def get_data_centers(
    country: str | None = Query(default=None, description="ISO country code"),
) -> dict:
    """Get data center locations from PeeringDB. Free, no key needed."""
    try:
        results = await _peeringdb.get_facilities(country)
    except Exception as exc:
        logger.exception("PeeringDB facilities query failed")
        raise HTTPException(502, "Infrastructure data temporarily unavailable")
    return {"results": results, "count": len(results)}


@router.get("/infrastructure/ixps")
async def get_ixps(
    country: str | None = Query(default=None),
) -> dict:
    """Get Internet Exchange Point locations from PeeringDB. Free."""
    try:
        results = await _peeringdb.get_ixps(country)
    except Exception as exc:
        logger.exception("PeeringDB IXP query failed")
        raise HTTPException(502, "Infrastructure data temporarily unavailable")
    return {"results": results, "count": len(results)}


@router.get("/infrastructure/submarine-cables")
async def get_submarine_cable_landings() -> dict:
    """Get submarine cable landing points from TeleGeography. Free."""
    try:
        results = await _cables.get_landing_points()
    except Exception as exc:
        logger.exception("Submarine cable data fetch failed")
        raise HTTPException(502, "Infrastructure data temporarily unavailable")
    return {"results": results, "count": len(results)}


@router.get("/infrastructure/submarine-cables/geojson")
async def get_submarine_cables_geojson() -> dict:
    """Get full submarine cable network as GeoJSON for map rendering. Free."""
    try:
        return await _cables.get_cables_geojson()
    except Exception as exc:
        raise HTTPException(502, f"Cable data fetch failed: {str(exc)[:100]}")
