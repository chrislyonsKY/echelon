"""
Evidence router — attach and manage evidence items (video, images) on signal events.

Video is evidence attached to an event. Provenance determines trust.
Graphic classification determines presentation. Evidence never affects
convergence scoring.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.moderation import get_moderation_service

logger = logging.getLogger(__name__)
router = APIRouter()


class EvidenceCreate(BaseModel):
    """Request body for attaching evidence to a signal event."""
    signal_id: str
    type: str = "video"  # "video" | "image" | "document"
    url: str
    platform: str | None = None
    thumbnail_url: str | None = None
    title: str | None = None
    description: str | None = None
    author: str | None = None
    language: str | None = None
    published_at: str | None = None
    provenance_family: str | None = None  # "official", "ugc", "aggregator", "context_only"
    confirmation_policy: str | None = None
    geolocation_status: str = "unverified"
    time_verification_status: str = "unverified"


class EvidenceReview(BaseModel):
    """Request body for updating evidence review status."""
    review_status: str  # "human_approved" | "human_rejected"
    graphic_flag: bool | None = None
    graphic_reason: str | None = None


@router.get("/for/{signal_id}")
async def get_evidence_for_signal(
    signal_id: str,
    include_restricted: bool = Query(default=False, description="Include restricted content (analyst only)"),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return evidence items attached to a signal event.

    Restricted content (perpetrator/terrorist-produced) is excluded by default.
    Pass include_restricted=true for authenticated analyst access only.
    """
    restriction_clause = "" if include_restricted else "AND restricted = false"

    result = await session.execute(
        text(f"""
            SELECT id, signal_id, type, url, platform, thumbnail_url, title,
                   description, author, language, published_at, attached_at,
                   provenance_family, confirmation_policy,
                   geolocation_status, time_verification_status,
                   graphic_flag, graphic_confidence, graphic_reason,
                   review_status, restricted, restricted_reason, content_hash
            FROM evidence
            WHERE signal_id = :signal_id
              AND review_status != 'human_rejected'
              {restriction_clause}
            ORDER BY attached_at DESC
        """),
        {"signal_id": signal_id},
    )
    return [_row_to_dict(r) for r in result.fetchall()]


