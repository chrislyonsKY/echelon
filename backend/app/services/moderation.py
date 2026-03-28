"""
Pluggable moderation service interface.

If no moderation backend is configured, evidence is stored with
review_status="unreviewed" and no automatic block. Model-flagged
content remains reviewable by humans — never permanently discarded.

Core policy: graphic classification determines presentation only.
It never affects convergence scoring or event validity.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModerationResult:
    """Result of moderation analysis on evidence content."""
    graphic_flag: bool = False
    graphic_confidence: float = 0.0
    graphic_reason: str = ""
    review_status: str = "unreviewed"
    # "unreviewed" | "auto_flagged" | "human_approved" | "human_rejected" | "restricted"
    restricted: bool = False  # Perpetrator/terrorist content — never publicly amplified
    restricted_reason: str = ""
    moderation_payload: dict[str, Any] = field(default_factory=dict)


# ── Perpetrator/Terrorist Content Policy ──────────────────────────────────────
#
# Perpetrator-produced or terrorist-promoted video is NEVER publicly amplified.
# It is either:
#   1. Blocked entirely (review_status="human_rejected"), or
#   2. Retained as restricted analyst evidence (review_status="restricted")
#      with: content hash, warnings, provenance tagging, mandatory human review.
#
# Restricted content:
#   - Is never shown in public feeds, search results, or map overlays
#   - Is only visible to authenticated analysts with explicit opt-in
#   - Carries a non-dismissable warning banner
#   - Retains full provenance chain for investigative use
#   - Is hashed for cross-referencing (e.g., with the GIFCT hash-sharing database)
#
# This policy cannot be overridden by configuration — it is hardcoded.
# ──────────────────────────────────────────────────────────────────────────────


class ModerationService(ABC):
    """Abstract interface for content moderation.

    Implementations may use:
    - OpenAI moderation API
    - Google Cloud Vision SafeSearch
    - AWS Rekognition content moderation
    - Self-hosted models (e.g., NudeNet, NSFW detector)
    - Manual/no-op for development
    """

    @abstractmethod
    async def moderate_video(
        self,
        url: str,
        title: str | None = None,
        description: str | None = None,
        thumbnail_url: str | None = None,
    ) -> ModerationResult:
        """Analyze video content for graphic/disturbing material.

        Should extract keyframes, run classification on keyframes
        plus title/description text, and return a video-level result.
        """
        ...

    @abstractmethod
    async def moderate_image(
        self,
        url: str,
        caption: str | None = None,
    ) -> ModerationResult:
        """Analyze a single image for graphic content."""
        ...


class NoOpModerationService(ModerationService):
    """Default moderation when no backend is configured.

    All content passes through as "unreviewed" — available for
    human review but not auto-blocked or auto-approved.
    """

    async def moderate_video(
        self,
        url: str,
        title: str | None = None,
        description: str | None = None,
        thumbnail_url: str | None = None,
    ) -> ModerationResult:
        logger.debug("NoOp moderation: video stored as unreviewed (%s)", url)
        return ModerationResult(
            graphic_flag=False,
            graphic_confidence=0.0,
            graphic_reason="",
            review_status="unreviewed",
            moderation_payload={"service": "noop", "note": "No moderation backend configured"},
        )

    async def moderate_image(
        self,
        url: str,
        caption: str | None = None,
    ) -> ModerationResult:
        logger.debug("NoOp moderation: image stored as unreviewed (%s)", url)
        return ModerationResult(
            graphic_flag=False,
            graphic_confidence=0.0,
            graphic_reason="",
            review_status="unreviewed",
            moderation_payload={"service": "noop"},
        )


def get_moderation_service() -> ModerationService:
    """Factory — returns the configured moderation backend.

    Currently returns NoOp. To enable real moderation:
    1. Implement a concrete ModerationService subclass
    2. Add config to app/config.py (e.g., MODERATION_BACKEND=openai)
    3. Return the appropriate implementation here
    """
    return NoOpModerationService()
