"""
Convergence router — serves H3 heatmap tiles and cell detail endpoints.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/tiles")
async def get_convergence_tiles(
    resolution: int = Query(default=5, ge=5, le=9),
    bbox: str | None = Query(default=None, description="west,south,east,north"),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return pre-computed convergence Z-scores for H3 cells at the requested resolution.

    Optionally filtered by bounding box. Results are served from the
    h3_convergence_scores cache table (refreshed every 15 minutes by Celery).
    """
    params: dict = {"resolution": resolution}
    bbox_filter = ""

    if bbox:
        try:
            west, south, east, north = [float(x) for x in bbox.split(",")]
        except ValueError:
            raise HTTPException(400, "bbox must be four comma-separated floats: west,south,east,north")
        params.update(west=west, south=south, east=east, north=north)
        # Filter cells whose center falls within the viewport bbox.
        # h3_convergence_scores stores an h3_index string; we join signals
        # to filter spatially, but a faster approach is to use h3 cell
        # center coordinates stored during scoring. For now, filter via
        # the signals table to find which cells have signals in the bbox.
        bbox_filter = """
            AND h3_index IN (
                SELECT DISTINCT h3_index_5 FROM signals
                WHERE ST_Intersects(location, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
                UNION
                SELECT DISTINCT h3_index_7 FROM signals
                WHERE ST_Intersects(location, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
                UNION
                SELECT DISTINCT h3_index_9 FROM signals
                WHERE ST_Intersects(location, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
            )
        """

    result = await session.execute(
        text(f"""
            SELECT h3_index, resolution, z_score, raw_score,
                   signal_breakdown, low_confidence, computed_at
            FROM h3_convergence_scores
            WHERE resolution = :resolution AND raw_score > 0.01
            {bbox_filter}
            ORDER BY raw_score DESC
            LIMIT 3000
        """),
        params,
    )

    return [
        {
            "h3Index": row.h3_index,
            "resolution": row.resolution,
            "zScore": round(row.z_score, 4),
            "rawScore": round(row.raw_score, 6),
            "signalBreakdown": row.signal_breakdown or {},
            "lowConfidence": row.low_confidence,
            "computedAt": row.computed_at.isoformat() if row.computed_at else None,
        }
        for row in result.fetchall()
    ]


@router.get("/cell/{h3_index}")
async def get_cell_detail(
    h3_index: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return full convergence detail for a single H3 cell including signal breakdown."""
    result = await session.execute(
        text("""
            SELECT h3_index, resolution, z_score, raw_score,
                   signal_breakdown, low_confidence, computed_at
            FROM h3_convergence_scores
            WHERE h3_index = :h3_index
            ORDER BY resolution
        """),
        {"h3_index": h3_index},
    )
    rows = result.fetchall()

    if not rows:
        raise HTTPException(404, f"No convergence data for cell {h3_index}")

    return {
        "h3Index": h3_index,
        "scores": [
            {
                "resolution": row.resolution,
                "zScore": round(row.z_score, 4),
                "rawScore": round(row.raw_score, 6),
                "signalBreakdown": row.signal_breakdown or {},
                "lowConfidence": row.low_confidence,
                "computedAt": row.computed_at.isoformat() if row.computed_at else None,
            }
            for row in rows
        ],
    }


@router.get("/trends")
async def get_regional_trends(
    bbox: str | None = Query(default=None, description="west,south,east,north"),
    days: int = Query(default=7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return signal counts and trend indicators grouped by source for a region.

    Used by the Admin1 trend table and regional monitors.
    If no bbox is provided, returns global trends.
    """
    params: dict = {"days": days}
    bbox_clause = ""

    if bbox:
        try:
            west, south, east, north = [float(x) for x in bbox.split(",")]
        except ValueError:
            raise HTTPException(400, "bbox must be four comma-separated floats")
        params.update(west=west, south=south, east=east, north=north)
        bbox_clause = "AND ST_Intersects(location, ST_MakeEnvelope(:west, :south, :east, :north, 4326))"

    result = await session.execute(
        text(f"""
            WITH current_period AS (
                SELECT signal_type, COUNT(*) AS count
                FROM signals
                WHERE occurred_at >= NOW() - INTERVAL '1 day' * :days
                {bbox_clause}
                GROUP BY signal_type
            ),
            previous_period AS (
                SELECT signal_type, COUNT(*) AS count
                FROM signals
                WHERE occurred_at >= NOW() - INTERVAL '1 day' * :days * 2
                  AND occurred_at < NOW() - INTERVAL '1 day' * :days
                {bbox_clause}
                GROUP BY signal_type
            )
            SELECT
                COALESCE(c.signal_type, p.signal_type) AS signal_type,
                COALESCE(c.count, 0) AS current_count,
                COALESCE(p.count, 0) AS previous_count
            FROM current_period c
            FULL OUTER JOIN previous_period p ON c.signal_type = p.signal_type
            ORDER BY COALESCE(c.count, 0) DESC
        """),
        params,
    )

    trends = []
    for row in result.fetchall():
        current = row.current_count
        previous = row.previous_count

        # Compute change % with cold-start protection:
        # - If no previous data, trend is "new" not "rising"
        # - If previous < 10, percentage is unreliable — flag as low baseline
        # - Cap percentage at ±999% to prevent misleading extremes
        if previous >= 10:
            change_pct = round((current - previous) / previous * 100, 1)
            change_pct = max(-999.0, min(999.0, change_pct))
        elif previous > 0:
            change_pct = round((current - previous) / previous * 100, 1)
            change_pct = max(-999.0, min(999.0, change_pct))
        elif current > 0:
            change_pct = 0.0  # No baseline to compare against — show 0, not +100%
        else:
            change_pct = 0.0

        low_baseline = (current + previous) < 30

        # Trend label with cold-start awareness
        if low_baseline or previous < 5:
            trend = "insufficient_data"
        elif change_pct > 10:
            trend = "rising"
        elif change_pct < -10:
            trend = "falling"
        else:
            trend = "stable"

        trends.append({
            "signalType": row.signal_type,
            "currentCount": current,
            "previousCount": previous,
            "changePct": change_pct,
            "trend": trend,
            "lowBaseline": low_baseline,
        })

    return trends
