"""
OSM Overpass API service client.

Queries OpenStreetMap for military/infrastructure features.
Throttle: 1 request per 60s for large area queries.
No API key required.
"""
import asyncio
import hashlib
import logging
import random
from typing import Any

import httpx

logger = logging.getLogger(__name__)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

CONFLICT_RELEVANT_TAGS = [
    "military",
    "aeroway=aerodrome",
    "aeroway=helipad",
    "man_made=petroleum_well",
    "man_made=pipeline",
    "power=plant",
    "landuse=military",
]

_MAX_RETRIES = 3
_BASE_BACKOFF = 10.0


class OverpassService:
    """Client for the OpenStreetMap Overpass API."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=180.0)

    async def query_infrastructure(
        self,
        bbox: tuple[float, float, float, float],
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Query OSM infrastructure features within a bounding box.

        Args:
            bbox: (west, south, east, north) in WGS84.
            tags: OSM tag filters. Defaults to CONFLICT_RELEVANT_TAGS.

        Returns:
            List of normalized element dicts with lat, lon, tags, and OSM metadata.
        """
        if tags is None:
            tags = CONFLICT_RELEVANT_TAGS

        west, south, east, north = bbox
        # Overpass bbox format: (south, west, north, east)
        bbox_str = f"{south},{west},{north},{east}"

        # Build Overpass QL query
        query = _build_overpass_query(tags, bbox_str)
        logger.info("Overpass: querying bbox (%s) with %d tag filters", bbox_str, len(tags))

        response = await self._request_with_backoff(query)
        body = response.json()

        elements = body.get("elements", [])
        results = _normalize_elements(elements)
        logger.info("Overpass: got %d elements, %d with valid coordinates", len(elements), len(results))
        return results

    async def _request_with_backoff(self, query: str) -> httpx.Response:
        """POST to Overpass with exponential backoff on 429/503.

        Args:
            query: Overpass QL query string.

        Returns:
            Successful httpx.Response.

        Raises:
            httpx.HTTPStatusError: After retries exhausted.
        """
        last_response: httpx.Response | None = None

        for attempt in range(_MAX_RETRIES + 1):
            response = await self._client.post(
                OVERPASS_URL,
                data={"data": query},
            )

            if response.status_code == 200:
                return response

            if response.status_code in (429, 503, 504):
                last_response = response
                if attempt < _MAX_RETRIES:
                    backoff = _BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 5)
                    logger.warning(
                        "Overpass %d, retrying in %.0fs (attempt %d/%d)",
                        response.status_code, backoff, attempt + 1, _MAX_RETRIES,
                    )
                    await asyncio.sleep(backoff)
                continue

            response.raise_for_status()

        if last_response is not None:
            last_response.raise_for_status()
        raise httpx.HTTPStatusError(
            "Overpass request failed after retries",
            request=httpx.Request("POST", OVERPASS_URL),
            response=last_response,  # type: ignore[arg-type]
        )

    def build_dedup_hash(self, element: dict[str, Any]) -> str:
        """Compute deduplication hash for an OSM element.

        Uses OSM type + id as the dedup key (globally unique in OSM).

        Args:
            element: Normalized OSM element dict.

        Returns:
            SHA-256 hex string.
        """
        key = f"osm:{element['osm_type']}:{element['osm_id']}"
        return hashlib.sha256(key.encode()).hexdigest()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


def _build_overpass_query(tags: list[str], bbox: str) -> str:
    """Build an Overpass QL query from a list of tag filters.

    Generates union queries across node and way types for each tag.

    Args:
        tags: List of OSM tag filters (e.g. 'military', 'aeroway=aerodrome').
        bbox: Overpass bbox string '(south,west,north,east)'.

    Returns:
        Overpass QL query string.
    """
    parts: list[str] = []
    for tag in tags:
        if "=" in tag:
            key, value = tag.split("=", 1)
            tag_filter = f'["{key}"="{value}"]'
        else:
            tag_filter = f'["{tag}"]'

        parts.append(f'  node{tag_filter}({bbox});')
        parts.append(f'  way{tag_filter}({bbox});')

    union = "\n".join(parts)
    return f"[out:json][timeout:120];\n(\n{union}\n);\nout center;\n"


def _normalize_elements(elements: list[dict]) -> list[dict[str, Any]]:
    """Normalize Overpass response elements to a flat format with lat/lon.

    Nodes have direct lat/lon. Ways use the 'center' coordinate from 'out center'.

    Args:
        elements: Raw Overpass JSON elements.

    Returns:
        List of normalized dicts with osm_type, osm_id, lat, lon, tags.
    """
    results: list[dict[str, Any]] = []

    for el in elements:
        osm_type = el.get("type", "")
        osm_id = el.get("id", 0)
        tags = el.get("tags", {})

        # Extract coordinates
        if osm_type == "node":
            lat = el.get("lat")
            lon = el.get("lon")
        elif osm_type == "way":
            center = el.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")
        else:
            continue

        if lat is None or lon is None:
            continue

        # Determine infrastructure type from tags
        infra_type = _classify_infrastructure(tags)

        results.append({
            "osm_type": osm_type,
            "osm_id": osm_id,
            "latitude": lat,
            "longitude": lon,
            "tags": tags,
            "infra_type": infra_type,
            "name": tags.get("name", ""),
        })

    return results


def _classify_infrastructure(tags: dict[str, str]) -> str:
    """Classify an OSM element into an infrastructure category.

    Args:
        tags: OSM tag dict.

    Returns:
        Classification string for display.
    """
    if tags.get("military"):
        return f"military_{tags['military']}"
    if tags.get("aeroway") == "aerodrome":
        return "aerodrome"
    if tags.get("aeroway") == "helipad":
        return "helipad"
    if tags.get("man_made") == "petroleum_well":
        return "petroleum_well"
    if tags.get("man_made") == "pipeline":
        return "pipeline"
    if tags.get("power") == "plant":
        return "power_plant"
    if tags.get("landuse") == "military":
        return "military_zone"
    return "infrastructure"
