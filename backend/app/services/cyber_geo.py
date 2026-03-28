"""
Cyber-GEOINT service — bridges logical networks and physical geography.

Integrates:
- Shodan (BYOK) — exposed IoT devices, ICS/SCADA, servers
- Censys (BYOK) — attack surface mapping, TLS certificates
- WiGLE (BYOK) — WiFi networks, Bluetooth, cell towers
- PeeringDB (free) — IXPs and data center locations
- Submarine cables (free) — TeleGeography cable landing points
- OpenCelliD (free tier) — cell tower locations

All BYOK keys are passed per-request in headers, never stored.
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0


class ShodanClient:
    """Query Shodan for exposed devices in a geographic area. Requires BYOK."""

    BASE = "https://api.shodan.io"

    async def search_geo(
        self, api_key: str, lat: float, lng: float, radius_km: float = 50, query: str = ""
    ) -> list[dict[str, Any]]:
        """Search Shodan for devices near a coordinate."""
        geo_query = f"geo:{lat},{lng},{int(radius_km)}"
        full_query = f"{query} {geo_query}".strip()

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.BASE}/shodan/host/search",
                params={"key": api_key, "query": full_query, "minify": True},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for match in data.get("matches", []):
            loc = match.get("location", {})
            if loc.get("latitude") and loc.get("longitude"):
                results.append({
                    "ip": match.get("ip_str", ""),
                    "port": match.get("port"),
                    "org": match.get("org", ""),
                    "product": match.get("product", ""),
                    "os": match.get("os", ""),
                    "lat": loc["latitude"],
                    "lng": loc["longitude"],
                    "city": loc.get("city", ""),
                    "country": loc.get("country_name", ""),
                    "isp": match.get("isp", ""),
                    "vulns": list(match.get("vulns", {}).keys())[:5] if match.get("vulns") else [],
                })
        return results


class CensysClient:
    """Query Censys for hosts in a geographic area. Requires BYOK."""

    BASE = "https://search.censys.io/api/v2"

    async def search_geo(
        self, api_id: str, api_secret: str, query: str, lat: float, lng: float, radius_km: float = 50,
    ) -> list[dict[str, Any]]:
        """Search Censys hosts by geographic location."""
        full_query = f"{query} and location.coordinates: [{lng},{lat}] and location.registered_country_code: *"

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.BASE}/hosts/search",
                params={"q": full_query, "per_page": 50},
                auth=(api_id, api_secret),
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for hit in data.get("result", {}).get("hits", []):
            loc = hit.get("location", {})
            coords = loc.get("coordinates", {})
            if coords.get("latitude") and coords.get("longitude"):
                results.append({
                    "ip": hit.get("ip", ""),
                    "services": [s.get("service_name", "") for s in hit.get("services", [])[:5]],
                    "lat": coords["latitude"],
                    "lng": coords["longitude"],
                    "city": loc.get("city", ""),
                    "country": loc.get("country", ""),
                    "asn": hit.get("autonomous_system", {}).get("asn"),
                    "org": hit.get("autonomous_system", {}).get("name", ""),
                })
        return results


class WiGLEClient:
    """Query WiGLE for WiFi networks and cell towers. Requires BYOK."""

    BASE = "https://api.wigle.net/api/v2"

    async def search_wifi(
        self, api_name: str, api_token: str,
        lat_min: float, lat_max: float, lng_min: float, lng_max: float,
    ) -> list[dict[str, Any]]:
        """Search WiFi networks within a bounding box."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.BASE}/network/search",
                params={
                    "latrange1": lat_min, "latrange2": lat_max,
                    "longrange1": lng_min, "longrange2": lng_max,
                    "resultsPerPage": 100,
                },
                auth=(api_name, api_token),
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for net in data.get("results", []):
            if net.get("trilat") and net.get("trilong"):
                results.append({
                    "ssid": net.get("ssid", ""),
                    "bssid": net.get("netid", ""),
                    "encryption": net.get("encryption", ""),
                    "channel": net.get("channel"),
                    "lat": net["trilat"],
                    "lng": net["trilong"],
                    "lastSeen": net.get("lastupdt", ""),
                    "type": net.get("type", "wifi"),
                })
        return results

    async def search_cell_towers(
        self, api_name: str, api_token: str,
        lat_min: float, lat_max: float, lng_min: float, lng_max: float,
    ) -> list[dict[str, Any]]:
        """Search cell towers within a bounding box."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.BASE}/cell/search",
                params={
                    "latrange1": lat_min, "latrange2": lat_max,
                    "longrange1": lng_min, "longrange2": lng_max,
                    "resultsPerPage": 100,
                },
                auth=(api_name, api_token),
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for cell in data.get("results", []):
            if cell.get("trilat") and cell.get("trilong"):
                results.append({
                    "operator": cell.get("operator", ""),
                    "mcc": cell.get("mcc"),
                    "mnc": cell.get("mnc"),
                    "lac": cell.get("lac"),
                    "cellId": cell.get("cid"),
                    "lat": cell["trilat"],
                    "lng": cell["trilong"],
                    "range": cell.get("range"),
                    "type": "cell_tower",
                })
        return results


class PeeringDBClient:
    """Query PeeringDB for IXPs and data center locations. Free, no key needed."""

    BASE = "https://www.peeringdb.com/api"

    async def get_facilities(self, country: str | None = None) -> list[dict[str, Any]]:
        """Get data center / colocation facility locations."""
        params: dict[str, Any] = {"depth": 1}
        if country:
            params["country"] = country

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{self.BASE}/fac", params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for fac in data.get("data", []):
            if fac.get("latitude") and fac.get("longitude"):
                results.append({
                    "name": fac.get("name", ""),
                    "org": fac.get("org_name", ""),
                    "city": fac.get("city", ""),
                    "country": fac.get("country", ""),
                    "lat": fac["latitude"],
                    "lng": fac["longitude"],
                    "website": fac.get("website", ""),
                    "type": "data_center",
                })
        return results

    async def get_ixps(self, country: str | None = None) -> list[dict[str, Any]]:
        """Get Internet Exchange Point locations."""
        params: dict[str, Any] = {"depth": 1}
        if country:
            params["country"] = country

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{self.BASE}/ix", params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for ix in data.get("data", []):
            # IXPs don't always have direct coords — use facility location
            if ix.get("city") and ix.get("country"):
                results.append({
                    "name": ix.get("name", ""),
                    "city": ix.get("city", ""),
                    "country": ix.get("country", ""),
                    "media": ix.get("media", ""),
                    "proto_unicast": ix.get("proto_unicast"),
                    "networks": ix.get("net_count", 0),
                    "type": "ixp",
                })
        return results


class SubmarineCableClient:
    """Load submarine cable landing points from TeleGeography's open data."""

    CABLES_URL = "https://raw.githubusercontent.com/telegeography/www.submarinecablemap.com/master/web/public/api/v3/cable/cable-geo.json"
    LANDING_URL = "https://raw.githubusercontent.com/telegeography/www.submarinecablemap.com/master/web/public/api/v3/landing-point/landing-point-geo.json"

    async def get_landing_points(self) -> list[dict[str, Any]]:
        """Get submarine cable landing point locations."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(self.LANDING_URL)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [])
            if len(coords) >= 2:
                results.append({
                    "name": props.get("name", ""),
                    "country": props.get("country", ""),
                    "lat": coords[1],
                    "lng": coords[0],
                    "cableCount": len(props.get("cable_ids", [])),
                    "type": "cable_landing",
                })
        return results

    async def get_cables_geojson(self) -> dict[str, Any]:
        """Get full submarine cable GeoJSON for rendering as map layer."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(self.CABLES_URL)
            resp.raise_for_status()
            return resp.json()


# ── IP Geolocation with accuracy warnings ─────────────────────────────────────

# IMPORTANT: IP geolocation is approximate. Results often point to the
# geographic center of a country or ISP default location (e.g., "the farm
# in Kansas" for US-defaulted IPs). Always display accuracy warnings.

IP_GEOLOCATION_WARNING = (
    "IP geolocation is approximate and should not be treated as ground truth. "
    "Results may point to ISP default locations, country centroids, or data center "
    "addresses rather than actual device locations. Use for general area assessment only."
)
