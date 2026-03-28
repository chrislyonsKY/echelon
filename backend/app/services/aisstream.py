"""
AISStream.io WebSocket service client.

Provides real-time AIS vessel tracking data via WebSocket streaming.
Connects to the AISStream WebSocket API, subscribes to position reports
within specified bounding boxes, collects messages for a fixed duration,
and returns normalized vessel position records.

See: https://aisstream.io/documentation
"""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

import websockets

from app.config import settings

logger = logging.getLogger(__name__)

AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"


class AISStreamService:
    """Client for the AISStream.io real-time AIS WebSocket API."""

    def __init__(self) -> None:
        self._api_key: str = settings.aisstream_api_key

    async def collect_positions(
        self,
        bboxes: list[tuple[float, float, float, float]],
        duration_seconds: int = 60,
    ) -> list[dict[str, Any]]:
        """Connect to AISStream and collect vessel position reports.

        Opens a WebSocket connection, subscribes to PositionReport messages
        within the given bounding boxes, and collects data for the specified
        duration before disconnecting.

        Args:
            bboxes: List of (west, south, east, north) bounding boxes in WGS84.
                    Converted to AISStream format [[south_lat, west_lon], [north_lat, east_lon]].
            duration_seconds: How long to listen for messages (default 60s).

        Returns:
            List of normalized position dicts with keys: mmsi, ship_name,
            latitude, longitude, speed, course, heading, timestamp.
            Returns empty list on any error.
        """
        if not self._api_key:
            logger.warning("AISStream: no API key configured, skipping collection")
            return []

        # Convert (west, south, east, north) to AISStream [[south_lat, west_lon], [north_lat, east_lon]]
        ais_bboxes = [
            [[south, west], [north, east]]
            for west, south, east, north in bboxes
        ]

        subscription = {
            "APIKey": self._api_key,
            "BoundingBoxes": ais_bboxes,
            "FilterMessageTypes": ["PositionReport"],
        }

        positions: list[dict[str, Any]] = []

        try:
            async with websockets.connect(AISSTREAM_WS_URL) as ws:
                # Must subscribe within 3 seconds of connecting
                await ws.send(json.dumps(subscription))
                logger.info(
                    "AISStream: subscribed with %d bounding boxes, listening for %ds",
                    len(ais_bboxes),
                    duration_seconds,
                )

                deadline = asyncio.get_event_loop().time() + duration_seconds

                while asyncio.get_event_loop().time() < deadline:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        break

                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    except asyncio.TimeoutError:
                        break

                    position = self._parse_position_report(raw)
                    if position is not None:
                        positions.append(position)

            logger.info("AISStream: collected %d position reports", len(positions))

        except Exception:
            logger.warning("AISStream: connection error during collection", exc_info=True)

        return positions

    def _parse_position_report(self, raw: str | bytes) -> dict[str, Any] | None:
        """Parse a raw WebSocket message into a normalized position dict.

        Args:
            raw: Raw JSON message from the WebSocket.

        Returns:
            Normalized position dict, or None if the message is not a valid
            PositionReport.
        """
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

        msg_type = msg.get("MessageType")
        if msg_type != "PositionReport":
            return None

        message = msg.get("Message", {}).get("PositionReport", {})
        metadata = msg.get("MetaData", {})

        mmsi = metadata.get("MMSI")
        if mmsi is None:
            return None

        latitude = message.get("Latitude") or metadata.get("latitude")
        longitude = message.get("Longitude") or metadata.get("longitude")
        if latitude is None or longitude is None:
            return None

        # Parse timestamp from metadata
        time_str = metadata.get("time_utc", "")
        try:
            timestamp = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.now(timezone.utc)

        return {
            "mmsi": int(mmsi),
            "ship_name": (metadata.get("ShipName") or "").strip(),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "speed": float(message.get("Sog", 0.0)),
            "course": float(message.get("Cog", 0.0)),
            "heading": float(message.get("TrueHeading", 0.0)),
            "timestamp": timestamp,
        }

    def build_dedup_hash(self, position: dict[str, Any]) -> str:
        """Compute deduplication hash for an AIS position report.

        Uses MMSI and timestamp truncated to the minute as the dedup key.
        This avoids duplicate entries when the same vessel sends multiple
        position reports within the same minute.

        Args:
            position: Normalized position dict.

        Returns:
            SHA-256 hex string.
        """
        ts = position["timestamp"]
        if isinstance(ts, datetime):
            ts_key = ts.strftime("%Y%m%d%H%M")
        else:
            ts_key = str(ts)[:12]

        key = f"ais:{position['mmsi']}:{ts_key}"
        return hashlib.sha256(key.encode()).hexdigest()