@router.post("/attach")
async def attach_evidence(
    body: EvidenceCreate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Attach evidence to a signal event.

    Runs moderation if a backend is configured. If not, evidence is
    stored as review_status="unreviewed" — available for human review.
    """
    # Verify signal exists
    signal_check = await session.execute(
        text("SELECT id FROM signals WHERE id = :id"),
        {"id": body.signal_id},
    )
    if not signal_check.fetchone():
        raise HTTPException(404, f"Signal {body.signal_id} not found")

    # Run moderation (no-op if not configured)
    moderation = get_moderation_service()
    if body.type == "video":
        mod_result = await moderation.moderate_video(
            url=body.url,
            title=body.title,
            description=body.description,
            thumbnail_url=body.thumbnail_url,
        )
    else:
        mod_result = await moderation.moderate_image(
            url=body.url,
            caption=body.title,
        )

    evidence_id = str(uuid.uuid4())
    published_at = None
    if body.published_at:
        try:
            published_at = datetime.fromisoformat(body.published_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    await session.execute(
        text("""
            INSERT INTO evidence (
                id, signal_id, type, url, platform, thumbnail_url, title,
                description, author, language, published_at, attached_at,
                provenance_family, confirmation_policy,
                geolocation_status, time_verification_status,
                graphic_flag, graphic_confidence, graphic_reason,
                review_status, moderation_payload
            ) VALUES (
                :id, :signal_id, :type, :url, :platform, :thumbnail_url, :title,
                :description, :author, :language, :published_at, NOW(),
                :provenance_family, :confirmation_policy,
                :geolocation_status, :time_verification_status,
                :graphic_flag, :graphic_confidence, :graphic_reason,
                :review_status, CAST(:moderation_payload AS jsonb)
            )
        """),
        {
            "id": evidence_id,
            "signal_id": body.signal_id,
            "type": body.type,
            "url": body.url,
            "platform": body.platform,
            "thumbnail_url": body.thumbnail_url,
            "title": body.title,
            "description": body.description,
            "author": body.author,
            "language": body.language,
            "published_at": published_at,
            "provenance_family": body.provenance_family,
            "confirmation_policy": body.confirmation_policy,
            "geolocation_status": body.geolocation_status,
            "time_verification_status": body.time_verification_status,
            "graphic_flag": mod_result.graphic_flag,
            "graphic_confidence": mod_result.graphic_confidence,
            "graphic_reason": mod_result.graphic_reason,
            "review_status": mod_result.review_status,
            "moderation_payload": __import__("json").dumps(mod_result.moderation_payload),
        },
    )
    await session.commit()

    return {
        "id": evidence_id,
        "signalId": body.signal_id,
        "type": body.type,
        "reviewStatus": mod_result.review_status,
        "graphicFlag": mod_result.graphic_flag,
    }


@router.patch("/{evidence_id}/review")
async def review_evidence(
    evidence_id: str,
    body: EvidenceReview,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Update review status of evidence. Human review overrides model flags.

    This is the only way to change graphic_flag after auto-moderation.
    Content is never permanently discarded — only its presentation changes.
    """
    if body.review_status not in ("human_approved", "human_rejected"):
        raise HTTPException(400, "review_status must be 'human_approved' or 'human_rejected'")

    updates = ["review_status = :review_status"]
    params: dict[str, Any] = {"evidence_id": evidence_id, "review_status": body.review_status}

    if body.graphic_flag is not None:
        updates.append("graphic_flag = :graphic_flag")
        params["graphic_flag"] = body.graphic_flag

    if body.graphic_reason is not None:
        updates.append("graphic_reason = :graphic_reason")
        params["graphic_reason"] = body.graphic_reason

    result = await session.execute(
        text(f"UPDATE evidence SET {', '.join(updates)} WHERE id = :evidence_id"),
        params,
    )
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(404, "Evidence not found")

    return {"ok": True, "reviewStatus": body.review_status}


@router.get("/pending-review")
async def get_pending_review(
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return evidence items pending human review."""
    result = await session.execute(
        text("""
            SELECT id, signal_id, type, url, platform, thumbnail_url, title,
                   description, author, language, published_at, attached_at,
                   provenance_family, confirmation_policy,
                   geolocation_status, time_verification_status,
                   graphic_flag, graphic_confidence, graphic_reason,
                   review_status
            FROM evidence
            WHERE review_status IN ('unreviewed', 'auto_flagged')
            ORDER BY attached_at DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    return [_row_to_dict(r) for r in result.fetchall()]


def _row_to_dict(r) -> dict:
    """Convert a DB row to API response dict."""
    d = {
        "id": str(r.id),
        "signalId": str(r.signal_id),
        "type": r.type,
        "url": r.url,
        "platform": r.platform,
        "thumbnailUrl": r.thumbnail_url,
        "title": r.title,
        "description": r.description,
        "author": r.author,
        "language": r.language,
        "publishedAt": r.published_at.isoformat() if r.published_at else None,
        "attachedAt": r.attached_at.isoformat() if r.attached_at else None,
        "provenanceFamily": r.provenance_family,
        "confirmationPolicy": r.confirmation_policy,
        "geolocationStatus": r.geolocation_status,
        "timeVerificationStatus": r.time_verification_status,
        "graphicFlag": r.graphic_flag,
        "graphicConfidence": r.graphic_confidence,
        "graphicReason": r.graphic_reason,
        "reviewStatus": r.review_status,
        "restricted": r.restricted,
        "restrictedReason": r.restricted_reason,
        "contentHash": r.content_hash,
    }

    # Restricted content: redact URL and thumbnail from public responses
    if r.restricted:
        d["url"] = "[RESTRICTED — analyst access only]"
        d["thumbnailUrl"] = None

    return d
