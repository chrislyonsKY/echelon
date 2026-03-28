"""
OpenSky Network REST API service client.

Fetches live aircraft state vectors and filters for likely military traffic
using callsign patterns and ICAO24 hex address ranges.

No API key required for basic access. Anonymous rate limit: ~10 req / 10s.
See: https://opensky-network.org/api
"""
import hashlib
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENSKY_BASE_URL = "https://opensky-network.org/api"

# ── Military callsign prefixes ───────────────────────────────────────────────
# US military airlift / tanker / transport
_US_MILITARY_PREFIXES = (
    "RCH",      # C-17 Globemaster (REACH shorthand)
    "REACH",    # C-17 / C-5 airlift
    "DUKE",     # C-130 tactical airlift
    "EVAC",     # Aeromedical evacuation
    "HOMER",    # P-8 Poseidon maritime patrol
    "IRON",     # B-52 bomber
    "JAKE",     # E-6B Mercury (TACAMO)
    "KING",     # HC-130 tanker / SAR
    "NATO",     # NATO AWACS / alliance flights
    "ALLIED",   # Allied coalition flights
)

# Surveillance / ISR callsign substrings (can appear anywhere in callsign)
_SURVEILLANCE_SUBSTRINGS = (
    "FORTE",    # RQ-4 Global Hawk
    "HOMER",    # P-8 Poseidon
    "LAGR",     # RC-135 Rivet Joint
)

# ── Military ICAO24 hex ranges ───────────────────────────────────────────────
# Each tuple is (range_start, range_end) inclusive, as integers.
# US military aircraft are assigned ICAO24 addresses in AE0000-AE7FFF.
# Additional ranges cover known NATO / allied military blocks.
_MILITARY_ICAO_RANGES: list[tuple[int, int]] = [
    (0xAE0000, 0xAE7FFF),  # US military (primary block)
    (0xADF7C0, 0xADFFFF),  # US military (secondary block)
    (0x3F0000, 0x3FFFFF),  # France military
    (0x43C000, 0x43CFFF),  # UK military
    (0x3E8000, 0x3EBFFF),  # Germany military
    (0x500000, 0x5003FF),  # Israel military (partial)
]

_MAX_RETRIES = 2
_REQUEST_TIMEOUT = 30.0


