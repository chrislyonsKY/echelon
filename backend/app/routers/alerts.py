"""
Alerts router — AOI management and alert notification endpoints.
Requires authentication for all write operations.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.routers.auth import get_current_user_id, require_auth

logger = logging.getLogger(__name__)
router = APIRouter()


class AOICreate(BaseModel):
    """Request body for creating a new AOI."""
    name: str
    geometry: dict        # GeoJSON Polygon
    alert_threshold: float = 2.0
    alert_email: bool = False


@router.get("/unread")
async def get_unread_alerts(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> list[dict]:
    """Return unread alert records for the current authenticated user."""
    result = await session.execute(
        text("""
            SELECT a.id, a.aoi_id, ao.name AS aoi_name, a.trigger_type,
                   a.trigger_detail, a.h3_index, a.z_score, a.fired_at
            FROM alerts a
            JOIN aois ao ON ao.id = a.aoi_id
            WHERE ao.user_id = :user_id AND a.read_at IS NULL
            ORDER BY a.fired_at DESC
            LIMIT 50
        """),
        {"user_id": user_id},
    )
    return [
        {
            "id": str(r.id),
            "aoiId": str(r.aoi_id),
            "aoiName": r.aoi_name,
            "triggerType": r.trigger_type,
            "triggerDetail": r.trigger_detail,
            "h3Index": r.h3_index,
            "zScore": r.z_score,
            "firedAt": r.fired_at.isoformat() if r.fired_at else None,
        }
        for r in result.fetchall()
    ]


@router.patch("/{alert_id}/read")
async def mark_alert_read(
    alert_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> dict:
    """Mark an alert as read."""
    result = await session.execute(
        text("""
            UPDATE alerts SET read_at = NOW()
            WHERE id = :alert_id
              AND aoi_id IN (SELECT id FROM aois WHERE user_id = :user_id)
              AND read_at IS NULL
        """),
        {"alert_id": alert_id, "user_id": user_id},
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(404, "Alert not found or already read")
    return {"ok": True}


@router.get("/aois")
async def get_aois(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> list[dict]:
    """Return all saved AOIs for the current authenticated user."""
    result = await session.execute(
        text("""
            SELECT id, name, ST_AsGeoJSON(geometry::geometry) AS geojson,
                   alert_threshold, alert_email, created_at
            FROM aois
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """),
        {"user_id": user_id},
    )
    import json
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "geometry": json.loads(r.geojson),
            "alertThreshold": r.alert_threshold,
            "alertEmail": r.alert_email,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in result.fetchall()
    ]


@router.post("/aois")
async def create_aoi(
    body: AOICreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> dict:
    """Create a new AOI for the current authenticated user."""
    import json

    # Validate geometry is a Polygon
    geom_type = body.geometry.get("type")
    if geom_type != "Polygon":
        raise HTTPException(400, f"Geometry must be a Polygon, got {geom_type}")

    coords = body.geometry.get("coordinates")
    if not coords or not isinstance(coords, list):
        raise HTTPException(400, "Invalid polygon coordinates")

    aoi_id = str(uuid.uuid4())
    geojson_str = json.dumps(body.geometry)

    await session.execute(
        text("""
            INSERT INTO aois (id, user_id, name, geometry, alert_threshold, alert_email, created_at)
            VALUES (:id, :user_id, :name,
                    ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326)::geography,
                    :threshold, :alert_email, NOW())
        """),
        {
            "id": aoi_id,
            "user_id": user_id,
            "name": body.name,
            "geojson": geojson_str,
            "threshold": body.alert_threshold,
            "alert_email": body.alert_email,
        },
    )
    await session.commit()

    return {
        "id": aoi_id,
        "name": body.name,
        "geometry": body.geometry,
        "alertThreshold": body.alert_threshold,
        "alertEmail": body.alert_email,
    }


@router.get("/dashboard")
async def get_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> list[dict]:
    """Return all AOIs with current status: max Z-score, signal count, recent alerts."""
    import json

    result = await session.execute(
        text("""
            SELECT
                ao.id, ao.name, ao.alert_threshold, ao.alert_email, ao.created_at,
                ST_AsGeoJSON(ao.geometry::geometry) AS geojson,
                (
                    SELECT MAX(h.z_score)
                    FROM h3_convergence_scores h
                    WHERE h.resolution = 7
                      AND ST_Intersects(
                          ST_SetSRID(ST_MakePoint(
                              (ST_XMin(ao.geometry::geometry) + ST_XMax(ao.geometry::geometry)) / 2,
                              (ST_YMin(ao.geometry::geometry) + ST_YMax(ao.geometry::geometry)) / 2
                          ), 4326)::geography,
                          ao.geometry
                      )
                ) AS max_z_score,
                (
                    SELECT COUNT(*)
                    FROM signals s
                    WHERE ST_Intersects(s.location, ao.geometry)
                      AND s.occurred_at >= NOW() - INTERVAL '7 days'
                ) AS signal_count_7d,
                (
                    SELECT COUNT(*)
                    FROM alerts al
                    WHERE al.aoi_id = ao.id AND al.read_at IS NULL
                ) AS unread_alert_count,
                (
                    SELECT MAX(al.fired_at)
                    FROM alerts al
                    WHERE al.aoi_id = ao.id
                ) AS last_alert_at
            FROM aois ao
            WHERE ao.user_id = :user_id
            ORDER BY ao.created_at DESC
        """),
        {"user_id": user_id},
    )
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "alertThreshold": r.alert_threshold,
            "alertEmail": r.alert_email,
            "geometry": json.loads(r.geojson),
            "maxZScore": round(r.max_z_score, 2) if r.max_z_score is not None else None,
            "signalCount7d": r.signal_count_7d,
            "unreadAlertCount": r.unread_alert_count,
            "lastAlertAt": r.last_alert_at.isoformat() if r.last_alert_at else None,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in result.fetchall()
    ]


@router.delete("/aois/{aoi_id}")
async def delete_aoi(
    aoi_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_auth),
) -> dict:
    """Delete an AOI. Only the owning user may delete their own AOIs."""
    result = await session.execute(
        text("DELETE FROM aois WHERE id = :id AND user_id = :user_id"),
        {"id": aoi_id, "user_id": user_id},
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(404, "AOI not found")
    return {"ok": True}
