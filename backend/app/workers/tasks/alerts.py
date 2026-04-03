"""
AOI alert checking task. Runs every 15 minutes.

For each user AOI, checks if any H3 cell within the AOI geometry
exceeds the user's Z-score threshold. Fires alert records and sends
email via Resend if the user opted in.

Task is idempotent — duplicate alerts are prevented by checking
if an alert was already fired for the same cell in the same scoring cycle.
"""
import asyncio
import html
import logging
import uuid
from datetime import UTC, datetime, timedelta

import resend
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Don't re-fire alerts for the same cell within this window
ALERT_COOLDOWN_HOURS = 6


@celery_app.task(
    name="app.workers.tasks.alerts.check_all_aois",
    bind=True,
    max_retries=2,
    soft_time_limit=120,
    time_limit=180,
    acks_late=True,
)
def check_all_aois(self) -> dict:
    """Check all AOIs for Z-score threshold breaches and fire alerts.

    Returns:
        Dict with 'aois_checked', 'alerts_fired', 'emails_sent' counts.
    """
    try:
        return asyncio.run(_check_alerts())
    except Exception as exc:
        logger.exception("Alert checking failed")
        raise self.retry(exc=exc)


async def _check_alerts() -> dict:
    """Async implementation of the AOI alert checker."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    aois_checked = 0
    alerts_fired = 0
    emails_sent = 0

    try:
        # Fetch all AOIs with their user info
        async with session_factory() as session:
            result = await session.execute(text("""
                SELECT a.id, a.user_id, a.name, a.alert_threshold, a.alert_email,
                       ST_AsGeoJSON(a.geometry::geometry) AS geojson,
                       u.email, u.github_username
                FROM aois a
                JOIN users u ON u.id = a.user_id
            """))
            aois = result.fetchall()

        if not aois:
            return {"aois_checked": 0, "alerts_fired": 0, "emails_sent": 0}

        cooldown_cutoff = datetime.now(UTC) - timedelta(hours=ALERT_COOLDOWN_HOURS)

        for aoi in aois:
            aois_checked += 1

            async with session_factory() as session:
                # Find convergence cells that intersect this AOI and exceed threshold
                # Use res 7 (regional) for alert checking
                breaching = await session.execute(
                    text("""
                        SELECT cs.h3_index, cs.z_score, cs.raw_score, cs.signal_breakdown
                        FROM h3_convergence_scores cs
                        JOIN signals s ON s.h3_index_7 = cs.h3_index AND cs.resolution = 7
                        WHERE cs.z_score >= :threshold
                          AND cs.resolution = 7
                          AND ST_Intersects(
                              s.location,
                              ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326)::geography
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM alerts al
                              WHERE al.aoi_id = :aoi_id
                                AND al.h3_index = cs.h3_index
                                AND al.fired_at > :cooldown
                          )
                        GROUP BY cs.h3_index, cs.z_score, cs.raw_score, cs.signal_breakdown
                        ORDER BY cs.z_score DESC
                        LIMIT 10
                    """),
                    {
                        "threshold": aoi.alert_threshold,
                        "geojson": aoi.geojson,
                        "aoi_id": str(aoi.id),
                        "cooldown": cooldown_cutoff,
                    },
                )
                cells = breaching.fetchall()

                if not cells:
                    continue

                # Fire alerts for breaching cells
                for cell in cells:
                    alert_id = str(uuid.uuid4())
                    await session.execute(
                        text("""
                            INSERT INTO alerts (id, aoi_id, trigger_type, trigger_detail,
                                                h3_index, z_score, fired_at, email_sent)
                            VALUES (:id, :aoi_id, 'zscore_threshold',
                                    CAST(:detail AS jsonb),
                                    :h3_index, :z_score, NOW(), :email_sent)
                        """),
                        {
                            "id": alert_id,
                            "aoi_id": str(aoi.id),
                            "detail": f'{{"threshold": {aoi.alert_threshold}, "breakdown": {cell.signal_breakdown or "{}"}}}',
                            "h3_index": cell.h3_index,
                            "z_score": cell.z_score,
                            "email_sent": aoi.alert_email and bool(settings.resend_api_key),
                        },
                    )
                    alerts_fired += 1

                await session.commit()

                # Send email if opted in
                if aoi.alert_email and aoi.email and settings.resend_api_key:
                    sent = _send_alert_email(
                        to_email=aoi.email,
                        aoi_name=aoi.name,
                        username=aoi.github_username,
                        cells=cells,
                        threshold=aoi.alert_threshold,
                    )
                    if sent:
                        emails_sent += 1

    finally:
        await engine.dispose()

    logger.info(
        "Alert check complete: %d AOIs checked, %d alerts fired, %d emails sent",
        aois_checked, alerts_fired, emails_sent,
    )
    return {
        "aois_checked": aois_checked,
        "alerts_fired": alerts_fired,
        "emails_sent": emails_sent,
    }


def _send_alert_email(
    to_email: str,
    aoi_name: str,
    username: str,
    cells: list,
    threshold: float,
) -> bool:
    """Send an alert notification email via Resend.

    Args:
        to_email: Recipient email address.
        aoi_name: Name of the AOI that triggered.
        username: GitHub username for greeting.
        cells: List of breaching cell rows (h3_index, z_score, signal_breakdown).
        threshold: The AOI's configured threshold.

    Returns:
        True if email sent successfully, False otherwise.
    """
    try:
        resend.api_key = settings.resend_api_key

        cell_rows = "\n".join(
            f"  - Cell {c.h3_index}: Z={c.z_score:.2f}σ"
            for c in cells[:5]
        )

        resend.Emails.send({
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": f"Echelon Alert: {html.escape(aoi_name)} — {len(cells)} cell(s) above {threshold}σ",
            "html": f"""
                <div style="font-family: -apple-system, sans-serif; max-width: 500px;">
                    <h2 style="color: #ef4444;">Echelon Convergence Alert</h2>
                    <p>Hi {html.escape(username)},</p>
                    <p>Your AOI <strong>{html.escape(aoi_name)}</strong> has <strong>{len(cells)} H3 cell(s)</strong>
                       exceeding your Z-score threshold of <strong>{threshold}σ</strong>:</p>
                    <pre style="background: #1f2937; color: #d1d5db; padding: 12px; border-radius: 6px; font-size: 13px;">{html.escape(str(cell_rows))}</pre>
                    <p><a href="https://echelon-geoint.org" style="color: #3b82f6;">Open Echelon Dashboard</a></p>
                    <p style="color: #6b7280; font-size: 12px;">
                        You're receiving this because you enabled email alerts for this AOI.
                        Manage your alert settings in the Echelon dashboard.
                    </p>
                </div>
            """,
        })
        logger.info("Alert email sent to %s for AOI '%s'", to_email[:3] + "***", aoi_name)
        return True
    except Exception:
        logger.warning("Failed to send alert email for AOI '%s'", aoi_name, exc_info=True)
        return False
