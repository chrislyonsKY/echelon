# Observability Guide

What to monitor on the Echelon droplet and how to check it. All commands assume you are SSH'd into the droplet in the `/opt/echelon` directory.

---

## 1. Disk Usage

PostGIS WAL files, Docker images, and backup files are the primary disk consumers.

```bash
# Overall disk usage
df -h /

# Docker disk usage breakdown (images, containers, volumes, build cache)
docker system df

# Largest Docker volumes
docker system df -v | grep -A 50 "VOLUME NAME"

# PostGIS data directory size
docker compose exec postgres du -sh /var/lib/postgresql/data/

# WAL file accumulation (should not grow unbounded)
docker compose exec postgres du -sh /var/lib/postgresql/data/pg_wal/

# Backup directory size
du -sh /opt/echelon/backups/

# Clean up dangling images and build cache
docker system prune -f
```

**Alert threshold:** Disk usage above 80%. At 90%, PostGIS may stop accepting writes.

---

## 2. Redis Memory

Redis holds the Celery task queue, result backend, and application cache.

```bash
# Memory usage summary
docker compose exec redis redis-cli INFO memory | grep -E "used_memory_human|maxmemory_human|mem_fragmentation_ratio"

# Key count by database
docker compose exec redis redis-cli INFO keyspace

# Largest keys (top 20 by memory)
docker compose exec redis redis-cli --bigkeys

# Monitor commands in real time (Ctrl+C to stop)
docker compose exec redis redis-cli MONITOR
```

**Alert threshold:** `used_memory` exceeding 75% of available RAM allocated to the Redis container. Check `maxmemory` policy is set to `allkeys-lru`.

---

## 3. Celery Worker Health

### Flower Dashboard

Flower runs on port 5555 and provides a web UI for task monitoring.

```bash
# Check Flower is running
curl -s -o /dev/null -w "%{http_code}" http://localhost:5555/

# Open in browser (via SSH tunnel if needed)
# ssh -L 5555:localhost:5555 echelon-droplet
```

### CLI Checks

```bash
# Are workers alive?
docker compose exec celery-worker celery -A app.workers.celery_app inspect ping

# Active tasks right now
docker compose exec celery-worker celery -A app.workers.celery_app inspect active

# Queue depth (tasks waiting to be picked up)
docker compose exec redis redis-cli LLEN celery

# Reserved (prefetched) tasks
docker compose exec celery-worker celery -A app.workers.celery_app inspect reserved

# Registered task types
docker compose exec celery-worker celery -A app.workers.celery_app inspect registered
```

**Alert threshold:** Queue depth (`LLEN celery`) above 100 sustained for more than 10 minutes indicates worker lag.

---

## 4. Failed Ingestion Tasks

```bash
# Recent task failures in worker logs
docker compose logs --since 1h celery-worker | grep -i "error\|exception\|traceback\|failed"

# Celery Beat schedule check (is beat scheduling tasks?)
docker compose logs --since 1h celery-beat | tail -30

# Count failed tasks via Flower API
curl -s http://localhost:5555/api/tasks?state=FAILURE | python3 -m json.tool | head -40

# Check specific task types
docker compose logs --since 6h celery-worker | grep -c "ingest_acled"
docker compose logs --since 6h celery-worker | grep -c "ingest_gdelt"
docker compose logs --since 6h celery-worker | grep -c "ingest_firms"
docker compose logs --since 6h celery-worker | grep -c "convergence"
```

**Alert threshold:** Any ingestion task failing 3 or more consecutive times. Check the external API status (ACLED, GFW, GDELT) for outages.

---

## 5. API Response Times

```bash
# Health endpoint (should respond in < 100ms)
curl -o /dev/null -s -w "HTTP %{http_code} in %{time_total}s\n" http://localhost/api/health

# Convergence endpoint (should respond in < 2s)
curl -o /dev/null -s -w "HTTP %{http_code} in %{time_total}s\n" \
  "http://localhost/api/convergence?res=5"

# Signals endpoint
curl -o /dev/null -s -w "HTTP %{http_code} in %{time_total}s\n" \
  "http://localhost/api/signals/acled?days=7"

# Nginx access log (recent 5xx errors)
docker compose logs --tail 200 nginx | grep " 5[0-9][0-9] " | wc -l

# Slow queries in PostgreSQL (if pg_stat_statements is enabled)
docker compose exec postgres psql -U echelon -d echelon \
  -c "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

**Alert threshold:** Health endpoint above 500ms or convergence endpoint above 5s.

---

## 6. Container Health

```bash
# All container statuses
docker compose ps

# Container resource usage (CPU, memory, net I/O)
docker stats --no-stream

# Restart counts (high restart count = crash loop)
docker compose ps --format "table {{.Name}}\t{{.Status}}"

# Individual container logs (last 50 lines)
docker compose logs --tail 50 backend
docker compose logs --tail 50 celery-worker
docker compose logs --tail 50 celery-beat
docker compose logs --tail 50 postgres
docker compose logs --tail 50 redis
docker compose logs --tail 50 nginx

# Check for OOM kills
docker inspect $(docker compose ps -q celery-worker) | grep -i oomkilled
```

**Alert threshold:** Any container in `restarting` state, or OOMKilled = true.

---

## 7. PostgreSQL Health

```bash
# Connection count (max_connections default is 100)
docker compose exec postgres psql -U echelon -d echelon \
  -c "SELECT count(*) FROM pg_stat_activity;"

# Database size
docker compose exec postgres psql -U echelon -d echelon \
  -c "SELECT pg_size_pretty(pg_database_size('echelon'));"

# Table sizes
docker compose exec postgres psql -U echelon -d echelon \
  -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"

# Long-running queries (> 30 seconds)
docker compose exec postgres psql -U echelon -d echelon \
  -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '30 seconds';"
```

---

## Quick Health Check Script

Save as `/opt/echelon/healthcheck.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== Disk ==="
df -h / | tail -1

echo "=== Containers ==="
docker compose -f /opt/echelon/docker-compose.yml ps --format "table {{.Name}}\t{{.Status}}"

echo "=== Redis Memory ==="
docker compose -f /opt/echelon/docker-compose.yml exec -T redis redis-cli INFO memory | grep used_memory_human

echo "=== Celery Queue ==="
QLEN=$(docker compose -f /opt/echelon/docker-compose.yml exec -T redis redis-cli LLEN celery)
echo "Queue depth: ${QLEN}"

echo "=== API Health ==="
curl -o /dev/null -s -w "HTTP %{http_code} in %{time_total}s\n" http://localhost/api/health

echo "=== Recent Errors (last hour) ==="
ERROR_COUNT=$(docker compose -f /opt/echelon/docker-compose.yml logs --since 1h celery-worker 2>&1 | grep -ci "error\|exception" || true)
echo "Error count: ${ERROR_COUNT}"
```

```bash
chmod +x /opt/echelon/healthcheck.sh
```

### Automated Health Check (Cron)

```bash
# Every 5 minutes -- check API is responding
*/5 * * * * curl -sf http://localhost/api/health > /dev/null || echo "Echelon API down" | mail -s "ALERT: Echelon" you@example.com
```
