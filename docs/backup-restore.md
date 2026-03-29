# Backup and Restore Procedures

This document covers backup and restore for all stateful components of the Echelon stack running on a DigitalOcean droplet with Docker Compose.

## Stateful Components

| Component | Data Location | Backup Method |
|-----------|--------------|---------------|
| PostgreSQL + PostGIS | Docker volume `echelon_pgdata` | `pg_dump` (custom format) |
| Redis | Docker volume `echelon_redisdata` | RDB snapshot copy |
| Environment config | `/opt/echelon/.env` | File copy |
| Docker volumes | `/var/lib/docker/volumes/` | Volume export |

## Prerequisites

```bash
# All commands assume you are on the droplet as a user with docker access
# Backup directory
sudo mkdir -p /opt/echelon/backups
```

---

## 1. PostgreSQL Backup

### Manual Backup

```bash
# Dump the entire database in custom format (compressed, supports parallel restore)
docker compose exec -T postgres pg_dump \
  -U echelon \
  -d echelon \
  -Fc \
  --no-owner \
  --no-acl \
  > /opt/echelon/backups/pg_backup_$(date +%Y%m%d_%H%M%S).dump

# Verify the backup is valid
pg_restore --list /opt/echelon/backups/pg_backup_*.dump | head -20
```

### Restore PostgreSQL

```bash
# Stop services that write to the database
docker compose stop backend celery-worker celery-beat

# Drop and recreate the database
docker compose exec -T postgres psql -U echelon -c "DROP DATABASE IF EXISTS echelon;"
docker compose exec -T postgres psql -U echelon -c "CREATE DATABASE echelon;"
docker compose exec -T postgres psql -U echelon -d echelon -c "CREATE EXTENSION IF NOT EXISTS postgis;"
docker compose exec -T postgres psql -U echelon -d echelon -c "CREATE EXTENSION IF NOT EXISTS h3;"

# Restore from dump
docker compose exec -T postgres pg_restore \
  -U echelon \
  -d echelon \
  --no-owner \
  --no-acl \
  --single-transaction \
  < /opt/echelon/backups/pg_backup_YYYYMMDD_HHMMSS.dump

# Restart services
docker compose start backend celery-worker celery-beat
```

---

## 2. Redis Backup

### Manual Backup

```bash
# Trigger an RDB snapshot
docker compose exec redis redis-cli BGSAVE

# Wait for save to complete
docker compose exec redis redis-cli LASTSAVE

# Copy the RDB file out of the container
docker compose cp redis:/data/dump.rdb /opt/echelon/backups/redis_$(date +%Y%m%d_%H%M%S).rdb
```

### Restore Redis

```bash
# Stop Redis
docker compose stop redis

# Copy the RDB file into the volume
docker compose cp /opt/echelon/backups/redis_YYYYMMDD_HHMMSS.rdb redis:/data/dump.rdb

# Start Redis (it loads the RDB on startup)
docker compose start redis
```

---

## 3. Environment File Backup

```bash
cp /opt/echelon/.env /opt/echelon/backups/env_$(date +%Y%m%d_%H%M%S).bak
```

Restore: copy the backup file back to `/opt/echelon/.env` and restart all services with `docker compose up -d`.

---

## 4. Docker Volume Backup (Full)

For a complete volume-level backup (useful before major upgrades):

```bash
# PostgreSQL volume
docker run --rm \
  -v echelon_pgdata:/source:ro \
  -v /opt/echelon/backups:/backup \
  alpine tar czf /backup/pgdata_$(date +%Y%m%d).tar.gz -C /source .

# Redis volume
docker run --rm \
  -v echelon_redisdata:/source:ro \
  -v /opt/echelon/backups:/backup \
  alpine tar czf /backup/redisdata_$(date +%Y%m%d).tar.gz -C /source .
```

---

## 5. Automated Daily Backups (Cron)

Create `/opt/echelon/backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/opt/echelon/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=14

# PostgreSQL
docker compose -f /opt/echelon/docker-compose.yml exec -T postgres pg_dump \
  -U echelon -d echelon -Fc --no-owner --no-acl \
  > "${BACKUP_DIR}/pg_backup_${TIMESTAMP}.dump"

# Redis
docker compose -f /opt/echelon/docker-compose.yml exec -T redis redis-cli BGSAVE
sleep 5
docker compose -f /opt/echelon/docker-compose.yml cp redis:/data/dump.rdb \
  "${BACKUP_DIR}/redis_${TIMESTAMP}.rdb"

# Environment file
cp /opt/echelon/.env "${BACKUP_DIR}/env_${TIMESTAMP}.bak"

# Prune old backups
find "${BACKUP_DIR}" -type f -mtime +${RETENTION_DAYS} -delete

echo "[$(date)] Backup completed: ${TIMESTAMP}"
```

Install the cron job:

```bash
chmod +x /opt/echelon/backup.sh

# Run daily at 03:00 UTC
echo "0 3 * * * /opt/echelon/backup.sh >> /var/log/echelon-backup.log 2>&1" \
  | sudo crontab -
```

---

## 6. Restore Verification

After any restore, run these checks to confirm data integrity:

```bash
# 1. Database connectivity and PostGIS extension
docker compose exec -T postgres psql -U echelon -d echelon \
  -c "SELECT PostGIS_Version();"

# 2. Table row counts (compare against pre-backup counts)
docker compose exec -T postgres psql -U echelon -d echelon \
  -c "SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"

# 3. Most recent records exist (should show recent timestamps)
docker compose exec -T postgres psql -U echelon -d echelon \
  -c "SELECT MAX(created_at) FROM events;"

# 4. Alembic migration state is intact
docker compose exec -T postgres psql -U echelon -d echelon \
  -c "SELECT version_num FROM alembic_version;"

# 5. Redis key count
docker compose exec redis redis-cli DBSIZE

# 6. API health check
curl -s http://localhost/api/health | python3 -m json.tool

# 7. Celery workers are processing
docker compose exec celery-worker celery -A app.workers.celery_app inspect ping

# 8. Flower dashboard accessible
curl -s -o /dev/null -w "%{http_code}" http://localhost:5555/
```

If any check fails, review container logs with `docker compose logs <service>` before proceeding.

---

## Offsite Backup (Optional)

For critical deployments, sync backups to DigitalOcean Spaces or another S3-compatible store:

```bash
# Install s3cmd or use aws-cli with DO Spaces endpoint
aws s3 sync /opt/echelon/backups/ \
  s3://echelon-backups/ \
  --endpoint-url https://nyc3.digitaloceanspaces.com
```
