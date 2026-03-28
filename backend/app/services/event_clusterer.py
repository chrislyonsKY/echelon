"""
Event Clustering Service

Groups spatiotemporally proximate signals into analyst-facing events.
Clustering logic:
    1. Query recent signals (last 72h) grouped by H3 res-7 cell
    2. Within each cell, group signals into 48h time windows
    3. Compute corroboration: count distinct provenance families
    4. Upsert events — merge into existing events if overlap detected

Called by the `cluster_events` Celery task after convergence scoring.
"""
import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Source → provenance family mapping (single source of truth)
SOURCE_FAMILY_MAP: dict[str, str] = {
    "gfw":              "official_sensor",
    "opensky":          "official_sensor",
    "firms":            "official_sensor",
    "sentinel2":        "official_sensor",
    "gdelt":            "curated_dataset",
    "acled":            "curated_dataset",
    "newsdata":         "news_media",
    "osint_scrape":     "news_media",
    "osm":              "open_source",
    "aisstream":        "crowd_sourced",
}

# Cluster window: signals within this many hours of each other merge
CLUSTER_WINDOW_HOURS: int = 48

# Minimum signals to form an event (prevents noise)
MIN_SIGNALS_FOR_EVENT: int = 2

# How far back to scan for new/updated events
SCAN_WINDOW_HOURS: int = 72

# Event type inference from dominant signal types
SIGNAL_TYPE_TO_EVENT_TYPE: dict[str, str] = {
    "gfw_ais_gap":           "maritime_anomaly",
    "gfw_loitering":         "maritime_anomaly",
    "ais_position":          "maritime_anomaly",
    "gdelt_conflict":        "conflict",
    "gdelt_gkg_threat":      "conflict",
    "acled_battle":          "conflict",
    "acled_explosion":       "conflict",
    "acled_other":           "civil_unrest",
    "sentinel2_nbr_anomaly": "environmental_change",
    "firms_thermal":         "environmental_change",
    "osm_change":            "infrastructure_change",
    "opensky_military":      "military_activity",
    "newsdata_article":      "media_report",
    "osint_scrape":          "media_report",
    "natural_hazard":        "natural_event",
}


def _confirmation_status(corroboration_count: int) -> str:
    """Derive confirmation status from the number of distinct source families."""
    if corroboration_count >= 3:
        return "corroborated"
    elif corroboration_count == 2:
        return "multi_source"
    elif corroboration_count == 1:
        return "single_source"
    return "unconfirmed"


def _infer_event_type(signal_types: list[str]) -> str:
    """Infer the dominant event type from the signal type distribution."""
    type_counts: dict[str, int] = defaultdict(int)
    for st in signal_types:
        event_type = SIGNAL_TYPE_TO_EVENT_TYPE.get(st, "unknown")
        type_counts[event_type] += 1
    return max(type_counts, key=type_counts.get) if type_counts else "unknown"


def _generate_title(event_type: str, signal_count: int, families: list[str]) -> str:
    """Generate a descriptive title for an event."""
    type_labels = {
        "maritime_anomaly": "Maritime Anomaly",
        "conflict": "Conflict Event",
        "civil_unrest": "Civil Unrest",
        "environmental_change": "Environmental Change",
        "infrastructure_change": "Infrastructure Change",
        "military_activity": "Military Activity",
        "media_report": "Media Report Cluster",
        "natural_event": "Natural Event",
        "unknown": "Activity Cluster",
    }
    label = type_labels.get(event_type, "Activity Cluster")
    family_count = len(families)
    return f"{label} ({signal_count} signals, {family_count} source{'s' if family_count != 1 else ''})"


