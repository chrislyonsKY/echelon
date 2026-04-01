"""
Echelon Celery Application

Configures Celery with Redis as broker and result backend.
All task modules are autodiscovered from app.workers.tasks.
"""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "echelon",
    broker=settings.celery_broker_url,
    backend=settings.redis_url.replace("redis://", "redis://").replace("/0", "/2"),
    include=[
        "app.workers.tasks.ingest_gfw",
        "app.workers.tasks.ingest_gdelt",
        "app.workers.tasks.ingest_newsdata",
        "app.workers.tasks.ingest_osm",
        "app.workers.tasks.ingest_opensky",
        "app.workers.tasks.ingest_osint_scrape",
        "app.workers.tasks.ingest_aisstream",
        "app.workers.tasks.ingest_firms",
        "app.workers.tasks.ingest_sentinel2",
        "app.workers.tasks.convergence",
        "app.workers.tasks.alerts",
        "app.workers.tasks.maintenance",
        "app.workers.tasks.clustering",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,           # Re-queue on worker crash
    task_reject_on_worker_lost=True,
    result_expires=86400,          # 24 hours
    worker_prefetch_multiplier=1,  # Fair task distribution
    task_soft_time_limit=120,      # Default soft limit — tasks can override
    task_time_limit=180,           # Default hard limit — tasks can override
    worker_max_tasks_per_child=200,  # Recycle workers to prevent memory leaks
)

# Load periodic task schedule for Celery Beat
from app.workers.beat_schedule import BEAT_SCHEDULE  # noqa: E402

celery_app.conf.beat_schedule = BEAT_SCHEDULE
