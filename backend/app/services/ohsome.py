"""
ohsome full-history client for recent OSM military-tag changes.

Replaces point-in-time Overpass snapshots with temporal change detection based
on OpenStreetMap history. The service queries the official ohsome
``elementsFullHistory/geometry`` endpoint and extracts only features whose
military-related tags were added, removed, or updated inside a rolling window.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from shapely.geometry import shape as shapely_shape

logger = logging.getLogger(__name__)

OHSOME_URL = "https://api.ohsome.org/v1/elementsFullHistory/geometry"
MILITARY_FILTER = "military=* or landuse=military or boundary=military"
DEFAULT_WINDOW_DAYS = 7

_MAX_RETRIES = 3
_BASE_BACKOFF = 5.0
_REQUEST_TIMEOUT = 180.0
_TIMEFRAME_ERROR_PATTERN = re.compile(r"timeframe \((?P<start>[^ ]+) to (?P<end>[^)]+)\)")


class OhsomeService:
    """Client for recent military-tag history from the ohsome API."""

    def __init__(self, window_days: int = DEFAULT_WINDOW_DAYS) -> None:
        self._window_days = window_days
        self._client = httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, follow_redirects=True)

    async def query_military_changes(
        self,
        bbox: tuple[float, float, float, float],
        *,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return military-tag changes within *bbox* during the recent window."""
        requested_end = (end_time or datetime.now(UTC)).astimezone(UTC)
        requested_start = requested_end - timedelta(days=self._window_days)

        west, south, east, north = bbox
        body = {
            "bboxes": f"{west},{south},{east},{north}",
            "time": f"{_format_timestamp(requested_start)},{_format_timestamp(requested_end)}",
            "filter": MILITARY_FILTER,
            "properties": "tags",
        }

        try:
            response = await self._request_with_backoff(body)
        except httpx.HTTPStatusError as exc:
            adjusted = _adjusted_window_from_error(exc.response, requested_end, self._window_days)
            if adjusted is None:
                raise

            adjusted_start, adjusted_end = adjusted
            logger.info(
                "ohsome: clamping query window to available data %s -> %s",
                _format_timestamp(adjusted_start),
                _format_timestamp(adjusted_end),
            )
            body["time"] = f"{_format_timestamp(adjusted_start)},{_format_timestamp(adjusted_end)}"
            response = await self._request_with_backoff(body)
            requested_start, requested_end = adjusted_start, adjusted_end

        payload = response.json()
        changes = _extract_changed_elements(payload, requested_start, requested_end)
        logger.info("ohsome: extracted %d military changes in bbox", len(changes))
        return changes

    async def _request_with_backoff(self, body: dict[str, str]) -> httpx.Response:
        """POST with simple retry/backoff for transient failures."""
        last_response: httpx.Response | None = None

        for attempt in range(_MAX_RETRIES + 1):
            response = await self._client.post(OHSOME_URL, data=body)
            if response.status_code == 200:
                return response

            if response.status_code in (429, 500, 502, 503, 504):
                last_response = response
                if attempt < _MAX_RETRIES:
                    backoff = _BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 2)
                    logger.warning(
                        "ohsome %d, retrying in %.1fs (attempt %d/%d)",
                        response.status_code,
                        backoff,
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(backoff)
                continue

            response.raise_for_status()

        if last_response is not None:
            last_response.raise_for_status()

        raise httpx.HTTPStatusError(
            "ohsome request failed after retries",
            request=httpx.Request("POST", OHSOME_URL),
            response=last_response,  # type: ignore[arg-type]
        )

    def build_dedup_hash(self, element: dict[str, Any]) -> str:
        """Compute a stable dedup key for a specific detected change."""
        key = (
            "ohsome:"
            f"{element.get('osm_id', '')}:"
            f"{element.get('change_type', '')}:"
            f"{element.get('change_timestamp', '')}"
        )
        return hashlib.sha256(key.encode()).hexdigest()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


def _extract_changed_elements(
    payload: dict[str, Any],
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    """Collapse ohsome history features into only meaningful change events."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for feature in payload.get("features", []):
        if not isinstance(feature, dict):
            continue

        properties = feature.get("properties", {})
        osm_id = str(properties.get("@osmId", ""))
        if not osm_id:
            continue

        grouped[osm_id].append(feature)

    results: list[dict[str, Any]] = []
    for osm_id, versions in grouped.items():
        versions.sort(
            key=lambda feature: _parse_timestamp(feature.get("properties", {}).get("@validFrom"))
            or window_start
        )
        change = _build_change_record(osm_id, versions, window_start, window_end)
        if change is not None:
            results.append(change)

    return results


def _build_change_record(
    osm_id: str,
    versions: list[dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any] | None:
    """Convert one feature history into a single change event, if any."""
    if not versions:
        return None

    first = versions[0]
    latest = versions[-1]
    first_props = first.get("properties", {})
    latest_props = latest.get("properties", {})

    first_from = _parse_timestamp(first_props.get("@validFrom"))
    latest_from = _parse_timestamp(latest_props.get("@validFrom"))
    latest_to = _parse_timestamp(latest_props.get("@validTo"))

    if first_from is None or latest_from is None or latest_to is None:
        return None

    tag_versions = [_extract_tags(version.get("properties", {})) for version in versions]
    tag_changed = any(current != previous for previous, current in zip(tag_versions, tag_versions[1:], strict=False))
    added_in_window = first_from > window_start
    removed_in_window = latest_to < window_end

    if not (added_in_window or removed_in_window or tag_changed):
        return None

    if removed_in_window:
        change_type = "removed"
        change_timestamp = latest_to
    elif added_in_window and len(versions) == 1:
        change_type = "added"
        change_timestamp = latest_from
    else:
        change_type = "updated"
        change_timestamp = latest_from

    tags = tag_versions[-1]
    lat, lon = _geometry_to_point(latest.get("geometry"))
    if lat is None or lon is None:
        return None

    osm_type, osm_numeric_id = _split_osm_id(osm_id)
    return {
        "osm_id": osm_numeric_id,
        "osm_ref": osm_id,
        "osm_type": osm_type,
        "latitude": lat,
        "longitude": lon,
        "tags": tags,
        "infra_type": _classify_infrastructure(tags),
        "name": tags.get("name", ""),
        "change_type": change_type,
        "change_timestamp": _format_timestamp(change_timestamp),
        "valid_from": _format_timestamp(latest_from),
        "valid_to": _format_timestamp(latest_to),
        "versions_count": len(versions),
    }


def _extract_tags(properties: dict[str, Any]) -> dict[str, str]:
    """Return only tag keys from ohsome properties, excluding metadata keys."""
    tags: dict[str, str] = {}
    for key, value in properties.items():
        if key.startswith("@") or value in (None, ""):
            continue
        tags[str(key)] = str(value)
    return tags


def _geometry_to_point(geometry: Any) -> tuple[float | None, float | None]:
    """Extract a representative point from a GeoJSON geometry."""
    if not isinstance(geometry, dict):
        return None, None

    try:
        geom = shapely_shape(geometry)
    except Exception:
        return None, None

    if geom.is_empty:
        return None, None

    point = geom.representative_point() if geom.geom_type != "Point" else geom
    return point.y, point.x


def _split_osm_id(osm_id: str) -> tuple[str, int]:
    """Split `way/123`-style ids into type and numeric id."""
    osm_type, _, raw_id = osm_id.partition("/")
    try:
        return osm_type, int(raw_id)
    except ValueError:
        return osm_type or "element", 0


def _classify_infrastructure(tags: dict[str, str]) -> str:
    """Classify a military-tagged OSM feature into a display category."""
    military = tags.get("military")
    if military:
        return f"military_{military}"
    if tags.get("landuse") == "military":
        return "military_zone"
    if tags.get("boundary") == "military":
        return "military_boundary"
    return "infrastructure"


def _adjusted_window_from_error(
    response: httpx.Response | None,
    requested_end: datetime,
    window_days: int,
) -> tuple[datetime, datetime] | None:
    """Clamp the query window if ohsome reports data lag behind wall-clock time."""
    if response is None or response.status_code != 404:
        return None

    try:
        body = response.json()
    except ValueError:
        return None

    message = str(body.get("message", ""))
    match = _TIMEFRAME_ERROR_PATTERN.search(message)
    if match is None:
        return None

    max_end = _parse_timestamp(match.group("end"))
    if max_end is None or max_end >= requested_end:
        return None

    adjusted_end = max_end
    adjusted_start = adjusted_end - timedelta(days=window_days)
    return adjusted_start, adjusted_end


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse ohsome timestamps into UTC datetimes."""
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text).astimezone(UTC)
    except ValueError:
        return None


def _format_timestamp(value: datetime) -> str:
    """Render a UTC datetime in the format expected by ohsome."""
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
