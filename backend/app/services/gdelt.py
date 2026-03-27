"""
GDELT bulk ingest client.

Two ingest streams from the same 15-minute update cycle:

1. **Event export** — structured CAMEO-coded events. Filtered for conflict codes
   (19x = fight/attack, 20x = use conventional force). Signal type: gdelt_conflict.

2. **GKG (Global Knowledge Graph)** — article-level theme/tone extraction.
   Filtered for threat themes (ARMEDCONFLICT, MILITARY, TERROR, KILL, etc.)
   with negative tone (< -2). Signal type: gdelt_gkg_threat.

GDELT is fully open — no API key required.
"""
import csv
import hashlib
import io
import logging
import zipfile
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GDELT_LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

# GKG themes that indicate conflict/threat activity
GKG_THREAT_THEMES = {
    "ARMEDCONFLICT", "MILITARY", "TERROR", "KILL",
    "CRISISLEX_T03_DEAD", "TAX_WEAPONS", "TAX_MILITARY",
    "REVOLT", "REBELLION", "INSURGENCY",
}

# Minimum negative tone to qualify as a threat signal (more negative = more threatening)
GKG_TONE_THRESHOLD = -2.0

# GKG v2 column indexes (0-based, 27 columns)
_GKG_COL_RECORD_ID = 0
_GKG_COL_DATE = 1
_GKG_COL_SOURCE = 3
_GKG_COL_DOC_ID = 4       # URL of the source article
_GKG_COL_THEMES = 7       # Semicolon-delimited theme list
_GKG_COL_V2THEMES = 8     # Enhanced themes with offsets
_GKG_COL_LOCATIONS = 9    # Semicolon-delimited location entries
_GKG_COL_V2LOCATIONS = 10 # Enhanced locations
_GKG_COL_V2TONE = 15      # Comma-delimited: tone, pos, neg, polarity, ard, srd, wordcount

# CAMEO event codes indicating conflict/violence
CONFLICT_CAMEO_CODES = {
    "190", "191", "192", "193", "194", "195", "196",
    "200", "201", "202", "203", "204",
}

# GDELT v2 export TSV column indexes (0-based, 61 columns total)
# See: http://data.gdeltproject.org/documentation/GDELT-Event_Codebook-V2.0.pdf
_COL_GLOBAL_EVENT_ID = 0
_COL_SQLDATE = 1
_COL_EVENT_CODE = 26       # EventBaseCode (CAMEO root code)
_COL_EVENT_ROOT_CODE = 27  # EventRootCode
_COL_GOLDSTEIN = 30        # GoldsteinScale (-10 to +10)
_COL_NUM_ARTICLES = 31     # NumArticles
_COL_AVG_TONE = 34         # AvgTone
_COL_ACTOR1_GEO_LAT = 39   # Actor1Geo_Lat (renamed in v2)
_COL_ACTOR1_GEO_LONG = 40  # Actor1Geo_Long
_COL_ACTION_GEO_TYPE = 50  # ActionGeo_Type
_COL_ACTION_GEO_LAT = 56   # ActionGeo_Lat
_COL_ACTION_GEO_LONG = 57  # ActionGeo_Long
_COL_SOURCEURL = 60        # SOURCEURL


