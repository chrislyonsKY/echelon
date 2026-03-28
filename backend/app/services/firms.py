"""
NASA FIRMS (Fire Information for Resource Management System) API client.

Fetches active fire / thermal anomaly detections from the VIIRS SNPP sensor
via the FIRMS CSV API. Each row represents a single thermal anomaly detection
with coordinates, fire radiative power, and confidence level.

Requires a FIRMS MAP_KEY (free registration at https://firms.modaps.eosdis.nasa.gov/).
"""
import csv
import hashlib
import io
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# Conflict zone bounding boxes: (name, (west, south, east, north))
CONFLICT_ZONES: list[tuple[str, tuple[float, float, float, float]]] = [
    ("Ukraine", (22.0, 44.0, 40.5, 52.5)),
    ("Eastern Mediterranean", (34.0, 29.0, 37.0, 34.0)),
    ("Yemen/Horn of Africa", (41.0, 10.0, 54.0, 19.0)),
    ("Persian Gulf", (47.0, 23.0, 57.0, 30.5)),
    ("South China Sea", (105.0, 5.0, 122.0, 22.0)),
    ("Korean Peninsula", (124.0, 33.0, 132.0, 43.0)),
    ("Taiwan Strait", (117.0, 21.5, 123.0, 26.0)),
]

# Confidence values that qualify as valid detections
VALID_CONFIDENCE = {"nominal", "n", "high", "h"}


class FIRMSService:
    """Client for NASA FIRMS thermal anomaly data."""

    def __init__(self, map_key: str) -> None:
        self._map_key = map_key
        self._client = httpx.AsyncClient(timeout=60.0)

    async def fetch_thermal_anomalies(
        self,
        bboxes: list[tuple[str, tuple[float, float, float, float]]],
        days: int = 2,
    ) -> list[dict[str, Any]]:
        """Fetch thermal anomaly detections for multiple bounding boxes.

        Args:
            bboxes: List of (name, (west, south, east, north)) tuples.
            days: Number of days of data to request (1-10).

        Returns:
            List of normalized anomaly dicts, filtered for confidence
            and minimum FRP.
        """
        all_anomalies: list[dict[str, Any]] = []

        for zone_name, (west, south, east, north) in bboxes:
            bbox_str = f"{west},{south},{east},{north}"
            url = f"{FIRMS_BASE_URL}/{self._map_key}/VIIRS_SNPP_NRT/{bbox_str}/{days}"

            try:
                response = await self._client.get(url)
                response.raise_for_status()

                anomalies = self._parse_csv(response.text, zone_name)
                all_anomalies.extend(anomalies)
                logger.info(
                    "FIRMS: %d anomalies from %s", len(anomalies), zone_name,
                )
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "FIRMS: HTTP %d for %s — skipping",
                    exc.response.status_code, zone_name,
                )
            except Exception:
                logger.exception("FIRMS: failed to fetch %s", zone_name)

        logger.info("FIRMS: %d total anomalies across %d zones", len(all_anomalies), len(bboxes))
        return all_anomalies

    def _parse_csv(self, csv_text: str, zone_name: str) -> list[dict[str, Any]]:
        """Parse FIRMS CSV response and apply confidence/FRP filters.

        Args:
            csv_text: Raw CSV response body.
            zone_name: Name of the conflict zone (for logging).

        Returns:
            List of filtered anomaly dicts.
        """
        anomalies: list[dict[str, Any]] = []
        reader = csv.DictReader(io.StringIO(csv_text))

        for row in reader:
            # Filter by confidence level
            confidence = row.get("confidence", "").strip().lower()
            if confidence not in VALID_CONFIDENCE:
                continue

            # Filter by fire radiative power
            frp = _safe_float(row.get("frp", ""))
            if frp is None or frp <= 10.0:
                continue

            lat = _safe_float(row.get("latitude", ""))
            lon = _safe_float(row.get("longitude", ""))
            if lat is None or lon is None:
                continue

            anomalies.append({
                "latitude": lat,
                "longitude": lon,
                "brightness": _safe_float(row.get("brightness", "")),
                "frp": frp,
                "confidence": row.get("confidence", "").strip(),
                "acq_date": row.get("acq_date", "").strip(),
                "acq_time": row.get("acq_time", "").strip(),
                "satellite": row.get("satellite", "").strip(),
                "daynight": row.get("daynight", "").strip(),
            })

        return anomalies

    def build_dedup_hash(self, anomaly: dict[str, Any]) -> str:
        """Compute deduplication hash for a thermal anomaly detection.

        Uses lat, lon, date, and time as the composite key.

        Args:
            anomaly: Parsed anomaly dict.

        Returns:
            SHA-256 hex string.
        """
        key = (
            f"firms:{anomaly['latitude']}:{anomaly['longitude']}"
            f":{anomaly['acq_date']}:{anomaly['acq_time']}"
        )
        return hashlib.sha256(key.encode()).hexdigest()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


def _safe_float(value: str) -> float | None:
    """Parse a string to float, returning None on failure."""
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return None