async def cluster_signals(session: AsyncSession) -> int:
    """Cluster recent signals into events.

    Returns the number of events created or updated.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=SCAN_WINDOW_HOURS)

    # Fetch recent signals grouped by H3 res-7 cell
    result = await session.execute(
        text("""
            SELECT id, source, signal_type, h3_index_7,
                   ST_Y(location::geometry) AS lat,
                   ST_X(location::geometry) AS lon,
                   occurred_at, provenance_family
            FROM signals
            WHERE occurred_at >= :cutoff
            ORDER BY h3_index_7, occurred_at
        """),
        {"cutoff": cutoff},
    )
    rows = result.fetchall()

    if not rows:
        logger.info("No recent signals to cluster")
        return 0

    # Group by H3 res-7 cell
    cells: dict[str, list] = defaultdict(list)
    for row in rows:
        cells[row.h3_index_7].append(row)

    events_upserted = 0

    for h3_cell, cell_signals in cells.items():
        if len(cell_signals) < MIN_SIGNALS_FOR_EVENT:
            continue

        # Sub-cluster within 48h windows
        clusters = _time_cluster(cell_signals)

        for cluster in clusters:
            if len(cluster) < MIN_SIGNALS_FOR_EVENT:
                continue

            signal_ids = [row.id for row in cluster]
            signal_types = [row.signal_type for row in cluster]
            sources = [row.source for row in cluster]

            # Compute centroid
            avg_lat = sum(row.lat for row in cluster) / len(cluster)
            avg_lon = sum(row.lon for row in cluster) / len(cluster)

            first_seen = min(row.occurred_at for row in cluster)
            last_seen = max(row.occurred_at for row in cluster)

            # Determine provenance families
            families = list(set(
                row.provenance_family or SOURCE_FAMILY_MAP.get(row.source, "unknown")
                for row in cluster
            ))
            families = [f for f in families if f != "unknown"]
            corroboration_count = len(families)

            event_type = _infer_event_type(signal_types)
            confirmation = _confirmation_status(corroboration_count)
            title = _generate_title(event_type, len(cluster), families)

            # Check if an event already exists for this cell + time window
            existing = await session.execute(
                text("""
                    SELECT id FROM events
                    WHERE h3_index_7 = :h3
                      AND first_seen <= :last_seen
                      AND last_seen >= :first_seen
                    LIMIT 1
                """),
                {"h3": h3_cell, "first_seen": first_seen, "last_seen": last_seen},
            )
            existing_row = existing.fetchone()

            if existing_row:
                event_id = existing_row.id

                # Update existing event
                await session.execute(
                    text("""
                        UPDATE events SET
                            title = :title,
                            event_type = :event_type,
                            location = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                            first_seen = LEAST(first_seen, :first_seen),
                            last_seen = GREATEST(last_seen, :last_seen),
                            source_families = :source_families,
                            corroboration_count = :corroboration_count,
                            confirmation_status = :confirmation,
                            signal_count = :signal_count,
                            updated_at = NOW()
                        WHERE id = :event_id
                    """),
                    {
                        "event_id": event_id,
                        "title": title,
                        "event_type": event_type,
                        "lat": avg_lat,
                        "lon": avg_lon,
                        "first_seen": first_seen,
                        "last_seen": last_seen,
                        "source_families": families,
                        "corroboration_count": corroboration_count,
                        "confirmation": confirmation,
                        "signal_count": len(cluster),
                    },
                )
            else:
                event_id = uuid.uuid4()

                await session.execute(
                    text("""
                        INSERT INTO events (id, title, event_type, location, h3_index_7,
                                           first_seen, last_seen, source_families,
                                           corroboration_count, confirmation_status,
                                           signal_count)
                        VALUES (:id, :title, :event_type,
                                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                                :h3, :first_seen, :last_seen, :source_families,
                                :corroboration_count, :confirmation, :signal_count)
                    """),
                    {
                        "id": event_id,
                        "title": title,
                        "event_type": event_type,
                        "lat": avg_lat,
                        "lon": avg_lon,
                        "h3": h3_cell,
                        "first_seen": first_seen,
                        "last_seen": last_seen,
                        "source_families": families,
                        "corroboration_count": corroboration_count,
                        "confirmation": confirmation,
                        "signal_count": len(cluster),
                    },
                )

            # Upsert junction rows (idempotent)
            for sig_id in signal_ids:
                await session.execute(
                    text("""
                        INSERT INTO event_signals (event_id, signal_id)
                        VALUES (:event_id, :signal_id)
                        ON CONFLICT DO NOTHING
                    """),
                    {"event_id": event_id, "signal_id": sig_id},
                )

            events_upserted += 1

    await session.commit()
    logger.info("Clustered %d events from %d signals", events_upserted, len(rows))
    return events_upserted


def _time_cluster(signals: list) -> list[list]:
    """Group signals into clusters where consecutive signals are within CLUSTER_WINDOW_HOURS.

    Uses a simple greedy approach: start a new cluster when the gap
    between consecutive signals exceeds the window.
    """
    if not signals:
        return []

    sorted_signals = sorted(signals, key=lambda s: s.occurred_at)
    clusters: list[list] = [[sorted_signals[0]]]

    for sig in sorted_signals[1:]:
        last_in_cluster = clusters[-1][-1]
        gap = (sig.occurred_at - last_in_cluster.occurred_at).total_seconds() / 3600.0

        if gap <= CLUSTER_WINDOW_HOURS:
            clusters[-1].append(sig)
        else:
            clusters.append([sig])

    return clusters
