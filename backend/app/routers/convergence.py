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

    if bbox:
        try:
            west, south, east, north = [float(x) for x in bbox.split(",")]
        except ValueError:
            raise HTTPException(400, "bbox must be four comma-separated floats: west,south,east,north")
        params.update(west=west, south=south, east=east, north=north)

        # Filter by joining signals table to find cells within bbox
        # For now, return all cells at the resolution (bbox filtering is a future optimization)

    result = await session.execute(
        text("""
            SELECT h3_index, resolution, z_score, raw_score,
                   signal_breakdown, low_confidence, computed_at
            FROM h3_convergence_scores
            WHERE resolution = :resolution
            ORDER BY z_score DESC
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