class OpenSkyService:
    """Client for the OpenSky Network REST API.

    Fetches aircraft state vectors and filters for likely military traffic
    based on callsign patterns and ICAO24 hex address ranges.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=OPENSKY_BASE_URL,
            timeout=_REQUEST_TIMEOUT,
        )

    async def fetch_military_aircraft(
        self,
        bbox: tuple[float, float, float, float],
        min_velocity: float = 50.0,
    ) -> list[dict[str, Any]]:
        """Fetch aircraft state vectors and filter for likely military traffic.

        Queries the OpenSky /states/all endpoint for the given bounding box,
        then filters results for airborne aircraft matching military callsign
        patterns, ICAO24 hex ranges, or minimum velocity thresholds.

        Args:
            bbox: (west, south, east, north) in WGS84 degrees.
            min_velocity: Minimum ground velocity in m/s to include.
                Filters out slow/stationary contacts. Default 50 m/s (~97 kts).

        Returns:
            List of aircraft dicts with icao24, callsign, position, velocity,
            heading, altitude, and origin_country fields.

        Raises:
            httpx.HTTPStatusError: On non-2xx response after retries.
        """
        west, south, east, north = bbox
        params = {
            "lamin": south,
            "lamax": north,
            "lomin": west,
            "lomax": east,
        }

        response = await self._request_with_retry("/states/all", params)
        body = response.json()

        states = body.get("states") or []
        timestamp = body.get("time", 0)

        aircraft: list[dict[str, Any]] = []
        for state in states:
            parsed = _parse_state_vector(state, timestamp)
            if parsed is None:
                continue

            # Filter: must be airborne
            if parsed["on_ground"]:
                continue

            # Filter: minimum velocity
            if parsed["velocity"] is not None and parsed["velocity"] < min_velocity:
                continue

            # Filter: must match military indicators
            if not _is_likely_military(parsed):
                continue

            aircraft.append(parsed)

        logger.info(
            "OpenSky: bbox (%.1f,%.1f,%.1f,%.1f) — %d total states, %d military matches",
            west, south, east, north, len(states), len(aircraft),
        )
        return aircraft

    async def _request_with_retry(
        self,
        path: str,
        params: dict[str, Any],
    ) -> httpx.Response:
        """Execute a GET request with simple retry on transient errors.

        Args:
            path: API path (appended to base URL).
            params: Query parameters.

        Returns:
            Successful httpx.Response.

        Raises:
            httpx.HTTPStatusError: After retries exhausted.
        """
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._client.get(path, params=params)
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.ReadTimeout) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "OpenSky request failed (attempt %d/%d): %s",
                        attempt + 1, _MAX_RETRIES, exc,
                    )
                    # No async sleep here — caller handles inter-query rate limiting

        raise last_exc  # type: ignore[misc]

    def build_dedup_hash(self, aircraft: dict[str, Any]) -> str:
        """Compute deduplication hash for an aircraft state observation.

        Uses icao24 + timestamp so the same aircraft at the same time is
        deduplicated, but new positions at different times are kept.

        Args:
            aircraft: Parsed aircraft dict with 'icao24' and 'timestamp' keys.

        Returns:
            SHA-256 hex string.
        """
        key = f"opensky:{aircraft['icao24']}:{aircraft['timestamp']}"
        return hashlib.sha256(key.encode()).hexdigest()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


def _parse_state_vector(
    state: list[Any],
    api_timestamp: int,
) -> dict[str, Any] | None:
    """Parse an OpenSky state vector array into a named dict.

    OpenSky returns state vectors as positional arrays with 17 fields:
    [0]  icao24           [1]  callsign        [2]  origin_country
    [3]  time_position    [4]  last_contact     [5]  longitude
    [6]  latitude         [7]  baro_altitude    [8]  on_ground
    [9]  velocity         [10] true_track       [11] vertical_rate
    [12] sensors          [13] geo_altitude     [14] squawk
    [15] spi              [16] position_source

    Args:
        state: Raw state vector list from OpenSky API.
        api_timestamp: Unix timestamp from the API response.

    Returns:
        Named dict with relevant fields, or None if coordinates are missing.
    """
    if len(state) < 17:
        return None

    icao24 = state[0]
    longitude = state[5]
    latitude = state[6]

    # Coordinates are required for geospatial indexing
    if longitude is None or latitude is None:
        return None

    callsign = (state[1] or "").strip()

    return {
        "icao24": icao24,
        "callsign": callsign,
        "origin_country": state[2] or "",
        "longitude": float(longitude),
        "latitude": float(latitude),
        "baro_altitude": state[7],
        "on_ground": bool(state[8]),
        "velocity": state[9],
        "heading": state[10],
        "vertical_rate": state[11],
        "geo_altitude": state[13],
        "squawk": state[14],
        "timestamp": api_timestamp,
    }


def _is_likely_military(aircraft: dict[str, Any]) -> bool:
    """Determine if an aircraft is likely military based on available indicators.

    Checks (in order):
    1. Callsign matches known military prefixes
    2. Callsign contains surveillance/ISR substrings
    3. ICAO24 hex falls within a known military allocation block

    Args:
        aircraft: Parsed aircraft dict.

    Returns:
        True if the aircraft matches any military indicator.
    """
    callsign = aircraft["callsign"].upper()
    icao24 = aircraft["icao24"]

    # Check military callsign prefixes
    if callsign and any(callsign.startswith(prefix) for prefix in _US_MILITARY_PREFIXES):
        return True

    # Check surveillance/ISR callsign substrings
    if callsign and any(substr in callsign for substr in _SURVEILLANCE_SUBSTRINGS):
        return True

    # Check ICAO24 hex against military allocation ranges
    try:
        icao_int = int(icao24, 16)
        for range_start, range_end in _MILITARY_ICAO_RANGES:
            if range_start <= icao_int <= range_end:
                return True
    except (ValueError, TypeError):
        pass

    return False