class GDELTService:
    """Client for GDELT bulk event file ingestion."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)

    async def _get_lastupdate(self) -> dict[str, str]:
        """Fetch and parse lastupdate.txt into a dict of file type → URL.

        Returns:
            Dict with keys 'export', 'mentions', 'gkg' mapping to URLs.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        response = await self._client.get(GDELT_LASTUPDATE_URL)
        response.raise_for_status()

        urls: dict[str, str] = {}
        for line in response.text.strip().splitlines():
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            url = parts[2]
            if "export" in url.lower():
                urls["export"] = url
            elif "mentions" in url.lower():
                urls["mentions"] = url
            elif "gkg" in url.lower():
                urls["gkg"] = url
        return urls

    async def get_latest_export_url(self) -> str:
        """Fetch the URL of the most recent GDELT export file.

        Returns:
            Full URL of the latest .export.CSV.zip file.

        Raises:
            ValueError: If the response cannot be parsed.
        """
        urls = await self._get_lastupdate()
        if "export" not in urls:
            raise ValueError("Could not find export URL in GDELT lastupdate.txt")
        return urls["export"]

    async def get_latest_gkg_url(self) -> str:
        """Fetch the URL of the most recent GDELT GKG file.

        Returns:
            Full URL of the latest .gkg.csv.zip file.

        Raises:
            ValueError: If the response cannot be parsed.
        """
        urls = await self._get_lastupdate()
        if "gkg" not in urls:
            raise ValueError("Could not find GKG URL in GDELT lastupdate.txt")
        return urls["gkg"]

    async def fetch_latest_conflict_events(self) -> list[dict[str, Any]]:
        """Download and parse the latest GDELT export, filtering for conflict events.

        Returns:
            List of conflict-coded event dicts with standardized field names.
        """
        export_url = await self.get_latest_export_url()
        logger.info("GDELT: downloading %s", export_url)

        response = await self._client.get(export_url)
        response.raise_for_status()

        events = self._parse_export_zip(response.content)
        logger.info("GDELT: parsed %d conflict events from latest export", len(events))
        return events

    def _parse_export_zip(self, zip_bytes: bytes) -> list[dict[str, Any]]:
        """Parse a GDELT export zip file and filter for conflict events.

        Args:
            zip_bytes: Raw bytes of the .export.CSV.zip file.

        Returns:
            List of conflict event dicts.
        """
        events: list[dict[str, Any]] = []

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if not name.endswith(".CSV"):
                    continue
                with zf.open(name) as f:
                    reader = csv.reader(
                        io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                        delimiter="\t",
                    )
                    for row in reader:
                        if len(row) < 58:
                            continue

                        event_code = row[_COL_EVENT_CODE].strip()
                        if event_code not in CONFLICT_CAMEO_CODES:
                            continue

                        # Prefer ActionGeo coordinates, fall back to Actor1Geo
                        lat, lon = _extract_coords(row)
                        if lat is None or lon is None:
                            continue

                        events.append({
                            "GlobalEventID": row[_COL_GLOBAL_EVENT_ID].strip(),
                            "SQLDATE": row[_COL_SQLDATE].strip(),
                            "EventCode": event_code,
                            "GoldsteinScale": _safe_float(row[_COL_GOLDSTEIN]),
                            "NumArticles": _safe_int(row[_COL_NUM_ARTICLES]),
                            "AvgTone": _safe_float(row[_COL_AVG_TONE]),
                            "latitude": lat,
                            "longitude": lon,
                            "SOURCEURL": row[_COL_SOURCEURL].strip() if len(row) > _COL_SOURCEURL else "",
                        })

        return events

    async def fetch_latest_gkg_threats(self) -> list[dict[str, Any]]:
        """Download and parse the latest GKG file, filtering for threat signals.

        Selects records that match threat themes AND have negative tone (< -2).
        Extracts the first geolocated location from each record.

        Returns:
            List of threat event dicts with lat/lon, tone, themes, and source URL.
        """
        gkg_url = await self.get_latest_gkg_url()
        logger.info("GDELT GKG: downloading %s", gkg_url)

        response = await self._client.get(gkg_url)
        response.raise_for_status()

        events = self._parse_gkg_zip(response.content)
        logger.info("GDELT GKG: parsed %d threat records from latest file", len(events))
        return events

    def _parse_gkg_zip(self, zip_bytes: bytes) -> list[dict[str, Any]]:
        """Parse a GKG zip file and filter for negative-tone threat records.

        Args:
            zip_bytes: Raw bytes of the .gkg.csv.zip file.

        Returns:
            List of threat event dicts.
        """
        events: list[dict[str, Any]] = []

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                with zf.open(name) as f:
                    reader = csv.reader(
                        io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                        delimiter="\t",
                    )
                    for row in reader:
                        if len(row) < 16:
                            continue

                        # Extract and check themes
                        themes = set(row[_GKG_COL_THEMES].split(";")) if row[_GKG_COL_THEMES] else set()
                        if len(row) > _GKG_COL_V2THEMES and row[_GKG_COL_V2THEMES]:
                            for t in row[_GKG_COL_V2THEMES].split(";"):
                                themes.add(t.split(",")[0] if "," in t else t)

                        matched_themes = themes & GKG_THREAT_THEMES
                        if not matched_themes:
                            continue

                        # Check tone threshold
                        tone = _parse_gkg_tone(row[_GKG_COL_V2TONE])
                        if tone is None or tone >= GKG_TONE_THRESHOLD:
                            continue

                        # Extract first valid location
                        lat, lon = _parse_gkg_location(row)
                        if lat is None or lon is None:
                            continue

                        events.append({
                            "GKGRecordID": row[_GKG_COL_RECORD_ID].strip(),
                            "DATE": row[_GKG_COL_DATE].strip(),
                            "themes": sorted(matched_themes),
                            "tone": tone,
                            "source": row[_GKG_COL_SOURCE].strip(),
                            "url": row[_GKG_COL_DOC_ID].strip(),
                            "latitude": lat,
                            "longitude": lon,
                        })

        return events

    def build_gkg_dedup_hash(self, event: dict[str, Any]) -> str:
        """Compute deduplication hash for a GKG threat record.

        Uses GKGRecordID as the dedup key.

        Args:
            event: Parsed GKG event dict.

        Returns:
            SHA-256 hex string.
        """
        key = f"gdelt_gkg:{event['GKGRecordID']}"
        return hashlib.sha256(key.encode()).hexdigest()

    def build_dedup_hash(self, event: dict[str, Any]) -> str:
        """Compute deduplication hash for a GDELT event.

        Uses GlobalEventID as the dedup key — it is globally unique per event.

        Args:
            event: Parsed GDELT event dict.

        Returns:
            SHA-256 hex string.
        """
        key = f"gdelt:{event['GlobalEventID']}:{event['SQLDATE']}"
        return hashlib.sha256(key.encode()).hexdigest()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


