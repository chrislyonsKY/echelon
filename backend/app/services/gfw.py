"""
GlobalFishingWatch API service client.

Fetches vessel anomaly events: AIS gaps, loitering, encounters, port visits.
Free for non-commercial / open-source use. ~24h data lag due to processing.
See: https://globalfishingwatch.org/our-apis/documentation
"""
import asyncio
import hashlib
import logging
import random
from datetime import date
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GFW_BASE_URL = "https://gateway.api.globalfishingwatch.org/v3"

# Dataset IDs per event type
GFW_DATASETS: dict[str, str] = {
    "gap":        "public-global-gaps-events:latest",
    "loitering":  "public-global-loitering-events:latest",
    "encounter":  "public-global-encounters-events:latest",
    "port_visit": "public-global-port-visits-events:latest",
}

# Map GFW event types to internal signal types
GFW_EVENT_TYPE_MAP: dict[str, str] = {
    "gap":        "gfw_ais_gap",
    "loitering":  "gfw_loitering",
    "encounter":  "gfw_encounter",
    "port_visit": "gfw_port_visit",
}

# Only ingest these event types (gap + loitering are scored, others are context)
INGEST_EVENT_TYPES = ("gap", "loitering")

_MAX_RETRIES = 3
_BASE_BACKOFF = 2.0
_PAGE_SIZE = 100
_MAX_EVENTS_PER_DATASET = 2000  # Cap to prevent runaway pagination


class GFWService:
    """Client for the GlobalFishingWatch Events API."""

    def __init__(self) -> None:
        self._token = settings.gfw_api_token
        self._client = httpx.AsyncClient(
            base_url=GFW_BASE_URL,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=120.0,
        )

    async def fetch_events(
        self,
        date_from: date,
        date_to: date,
        event_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch vessel anomaly events for a date range.

        Queries each event type dataset separately and merges results.
        GFW API is serialized (1 concurrent report) — requests run sequentially.

        Args:
            date_from: Inclusive start date.
            date_to: Inclusive end date.
            event_types: Event types to fetch. Defaults to INGEST_EVENT_TYPES.

        Returns:
            List of GFW event dicts with position, type, and vessel info.

        Raises:
            httpx.HTTPStatusError: On non-2xx response after retries exhausted.
        """
        types = event_types or list(INGEST_EVENT_TYPES)
        all_events: list[dict[str, Any]] = []

        for event_type in types:
            dataset = GFW_DATASETS.get(event_type)
            if not dataset:
                logger.warning("GFW: unknown event type '%s', skipping", event_type)
                continue

            events = await self._fetch_dataset(dataset, date_from, date_to)
            # Tag with our event type since the API response type may differ
            for e in events:
                e["_echelon_event_type"] = event_type
            all_events.extend(events)

            logger.info("GFW %s: fetched %d events", event_type, len(events))
            # GFW rate limit: serialize between datasets
            await asyncio.sleep(1.0)

        return all_events

    async def _fetch_dataset(
        self,
        dataset: str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Fetch all events from a single GFW dataset with pagination.

        Args:
            dataset: GFW dataset ID.
            date_from: Start date.
            date_to: End date.

        Returns:
            List of event dicts.
        """
        all_entries: list[dict[str, Any]] = []
        offset = 0

        while True:
            params = {
                "datasets[0]": dataset,
                "start-date": date_from.isoformat(),
                "end-date": date_to.isoformat(),
                "limit": _PAGE_SIZE,
                "offset": offset,
            }

            response = await self._request_with_backoff("/events", params)
            body = response.json()

            entries = body.get("entries", [])
            all_entries.extend(entries)

            total = body.get("total", 0)
            next_offset = body.get("nextOffset")

            if next_offset is None or offset + len(entries) >= total:
                break

            if len(all_entries) >= _MAX_EVENTS_PER_DATASET:
                logger.info("GFW: hit %d event cap for dataset, stopping pagination", _MAX_EVENTS_PER_DATASET)
                break

            offset = next_offset
            await asyncio.sleep(0.5)

        return all_entries

    async def _request_with_backoff(
        self,
        path: str,
        params: dict[str, Any],
    ) -> httpx.Response:
        """Execute a GET request with exponential backoff on 429/503.

        Args:
            path: API path (appended to base URL).
            params: Query parameters.

        Returns:
            Successful httpx.Response.

        Raises:
            httpx.HTTPStatusError: After retries exhausted.
        """
        last_response: httpx.Response | None = None

        for attempt in range(_MAX_RETRIES + 1):
            response = await self._client.get(path, params=params)

            if response.status_code not in (429, 503):
                response.raise_for_status()
                return response

            last_response = response

            # Respect Retry-After header if present
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                backoff = float(retry_after)
            else:
                backoff = _BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 1)

            if attempt < _MAX_RETRIES:
                logger.warning(
                    "GFW %d, retrying in %.1fs (attempt %d/%d)",
                    response.status_code, backoff, attempt + 1, _MAX_RETRIES,
                )
                await asyncio.sleep(backoff)

        if last_response is not None:
            last_response.raise_for_status()
        raise httpx.HTTPStatusError(
            "GFW request failed after retries",
            request=httpx.Request("GET", f"{GFW_BASE_URL}{path}"),
            response=last_response,  # type: ignore[arg-type]
        )

    def build_dedup_hash(self, event: dict[str, Any]) -> str:
        """Compute deduplication hash for a GFW event.

        GFW event IDs are globally unique — use directly as dedup key.

        Args:
            event: GFW event dict with 'id' key.

        Returns:
            SHA-256 hex string.
        """
        key = f"gfw:{event['id']}"
        return hashlib.sha256(key.encode()).hexdigest()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
