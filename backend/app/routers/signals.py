"""
Signals router — query individual signal events by cell or bounding box.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_RESULTS = 500


@router.get("/event/{signal_id}")
async def get_signal_detail(
    signal_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return full detail for a single signal event. Used for permalinks."""
    result = await session.execute(
        text("""
            SELECT id, source, signal_type,
                   ST_Y(location::geometry) AS lat,
                   ST_X(location::geometry) AS lon,
                   h3_index_5, h3_index_7, h3_index_9,
                   occurred_at, ingested_at, weight, raw_payload, source_id, dedup_hash
            FROM signals
            WHERE id = :signal_id
        """),
        {"signal_id": signal_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, f"Signal {signal_id} not found")

    # Find nearby signals (same H3 res-7 cell, +-24h window) for context
    from datetime import timedelta
    window_start = row.occurred_at - timedelta(hours=24) if row.occurred_at else None
    window_end = row.occurred_at + timedelta(hours=24) if row.occurred_at else None

    related = await session.execute(
        text("""
            SELECT id, source, signal_type,
                   ST_Y(location::geometry) AS lat,
                   ST_X(location::geometry) AS lon,
                   occurred_at, weight, raw_payload
            FROM signals
            WHERE h3_index_7 = :h3_7
              AND id != :signal_id
              AND occurred_at >= :window_start
              AND occurred_at <= :window_end
            ORDER BY occurred_at DESC
            LIMIT 20
        """),
        {"h3_7": row.h3_index_7, "signal_id": signal_id, "window_start": window_start, "window_end": window_end},
    )

    payload_fields = _signal_payload_fields(row.raw_payload)

    return {
        "id": str(row.id),
        "source": row.source,
        "signalType": row.signal_type,
        "location": {"lat": row.lat, "lng": row.lon},
        "h3": {"res5": row.h3_index_5, "res7": row.h3_index_7, "res9": row.h3_index_9},
        "occurredAt": row.occurred_at.isoformat() if row.occurred_at else None,
        "ingestedAt": row.ingested_at.isoformat() if row.ingested_at else None,
        "weight": row.weight,
        "sourceId": row.source_id,
        **payload_fields,
        "relatedSignals": [
            {
                "id": str(r.id),
                "source": r.source,
                "signalType": r.signal_type,
                "location": {"lat": r.lat, "lng": r.lon},
                "occurredAt": r.occurred_at.isoformat() if r.occurred_at else None,
                "weight": r.weight,
                **_signal_payload_fields(r.raw_payload),
            }
            for r in related.fetchall()
        ],
    }


def _signal_payload_fields(payload: dict | None) -> dict:
    """Promote provenance fields from raw payload for easier client access."""
    payload = payload or {}
    metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}

    provenance_family = payload.get("provenance_family") or metadata.get("provenance_family")
    confirmation_policy = payload.get("confirmation_policy") or metadata.get("confirmation_policy")

    return {
        "rawPayload": payload,
        "provenanceFamily": provenance_family,
        "confirmationPolicy": confirmation_policy,
    }


@router.get("/latest")
async def get_latest_signals(
    limit: int = Query(default=15, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return the most recent signals globally. Used by the live feed."""
    result = await session.execute(
        text("""
            SELECT id, source, signal_type,
                   ST_Y(location::geometry) AS lat,
                   ST_X(location::geometry) AS lon,
                   occurred_at, weight, raw_payload, source_id
            FROM signals
            ORDER BY occurred_at DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    return [
        {
            "id": str(row.id),
            "source": row.source,
            "signalType": row.signal_type,
            "location": {"lat": row.lat, "lng": row.lon},
            "occurredAt": row.occurred_at.isoformat() if row.occurred_at else None,
            "weight": row.weight,
            "sourceId": row.source_id,
            **_signal_payload_fields(row.raw_payload),
        }
        for row in result.fetchall()
    ]


@router.get("/")
async def get_signals(
    h3_index: str | None = Query(default=None),
    bbox: str | None = Query(default=None, description="west,south,east,north"),
    source: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=200, le=_MAX_RESULTS),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return signal events filtered by H3 cell or bounding box.

    Either h3_index or bbox must be provided.
    Results are ordered by occurred_at descending.
    """
    if not h3_index and not bbox:
        raise HTTPException(400, "Either h3_index or bbox must be provided")

    conditions: list[str] = []
    params: dict = {"limit": limit}

    if h3_index:
        # Match any resolution column
        conditions.append(
            "(h3_index_5 = :h3 OR h3_index_7 = :h3 OR h3_index_9 = :h3)"
        )
        params["h3"] = h3_index

    if bbox:
        try:
            west, south, east, north = [float(x) for x in bbox.split(",")]
        except ValueError:
            raise HTTPException(400, "bbox must be four comma-separated floats")
        conditions.append(
            "ST_Intersects(location, ST_MakeEnvelope(:west, :south, :east, :north, 4326))"
        )
        params.update(west=west, south=south, east=east, north=north)

    if source:
        conditions.append("source = :source")
        params["source"] = source

    if date_from:
        conditions.append("occurred_at >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("occurred_at <= :date_to")
        params["date_to"] = date_to

    where = " AND ".join(conditions)
    query = text(f"""
        SELECT id, source, signal_type,
               ST_Y(location::geometry) AS lat,
               ST_X(location::geometry) AS lon,
               occurred_at, weight, raw_payload, source_id
        FROM signals
        WHERE {where}
        ORDER BY occurred_at DESC
        LIMIT :limit
    """)

    result = await session.execute(query, params)

    return [
        {
            "id": str(row.id),
            "source": row.source,
            "signalType": row.signal_type,
            "location": {"lat": row.lat, "lng": row.lon},
            "occurredAt": row.occurred_at.isoformat() if row.occurred_at else None,
            "weight": row.weight,
            "sourceId": row.source_id,
            **_signal_payload_fields(row.raw_payload),
        }
        for row in result.fetchall()
    ]