def _extract_coords(row: list[str]) -> tuple[float | None, float | None]:
    """Extract lat/lon from a GDELT row, preferring ActionGeo over Actor1Geo.

    Args:
        row: TSV row as list of strings.

    Returns:
        (latitude, longitude) or (None, None) if no valid coordinates found.
    """
    # Try ActionGeo first
    lat = _safe_float(row[_COL_ACTION_GEO_LAT])
    lon = _safe_float(row[_COL_ACTION_GEO_LONG])
    if lat is not None and lon is not None and (lat != 0.0 or lon != 0.0):
        return lat, lon

    # Fall back to Actor1Geo
    lat = _safe_float(row[_COL_ACTOR1_GEO_LAT])
    lon = _safe_float(row[_COL_ACTOR1_GEO_LONG])
    if lat is not None and lon is not None and (lat != 0.0 or lon != 0.0):
        return lat, lon

    return None, None


def _safe_float(value: str) -> float | None:
    """Parse a string to float, returning None on failure."""
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return None


def _safe_int(value: str) -> int | None:
    """Parse a string to int, returning None on failure."""
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return None


def _parse_gkg_tone(tone_str: str) -> float | None:
    """Parse the V2Tone field (first value is overall tone).

    Args:
        tone_str: Comma-delimited tone string from GKG.

    Returns:
        Overall tone float, or None if unparseable.
    """
    if not tone_str:
        return None
    try:
        return float(tone_str.split(",")[0].strip())
    except (ValueError, IndexError):
        return None


def _parse_gkg_location(row: list[str]) -> tuple[float | None, float | None]:
    """Extract the first valid lat/lon from a GKG record.

    GKG locations are semicolon-delimited, each entry is hash-delimited:
    type#name#countrycode#adm1#adm2#lat#lon#featureid#...

    Prefers V2Locations (col 10), falls back to Locations (col 9).

    Args:
        row: GKG TSV row.

    Returns:
        (latitude, longitude) or (None, None).
    """
    for col_idx in (_GKG_COL_V2LOCATIONS, _GKG_COL_LOCATIONS):
        if col_idx >= len(row) or not row[col_idx]:
            continue
        for loc_entry in row[col_idx].split(";"):
            parts = loc_entry.split("#")
            if len(parts) < 7:
                continue
            lat = _safe_float(parts[5])
            lon = _safe_float(parts[6])
            if lat is not None and lon is not None and (lat != 0.0 or lon != 0.0):
                return lat, lon

    return None, None
