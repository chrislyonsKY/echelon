# ADR-0002: Celery + Redis for Data Ingestion Pipeline

**Status:** Accepted
**Date:** 2024-12-15

## Context

Echelon ingests data from multiple external sources on recurring schedules:

- ACLED conflict events (daily)
- Global Fishing Watch vessel anomalies (every 6 hours)
- Sentinel-2 COG change detection (daily)
- GDELT news articles (every 15 minutes)
- NewsData.io headlines (hourly)
- OSINT web scraping (hourly)
- FIRMS active fire data (every 6 hours)
- AIS vessel streams (continuous)

Each ingestion task must be:

- **Periodic:** Run on a configurable schedule
- **Retriable:** Automatically retry on transient failures (rate limits, network errors)
- **Idempotent:** Safe to re-run without creating duplicate records
- **Observable:** Visible task status, failure counts, and queue depth

Alternatives evaluated:

| Option | Pros | Cons |
|--------|------|------|
| **Celery + Redis** | Mature, beat scheduler, Flower monitoring, huge ecosystem | Redis as SPOF, memory-bound broker |
| asyncio background tasks | No extra infra, native to FastAPI | No persistence, no retry, no scheduling, lost on restart |
| Dramatiq | Cleaner API, Redis/RabbitMQ backends | Smaller community, no built-in beat scheduler |
| Temporal | Durable execution, versioned workflows | Heavy infra (Temporal server + DB), overkill for periodic ingest |

## Decision

We will use **Celery 5.4+** with **Redis 7.2+** as the message broker and result backend for all data ingestion and convergence scoring tasks. Celery Beat handles periodic scheduling. Flower provides the monitoring dashboard.

Docker Compose runs three Celery-related services:

- `celery-worker` -- executes tasks (2 workers, prefork pool)
- `celery-beat` -- schedules periodic tasks (single instance, writes schedule to `/tmp`)
- `flower` -- web UI for task monitoring (port 5555)

## Rationale

- **Maturity:** Celery is the most battle-tested distributed task queue in the Python ecosystem. Edge cases around retries, task routing, and serialization are well-documented.
- **Beat scheduler:** Built-in periodic task scheduling eliminates the need for external cron or a separate scheduler service.
- **Flower monitoring:** Provides real-time task status, worker health, and queue depth without writing custom observability code.
- **Redis reuse:** Redis already serves as the application cache. Using it as the Celery broker avoids adding another infrastructure dependency (e.g., RabbitMQ).
- **Retry policies:** Celery's `autoretry_for`, `retry_backoff`, and `max_retries` decorators handle transient external API failures cleanly.

## Consequences

- **Redis is a single point of failure** for the task queue. If Redis goes down, no tasks are enqueued or processed. Mitigation: Redis persistence (RDB snapshots) is enabled, and the droplet runs Redis with `appendonly yes`.
- **Worker concurrency tuning:** Sentinel-2 COG processing is CPU/memory heavy. The worker pool must be configured with appropriate concurrency limits (`--concurrency=2`) to avoid OOM on the droplet.
- **Beat must be a singleton:** Running multiple Celery Beat instances causes duplicate task scheduling. Docker Compose enforces `deploy.replicas: 1` for the beat service.
- **Task serialization:** All task arguments must be JSON-serializable. No passing ORM objects or database sessions to tasks.
- **Memory pressure:** Redis holds all pending tasks in memory. A sustained ingestion backlog could exhaust Redis memory on a small droplet. Monitoring via `redis-cli info memory` is essential.
