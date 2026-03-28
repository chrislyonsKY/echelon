"""
Events router — analyst-facing incidents clustered from raw signals.

Events group spatiotemporally related signals into a single unit with
corroboration count, source families, and confirmation status.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_RESULTS = 200


@router.get("/")
async def list_events(
    bbox: str | None = Query(default=None, description="west,south,east,north"),
    event_type: str | None = Query(default=None),
    confirmation: str | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=50, le=_MAX_RESULTS),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return recent events with optional spatial and type filters."""
    conditions: list[str] = ["first_seen >= NOW() - INTERVAL '1 day' * :days"]
    params: dict = {"days": days, "limit": limit}

    if bbox:
        try:
            west, south, east, north = [float(x) for x in bbox.split(",")]
        except ValueError:
            raise HTTPException(400, "bbox must be four comma-separated floats")
        conditions.append(
            "ST_Intersects(location, ST_MakeEnvelope(:west, :south, :east, :north, 4326))"
        )
        params.update(west=west, south=south, east=east, north=north)

    if event_type:
        conditions.append("event_type = :event_type")
        params["event_type"] = event_type

    if confirmation:
        conditions.append("confirmation_status = :confirmation")
        params["confirmation"] = confirmation

    where = " AND ".join(conditions)

    result = await session.execute(
        text(f"""
            SELECT id, title, event_type,
                   ST_Y(location::geometry) AS lat,
                   ST_X(location::geometry) AS lon,
                   h3_index_7, first_seen, last_seen,
                   source_families, corroboration_count,
                   confirmation_status, signal_count, summary
            FROM events
            WHERE {where}
            ORDER BY last_seen DESC
            LIMIT :limit
        """),
        params,
    )

    return [
        {
            "id": str(row.id),
            "title": row.title,
            "eventType": row.event_type,
            "location": {"lat": row.lat, "lng": row.lon},
            "h3Index": row.h3_index_7,
            "firstSeen": row.first_seen.isoformat() if row.first_seen else None,
            "lastSeen": row.last_seen.isoformat() if row.last_seen else None,
            "sourceFamilies": row.source_families or [],
            "corroborationCount": row.corroboration_count,
            "confirmationStatus": row.confirmation_status,
            "signalCount": row.signal_count,
            "summary": row.summary,
        }
        for row in result.fetchall()
    ]


@router.get("/{event_id}")
async def get_event_detail(
    event_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return full event detail with supporting signals and evidence."""
    result = await session.execute(
        text("""
            SELECT id, title, event_type,
                   ST_Y(location::geometry) AS lat,
                   ST_X(location::geometry) AS lon,
                   h3_index_7, first_seen, last_seen,
                   source_families, corroboration_count,
                   confirmation_status, signal_count, summary,
                   created_at, updated_at
            FROM events
            WHERE id = :event_id
        """),
        {"event_id": event_id},
    )
    event = result.fetchone()
    if not event:
        raise HTTPException(404, f"Event {event_id} not found")

    # Fetch supporting signals
    signals_result = await session.execute(
        text("""
            SELECT s.id, s.source, s.signal_type,
                   ST_Y(s.location::geometry) AS lat,
                   ST_X(s.location::geometry) AS lon,
                   s.occurred_at, s.weight, s.provenance_family,
                   s.confirmation_policy, s.source_id, s.raw_payload
            FROM signals s
            JOIN event_signals es ON es.signal_id = s.id
            WHERE es.event_id = :event_id
            ORDER BY s.occurred_at DESC
        """),
        {"event_id": event_id},
    )

    # Fetch evidence attached to any of the supporting signals
    evidence_result = await session.execute(
        text("""
            SELECT e.id, e.signal_id, e.type, e.url, e.platform,
                   e.thumbnail_url, e.title, e.provenance_family,
                   e.graphic_flag, e.review_status, e.restricted
            FROM evidence e
            JOIN event_signals es ON es.signal_id = e.signal_id
            WHERE es.event_id = :event_id
              AND e.restricted = false
            ORDER BY e.attached_at DESC
        """),
        {"event_id": event_id},
    )

    return {
        "id": str(event.id),
        "title": event.title,
        "eventType": event.event_type,
        "location": {"lat": event.lat, "lng": event.lon},
        "h3Index": event.h3_index_7,
        "firstSeen": event.first_seen.isoformat() if event.first_seen else None,
        "lastSeen": event.last_seen.isoformat() if event.last_seen else None,
        "sourceFamilies": event.source_families or [],
        "corroborationCount": event.corroboration_count,
        "confirmationStatus": event.confirmation_status,
        "signalCount": event.signal_count,
        "summary": event.summary,
        "createdAt": event.created_at.isoformat() if event.created_at else None,
        "updatedAt": event.updated_at.isoformat() if event.updated_at else None,
        "signals": [
            {
                "id": str(s.id),
                "source": s.source,
                "signalType": s.signal_type,
                "location": {"lat": s.lat, "lng": s.lon},
                "occurredAt": s.occurred_at.isoformat() if s.occurred_at else None,
                "weight": s.weight,
                "provenanceFamily": s.provenance_family,
                "confirmationPolicy": s.confirmation_policy,
                "sourceId": s.source_id,
            }
            for s in signals_result.fetchall()
        ],
        "evidence": [
            {
                "id": str(ev.id),
                "signalId": str(ev.signal_id),
                "type": ev.type,
                "url": ev.url,
                "platform": ev.platform,
                "thumbnailUrl": ev.thumbnail_url,
                "title": ev.title,
                "provenanceFamily": ev.provenance_family,
                "graphicFlag": ev.graphic_flag,
                "reviewStatus": ev.review_status,
            }
            for ev in evidence_result.fetchall()
        ],
    }


@router.get("/for-cell/{h3_index}")
async def get_events_for_cell(
    h3_index: str,
    days: int = Query(default=7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return events associated with a specific H3 cell."""
    result = await session.execute(
        text("""
            SELECT id, title, event_type,
                   ST_Y(location::geometry) AS lat,
                   ST_X(location::geometry) AS lon,
                   first_seen, last_seen,
                   source_families, corroboration_count,
                   confirmation_status, signal_count
            FROM events
            WHERE h3_index_7 = :h3
              AND first_seen >= NOW() - INTERVAL '1 day' * :days
            ORDER BY last_seen DESC
        """),
        {"h3": h3_index, "days": days},
    )

    return [
        {
            "id": str(row.id),
            "title": row.title,
            "eventType": row.event_type,
            "location": {"lat": row.lat, "lng": row.lon},
            "firstSeen": row.first_seen.isoformat() if row.first_seen else None,
            "lastSeen": row.last_seen.isoformat() if row.last_seen else None,
            "sourceFamilies": row.source_families or [],
            "corroborationCount": row.corroboration_count,
            "confirmationStatus": row.confirmation_status,
            "signalCount": row.signal_count,
        }
        for row in result.fetchall()
    ]
