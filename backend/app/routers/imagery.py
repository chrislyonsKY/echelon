"""
Imagery router for public Capella and Maxar scene discovery and analysis.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.open_imagery import OpenImageryService

logger = logging.getLogger(__name__)
router = APIRouter()

_service = OpenImageryService()


class ImageryAnalyzeRequest(BaseModel):
    """Request body for raster scene analysis."""

    itemUrl: str
    bbox: list[float] | None = None


@router.get("/search")
async def search_public_imagery(
    provider: str = Query(description="capella or maxar"),
    bbox: str = Query(description="west,south,east,north"),
    date_from: str = Query(description="YYYY-MM-DD"),
    date_to: str = Query(description="YYYY-MM-DD"),
    limit: int = Query(default=12, ge=1, le=24),
) -> list[dict]:
    """Search public open-data imagery for the current AOI and time window."""
    bbox_tuple = _parse_bbox(bbox)
    start_date = _parse_date(date_from)
    end_date = _parse_date(date_to)
    if start_date > end_date:
        raise HTTPException(400, "date_from must be on or before date_to")

    try:
        return await asyncio.to_thread(
            _service.search_scenes,
            provider,
            bbox_tuple,
            start_date,
            end_date,
            limit,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception:
        logger.exception("Imagery search failed")
        raise HTTPException(502, "Imagery catalog search failed")


@router.post("/analyze")
async def analyze_public_imagery(
    body: ImageryAnalyzeRequest,
) -> dict:
    """Run a lightweight raster analysis over a public scene footprint or AOI."""
    bbox_tuple = None
    if body.bbox is not None:
        if len(body.bbox) != 4:
            raise HTTPException(400, "bbox must contain four numeric values")
        try:
            bbox_tuple = (
                float(body.bbox[0]),
                float(body.bbox[1]),
                float(body.bbox[2]),
                float(body.bbox[3]),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "bbox must contain four numeric values") from exc

    try:
        return await asyncio.to_thread(_service.analyze_scene, body.itemUrl, bbox_tuple)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception:
        logger.exception("Imagery analysis failed")
        raise HTTPException(502, "Imagery analysis failed")


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        west, south, east, north = [float(part) for part in value.split(",")]
    except ValueError as exc:
        raise HTTPException(400, "bbox must be four comma-separated floats") from exc
    return west, south, east, north


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(400, "dates must be in YYYY-MM-DD format") from exc
