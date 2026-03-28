"""
Echelon Celery Beat Schedule

Defines all periodic ingestion and maintenance tasks.
See ai-dev/architecture.md — Ingestion Schedule for rationale on frequencies.
"""
from celery.schedules import crontab

BEAT_SCHEDULE = {
    # ── Data ingestion ────────────────────────────────────────────────────────
    "ingest-gfw-events-every-12h": {
        "task": "app.workers.tasks.ingest_gfw.run",
        "schedule": crontab(minute=30, hour="*/12"),
    },
    "ingest-gdelt-every-15m": {
        "task": "app.workers.tasks.ingest_gdelt.run",
        "schedule": crontab(minute="*/15"),
    },
    "ingest-newsdata-every-4h": {
        "task": "app.workers.tasks.ingest_newsdata.run",
        "schedule": crontab(minute=15, hour="*/4"),
    },
    "ingest-osm-daily": {
        "task": "app.workers.tasks.ingest_osm.run",
        "schedule": crontab(minute=0, hour=2),  # 2am UTC
    },
    "ingest-opensky-every-30m": {
        "task": "app.workers.tasks.ingest_opensky.run",
        "schedule": crontab(minute="*/30"),
    },
    "ingest-osint-scrape-every-2h": {
        "task": "app.workers.tasks.ingest_osint_scrape.run",
        "schedule": crontab(minute=20, hour="*/2"),
    },
    "ingest-aisstream-every-30m": {
        "task": "app.workers.tasks.ingest_aisstream.run",
        "schedule": crontab(minute="*/30"),
    },
    "ingest-firms-every-6h": {
        "task": "app.workers.tasks.ingest_firms.run",
        "schedule": crontab(minute=10, hour="*/6"),
    },
    "trigger-sentinel2-daily": {
        "task": "app.workers.tasks.ingest_sentinel2.trigger_scene_jobs",
        "schedule": crontab(minute=0, hour=3),  # 3am UTC
    },
    # ── Convergence scoring ───────────────────────────────────────────────────
    "recompute-convergence-every-15m": {
        "task": "app.workers.tasks.convergence.recompute_all",
        "schedule": crontab(minute="*/15"),
    },
    # ── Alerts ────────────────────────────────────────────────────────────────
    "check-aoi-alerts-every-15m": {
        "task": "app.workers.tasks.alerts.check_all_aois",
        "schedule": crontab(minute="*/15"),
    },
    # ── Event clustering ──────────────────────────────────────────────────
    "cluster-events-every-15m": {
        "task": "app.workers.tasks.clustering.cluster_events",
        "schedule": crontab(minute="3,18,33,48"),  # Offset from convergence scoring
    },
    # ── Maintenance ───────────────────────────────────────────────────────────
    "trim-old-signals-daily": {
        "task": "app.workers.tasks.maintenance.trim_old_signals",
        "schedule": crontab(minute=0, hour=4),  # 4am UTC
    },
}
