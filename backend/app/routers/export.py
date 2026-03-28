"""
Export router — download signals as GeoJSON, KML, or CSV.

For use in Google Earth, QGIS, ArcGIS, and intelligence reports.
"""
import csv
import io
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter()

_SIGNALS_QUERY = """
    SELECT id, source, signal_type,
           ST_Y(location::geometry) AS lat,
           ST_X(location::geometry) AS lon,
           occurred_at, weight, raw_payload, source_id
    FROM signals
    WHERE occurred_at >= NOW() - INTERVAL '1 day' * :days
    {bbox_clause}
    ORDER BY occurred_at DESC
    LIMIT :limit
"""


@router.get("/geojson")
async def export_geojson(
    days: int = Query(default=7, ge=1, le=90),
    bbox: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=5000, le=10000),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Export signals as GeoJSON FeatureCollection."""
    rows = await _fetch_signals(session, days, bbox, source, limit)

    features = []
    for r in rows:
        payload = r.raw_payload or {}
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
            "properties": {
                "id": str(r.id),
                "source": r.source,
                "signalType": r.signal_type,
                "occurredAt": r.occurred_at.isoformat() if r.occurred_at else None,
                "weight": r.weight,
                "sourceId": r.source_id,
                "language": payload.get("language"),
                "title": payload.get("title_original") or payload.get("title"),
                "translatedTitle": payload.get("title_translated"),
                "description": payload.get("description_original") or payload.get("description"),
                "translatedDescription": payload.get("description_translated"),
            },
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "exportedAt": datetime.now(timezone.utc).isoformat(),
            "count": len(features),
            "source": "Echelon GEOINT Platform",
        },
    }

    return Response(
        content=json.dumps(geojson, indent=2),
        media_type="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename=echelon-signals-{days}d.geojson"},
    )


@router.get("/kml")
async def export_kml(
    days: int = Query(default=7, ge=1, le=90),
    bbox: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=5000, le=10000),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Export signals as KML for Google Earth."""
    rows = await _fetch_signals(session, days, bbox, source, limit)

    placemarks = []
    for r in rows:
        payload = r.raw_payload or {}
        title = payload.get("title_translated") or payload.get("title_original") or payload.get("title")
        name = str(title or f"{r.signal_type} ({r.source})")
        desc = (
            f"Weight: {r.weight}<br/>"
            f"Time: {r.occurred_at.isoformat() if r.occurred_at else 'unknown'}<br/>"
            f"Language: {payload.get('language') or 'und'}"
        )
        placemarks.append(f"""    <Placemark>
      <name>{_xml_escape(name)}</name>
      <description>{_xml_escape(desc)}</description>
      <TimeStamp><when>{r.occurred_at.isoformat() if r.occurred_at else ''}</when></TimeStamp>
      <Point><coordinates>{r.lon},{r.lat},0</coordinates></Point>
    </Placemark>""")

    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Echelon Signals Export</name>
    <description>Exported {len(placemarks)} signals, {days}-day window</description>
{chr(10).join(placemarks)}
  </Document>
</kml>"""

    return Response(
        content=kml,
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f"attachment; filename=echelon-signals-{days}d.kml"},
    )


@router.get("/csv")
async def export_csv(
    days: int = Query(default=7, ge=1, le=90),
    bbox: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=5000, le=10000),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Export signals as CSV."""
    rows = await _fetch_signals(session, days, bbox, source, limit)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "source", "signal_type", "lat", "lon", "occurred_at", "weight", "source_id",
        "language", "title", "translated_title", "description", "translated_description",
    ])
    for r in rows:
        payload = r.raw_payload or {}
        writer.writerow([
            str(r.id), r.source, r.signal_type, r.lat, r.lon,
            r.occurred_at.isoformat() if r.occurred_at else "", r.weight, r.source_id or "",
            payload.get("language") or "",
            payload.get("title_original") or payload.get("title") or "",
            payload.get("title_translated") or "",
            payload.get("description_original") or payload.get("description") or "",
            payload.get("description_translated") or "",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=echelon-signals-{days}d.csv"},
    )


async def _fetch_signals(session, days, bbox, source, limit):
    """Shared query for all export formats."""
    params: dict = {"days": days, "limit": limit}
    bbox_clause = ""
    source_clause = ""

    if bbox:
        try:
            west, south, east, north = [float(x) for x in bbox.split(",")]
        except ValueError:
            pass
        else:
            params.update(west=west, south=south, east=east, north=north)
            bbox_clause = "AND ST_Intersects(location, ST_MakeEnvelope(:west, :south, :east, :north, 4326))"

    if source:
        source_clause = "AND source = :source"
        params["source"] = source

    query = _SIGNALS_QUERY.format(bbox_clause=bbox_clause + " " + source_clause)
    result = await session.execute(text(query), params)
    return result.fetchall()


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
