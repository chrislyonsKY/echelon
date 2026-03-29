"""
Investigations router — saved analyst views, provenance, scoring, notes, feedback.

An investigation captures the full analyst workspace state (viewport, layers,
filters, selected events, imagery, notes) so work can be resumed and shared.
Provenance and scoring endpoints support transparency into convergence results.
"""
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.routers.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class InvestigationCreate(BaseModel):
    """Request body for creating a new investigation (saved view)."""
    title: str
    description: str | None = None
    viewport: dict | None = None          # {lat, lng, zoom, bearing, pitch}
    date_range: dict | None = None        # {start, end}
    active_layers: list[str] | None = None
    filters: dict | None = None
    aoi_geojson: dict | None = None       # GeoJSON Polygon/MultiPolygon
    selected_events: list[str] | None = None
    imagery_selections: list[dict] | None = None
    notes: str | None = None
    tags: list[str] | None = None


class InvestigationUpdate(BaseModel):
    """Partial update for an existing investigation."""
    title: str | None = None
    description: str | None = None
    viewport: dict | None = None
    date_range: dict | None = None
    active_layers: list[str] | None = None
    filters: dict | None = None
    aoi_geojson: dict | None = None
    selected_events: list[str] | None = None
    imagery_selections: list[dict] | None = None
    notes: str | None = None
    tags: list[str] | None = None


class NoteCreate(BaseModel):
    """Request body for adding an analyst note."""
    event_id: str | None = None
    h3_index: str | None = None
    note_type: str = "observation"        # "observation" | "assessment" | "question"
    content: str
    confidence: str | None = None         # "low" | "medium" | "high"


class FeedbackCreate(BaseModel):
    """Request body for false-positive feedback."""
    event_id: str | None = None
    h3_index: str | None = None
    signal_ids: list[str] | None = None
    reason: str                           # "false_positive" | "duplicate" | "stale" | "other"
    detail: str | None = None


# ---------------------------------------------------------------------------
# Investigation CRUD
# ---------------------------------------------------------------------------

