# Observability

What to monitor on the Echelon droplet and how to check it.

## Container Health

```bash
docker compose ps                    # All containers should show "Up"
docker compose logs --tail=50 api    # Check for startup errors
docker compose logs --tail=50 worker # Check for task failures
```

## Disk Usage

PostGIS WAL and Docker images are the two growth drivers.

```bash
df -h /                              # Overall disk usage
du -sh /var/lib/docker/              # Docker storage
docker system df                     # Docker breakdown (images, containers, volumes)
docker compose exec db psql -U echelon -c "SELECT pg_database_size('echelon');"
```

**Alert threshold:** > 80% disk usage. Run `docker system prune` for images; for PostGIS, check signal retention (365-day trim runs daily via Celery beat).

## Redis Memory

```bash
docker compose exec redis redis-cli INFO memory | grep used_memory_human
docker compose exec redis redis-cli INFO memory | grep maxmemory
```

Max is set to 256MB with `allkeys-lru` eviction. If `used_memory` is near `maxmemory`, keys are being evicted — check if the Celery result backend is filling up.

## PostgreSQL

```bash
# Connection count
docker compose exec db psql -U echelon -c "SELECT count(*) FROM pg_stat_activity;"

# Table sizes
docker compose exec db psql -U echelon -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"

# Active locks (check for blocking)
docker compose exec db psql -U echelon -c "SELECT pid, state, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start;"
```

## Celery Worker Lag

Flower dashboard (internal): `http://localhost:5555` or via Nginx at `/flower/`.

```bash
# Check active/reserved/scheduled tasks
docker compose exec worker celery -A app.workers.celery_app inspect active
docker compose exec worker celery -A app.workers.celery_app inspect reserved

# Queue length (tasks waiting)
docker compose exec redis redis-cli LLEN celery
```

**Alert threshold:** Queue length > 100 means workers can't keep up. Consider increasing `--concurrency`.

## Failed Ingestion Tasks

```bash
# Recent task failures in worker logs
docker compose logs worker --since=1h 2>&1 | grep -i "error\|exception\|traceback" | tail -20

# Check beat schedule is running
docker compose logs beat --since=1h | tail -10
```

## API Response Times

```bash
# Quick smoke test of key endpoints
time curl -s http://localhost:8000/api/health/summary > /dev/null
time curl -s "http://localhost:8000/api/convergence/tiles?resolution=5" > /dev/null
time curl -s "http://localhost:8000/api/signals/?bbox=30,40,40,50" > /dev/null
```

**Alert threshold:** > 5s for any endpoint. Check PostGIS query plans and index usage.

## Nginx

```bash
docker compose logs nginx --since=1h | grep " 5[0-9][0-9] " | wc -l  # 5xx count
docker compose logs nginx --since=1h | grep " 4[0-9][0-9] " | wc -l  # 4xx count
```

## Automated Health Check

Add to crontab on the droplet:

```bash
# Every 5 minutes — check API is responding
*/5 * * * * curl -sf http://localhost:8000/api/health/summary > /dev/null || echo "Echelon API down" | mail -s "ALERT" you@example.com
```
