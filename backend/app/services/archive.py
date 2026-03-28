"""
Evidence preservation service — automated archiving for chain of custody.

Pushes URLs to the Wayback Machine Save Page Now API and stores
timestamped archive URLs. No API key required.

Usage:
  archiver = ArchiveService()
  result = await archiver.archive_url("https://example.com/evidence")
  # result.archive_url = "https://web.archive.org/web/20260328.../..."
"""
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

WAYBACK_SAVE_URL = "https://web.archive.org/save/"
WAYBACK_AVAILABILITY_URL = "https://archive.org/wayback/available"


@dataclass
class ArchiveResult:
    """Result of an archive operation."""
    url: str
    archive_url: str | None
    archived_at: datetime
    content_hash: str  # SHA-256 of the URL for dedup
    status: str  # "saved" | "already_archived" | "failed"
    error: str | None = None


class ArchiveService:
    """Preserve evidence URLs via the Internet Archive Wayback Machine."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "Echelon-GEOINT-Archiver/1.0 (open-source OSINT platform)"},
        )

    async def archive_url(self, url: str) -> ArchiveResult:
        """Submit a URL to Wayback Machine's Save Page Now.

        Returns the archived URL if successful. Does not block on
        full capture — the Wayback Machine processes asynchronously.
        """
        content_hash = hashlib.sha256(url.encode()).hexdigest()
        now = datetime.now(timezone.utc)

        # Check if already archived recently
        existing = await self._check_existing(url)
        if existing:
            return ArchiveResult(
                url=url,
                archive_url=existing,
                archived_at=now,
                content_hash=content_hash,
                status="already_archived",
            )

        # Submit to Wayback Machine
        try:
            resp = await self._client.post(
                WAYBACK_SAVE_URL,
                data={"url": url, "capture_all": "on"},
                headers={"Accept": "application/json"},
            )

            if resp.status_code in (200, 302):
                # Extract archive URL from redirect or response
                archive_url = resp.headers.get("Content-Location") or resp.headers.get("Location")
                if not archive_url and "url" in resp.text:
                    # Try to parse from response body
                    archive_url = f"https://web.archive.org/web/{now.strftime('%Y%m%d%H%M%S')}/{url}"

                logger.info("Archived %s -> %s", url, archive_url)
                return ArchiveResult(
                    url=url,
                    archive_url=archive_url,
                    archived_at=now,
                    content_hash=content_hash,
                    status="saved",
                )
            else:
                logger.warning("Archive failed for %s: HTTP %d", url, resp.status_code)
                return ArchiveResult(
                    url=url,
                    archive_url=None,
                    archived_at=now,
                    content_hash=content_hash,
                    status="failed",
                    error=f"HTTP {resp.status_code}",
                )

        except Exception as exc:
            logger.warning("Archive request failed for %s: %s", url, exc)
            return ArchiveResult(
                url=url,
                archive_url=None,
                archived_at=now,
                content_hash=content_hash,
                status="failed",
                error=str(exc)[:100],
            )

    async def _check_existing(self, url: str) -> str | None:
        """Check if a URL is already in the Wayback Machine."""
        try:
            resp = await self._client.get(
                WAYBACK_AVAILABILITY_URL,
                params={"url": url},
            )
            if resp.status_code == 200:
                data = resp.json()
                snapshot = data.get("archived_snapshots", {}).get("closest")
                if snapshot and snapshot.get("available"):
                    return snapshot["url"]
        except Exception:
            pass
        return None

    async def close(self) -> None:
        await self._client.aclose()