@router.post("/")
async def create_investigation(
    body: InvestigationCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> dict:
    """Create a new investigation (saved analyst view)."""
    inv_id = str(uuid.uuid4())

    await session.execute(
        text("""
            INSERT INTO investigations (
                id, user_id, title, description,
                viewport, date_range, active_layers, filters,
                aoi_geojson, selected_events, imagery_selections,
                notes, tags, created_at, updated_at
            ) VALUES (
                :id, :user_id, :title, :description,
                CAST(:viewport AS jsonb), CAST(:date_range AS jsonb),
                CAST(:active_layers AS jsonb), CAST(:filters AS jsonb),
                CAST(:aoi_geojson AS jsonb), CAST(:selected_events AS jsonb),
                CAST(:imagery_selections AS jsonb),
                :notes, CAST(:tags AS jsonb), NOW(), NOW()
            )
        """),
        {
            "id": inv_id,
            "user_id": user_id,
            "title": body.title,
            "description": body.description,
            "viewport": json.dumps(body.viewport) if body.viewport else None,
            "date_range": json.dumps(body.date_range) if body.date_range else None,
            "active_layers": json.dumps(body.active_layers) if body.active_layers else None,
            "filters": json.dumps(body.filters) if body.filters else None,
            "aoi_geojson": json.dumps(body.aoi_geojson) if body.aoi_geojson else None,
            "selected_events": json.dumps(body.selected_events) if body.selected_events else None,
            "imagery_selections": json.dumps(body.imagery_selections) if body.imagery_selections else None,
            "notes": body.notes,
            "tags": json.dumps(body.tags) if body.tags else None,
        },
    )
    await session.commit()

    return {
        "id": inv_id,
        "title": body.title,
        "description": body.description,
        "tags": body.tags or [],
    }


@router.get("/")
async def list_investigations(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> list[dict]:
    """List all investigations for the current authenticated user."""
    result = await session.execute(
        text("""
            SELECT id, title, description, tags, created_at, updated_at
            FROM investigations
            WHERE user_id = :user_id
            ORDER BY updated_at DESC
        """),
        {"user_id": user_id},
    )
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "description": r.description,
            "tags": r.tags or [],
            "createdAt": r.created_at.isoformat() if r.created_at else None,
            "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in result.fetchall()
    ]


@router.get("/{investigation_id}")
async def get_investigation(
    investigation_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> dict:
    """Return full investigation state including all fields."""
    result = await session.execute(
        text("""
            SELECT id, title, description,
                   viewport, date_range, active_layers, filters,
                   aoi_geojson, selected_events, imagery_selections,
                   notes, tags, created_at, updated_at
            FROM investigations
            WHERE id = :id AND user_id = :user_id
        """),
        {"id": investigation_id, "user_id": user_id},
    )
    r = result.fetchone()
    if not r:
        raise HTTPException(404, "Investigation not found")

    return {
        "id": str(r.id),
        "title": r.title,
        "description": r.description,
        "viewport": r.viewport,
        "dateRange": r.date_range,
        "activeLayers": r.active_layers or [],
        "filters": r.filters,
        "aoiGeojson": r.aoi_geojson,
        "selectedEvents": r.selected_events or [],
        "imagerySelections": r.imagery_selections or [],
        "notes": r.notes,
        "tags": r.tags or [],
        "createdAt": r.created_at.isoformat() if r.created_at else None,
        "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.patch("/{investigation_id}")
async def update_investigation(
    investigation_id: str,
    body: InvestigationUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> dict:
    """Partial update of an investigation. Only provided fields are changed."""
    updates: list[str] = []
    params: dict = {"id": investigation_id, "user_id": user_id}

    field_map = {
        "title": ("title", False),
        "description": ("description", False),
        "viewport": ("viewport", True),
        "date_range": ("date_range", True),
        "active_layers": ("active_layers", True),
        "filters": ("filters", True),
        "aoi_geojson": ("aoi_geojson", True),
        "selected_events": ("selected_events", True),
        "imagery_selections": ("imagery_selections", True),
        "notes": ("notes", False),
        "tags": ("tags", True),
    }

    for field_name, (col_name, is_json) in field_map.items():
        value = getattr(body, field_name)
        if value is not None:
            if is_json:
                updates.append(f"{col_name} = CAST(:{col_name} AS jsonb)")
                params[col_name] = json.dumps(value)
            else:
                updates.append(f"{col_name} = :{col_name}")
                params[col_name] = value

    if not updates:
        raise HTTPException(400, "No fields to update")

    updates.append("updated_at = NOW()")

    result = await session.execute(
        text(f"""
            UPDATE investigations
            SET {', '.join(updates)}
            WHERE id = :id AND user_id = :user_id
        """),
        params,
    )
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(404, "Investigation not found")

    return {"ok": True, "id": investigation_id}


@router.delete("/{investigation_id}")
async def delete_investigation(
    investigation_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> dict:
    """Delete an investigation. Only the owning user may delete."""
    result = await session.execute(
        text("DELETE FROM investigations WHERE id = :id AND user_id = :user_id"),
        {"id": investigation_id, "user_id": user_id},
    )
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(404, "Investigation not found")

    return {"ok": True}


# ---------------------------------------------------------------------------
# Provenance timeline
# ---------------------------------------------------------------------------

@router.get("/provenance/{event_id}")
async def get_provenance_timeline(
    event_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Provenance timeline for an event.

    Returns all contributing signals via event_signals junction, ordered
    by occurred_at, with source metadata and score contribution reason.
    """
    result = await session.execute(
        text("""
            SELECT s.id, s.source, s.signal_type,
                   s.occurred_at, s.ingested_at, s.weight,
                   s.provenance_family, s.confirmation_policy,
                   es.score_contribution_reason
            FROM signals s
            JOIN event_signals es ON es.signal_id = s.id
            WHERE es.event_id = :event_id
            ORDER BY s.occurred_at ASC
        """),
        {"event_id": event_id},
    )
    rows = result.fetchall()
    if not rows:
        raise HTTPException(404, f"No signals found for event {event_id}")

    return [
        {
            "id": str(r.id),
            "source": r.source,
            "signalType": r.signal_type,
            "occurredAt": r.occurred_at.isoformat() if r.occurred_at else None,
            "ingestedAt": r.ingested_at.isoformat() if r.ingested_at else None,
            "weight": r.weight,
            "provenanceFamily": r.provenance_family,
            "confirmationPolicy": r.confirmation_policy,
            "scoreContributionReason": r.score_contribution_reason,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Scoring explanation
# ---------------------------------------------------------------------------

@router.get("/scoring/{h3_index}")
async def get_scoring_explanation(
    h3_index: str,
    days: int = Query(default=7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Scoring explanation for a convergence cell.

    Returns the Z-score, raw_score, signal_breakdown, confidence fields,
    and a list of recent contributing signals with their weight.
    """
    # Fetch convergence score for the cell
    score_result = await session.execute(
        text("""
            SELECT h3_index, z_score, raw_score, signal_breakdown,
                   confidence_level, low_confidence,
                   baseline_mean, baseline_std, observation_count,
                   computed_at
            FROM h3_convergence_scores
            WHERE h3_index = :h3_index
            ORDER BY computed_at DESC
            LIMIT 1
        """),
        {"h3_index": h3_index},
    )
    score = score_result.fetchone()
    if not score:
        raise HTTPException(404, f"No convergence score for cell {h3_index}")

    # Fetch recent signals in this cell
    signals_result = await session.execute(
        text("""
            SELECT id, source, signal_type,
                   occurred_at, weight, provenance_family
            FROM signals
            WHERE h3_index = :h3_index
              AND occurred_at >= NOW() - INTERVAL '1 day' * :days
            ORDER BY occurred_at DESC
            LIMIT 100
        """),
        {"h3_index": h3_index, "days": days},
    )

    return {
        "h3Index": score.h3_index,
        "zScore": score.z_score,
        "rawScore": score.raw_score,
        "signalBreakdown": score.signal_breakdown,
        "confidenceLevel": score.confidence_level,
        "lowConfidence": score.low_confidence,
        "baselineMean": score.baseline_mean,
        "baselineStd": score.baseline_std,
        "observationCount": score.observation_count,
        "computedAt": score.computed_at.isoformat() if score.computed_at else None,
        "signals": [
            {
                "id": str(s.id),
                "source": s.source,
                "signalType": s.signal_type,
                "occurredAt": s.occurred_at.isoformat() if s.occurred_at else None,
                "weight": s.weight,
                "provenanceFamily": s.provenance_family,
            }
            for s in signals_result.fetchall()
        ],
    }


# ---------------------------------------------------------------------------
# Analyst notes
# ---------------------------------------------------------------------------

@router.post("/notes")
async def create_note(
    body: NoteCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> dict:
    """Add an analyst note to an event or H3 cell."""
    if not body.event_id and not body.h3_index:
        raise HTTPException(400, "Must provide either event_id or h3_index")

    note_id = str(uuid.uuid4())

    await session.execute(
        text("""
            INSERT INTO analyst_notes (
                id, user_id, event_id, h3_index,
                note_type, content, confidence, created_at
            ) VALUES (
                :id, :user_id, :event_id, :h3_index,
                :note_type, :content, :confidence, NOW()
            )
        """),
        {
            "id": note_id,
            "user_id": user_id,
            "event_id": body.event_id,
            "h3_index": body.h3_index,
            "note_type": body.note_type,
            "content": body.content,
            "confidence": body.confidence,
        },
    )
    await session.commit()

    return {
        "id": note_id,
        "noteType": body.note_type,
        "content": body.content,
        "confidence": body.confidence,
    }


@router.get("/notes/{event_id}")
async def get_notes_for_event(
    event_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return all analyst notes for a given event."""
    result = await session.execute(
        text("""
            SELECT id, user_id, note_type, content, confidence, created_at
            FROM analyst_notes
            WHERE event_id = :event_id
            ORDER BY created_at DESC
        """),
        {"event_id": event_id},
    )
    return [
        {
            "id": str(r.id),
            "userId": str(r.user_id),
            "noteType": r.note_type,
            "content": r.content,
            "confidence": r.confidence,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in result.fetchall()
    ]


# ---------------------------------------------------------------------------
# False-positive feedback
# ---------------------------------------------------------------------------

@router.post("/feedback")
async def submit_feedback(
    body: FeedbackCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> dict:
    """Submit false-positive or correction feedback on an event or cell."""
    if not body.event_id and not body.h3_index:
        raise HTTPException(400, "Must provide either event_id or h3_index")

    feedback_id = str(uuid.uuid4())

    await session.execute(
        text("""
            INSERT INTO analyst_feedback (
                id, user_id, event_id, h3_index,
                signal_ids, reason, detail, created_at
            ) VALUES (
                :id, :user_id, :event_id, :h3_index,
                CAST(:signal_ids AS jsonb), :reason, :detail, NOW()
            )
        """),
        {
            "id": feedback_id,
            "user_id": user_id,
            "event_id": body.event_id,
            "h3_index": body.h3_index,
            "signal_ids": json.dumps(body.signal_ids) if body.signal_ids else None,
            "reason": body.reason,
            "detail": body.detail,
        },
    )
    await session.commit()

    return {
        "id": feedback_id,
        "reason": body.reason,
        "ok": True,
    }
