# Release Process

Step-by-step checklist for cutting a new Echelon release and deploying to the DigitalOcean droplet.

---

## Pre-Release Checklist

- [ ] All changes are merged to `main`
- [ ] CI checks pass (lint, type check, tests)
- [ ] Local `docker compose up --build` runs cleanly
- [ ] No unresolved critical issues in the tracker

---

## 1. Version Bump

Update the version string in `backend/app/main.py`:

```python
app = FastAPI(
    title="Echelon API",
    version="X.Y.Z",  # <-- bump this
)
```

Follow semver:
- **Major** (X) -- breaking API changes, schema migrations that drop data
- **Minor** (Y) -- new features, new data sources, new endpoints
- **Patch** (Z) -- bug fixes, dependency updates, config changes

## 2. Update CHANGELOG

Add an entry at the top of `CHANGELOG.md`:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Fixed
- ...
```

## 3. Commit and Tag

```bash
git add backend/app/main.py CHANGELOG.md
git commit -m "Release vX.Y.Z"
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin main --tags
```

## 4. Build Docker Images

On the droplet (or locally if pushing to a registry):

```bash
ssh echelon-droplet
cd /opt/echelon
git pull origin main

# Build all images
docker compose build --no-cache
```

## 5. Deploy

```bash
# Take a pre-deploy backup (see docs/backup-restore.md)
/opt/echelon/backup.sh

# Run any new database migrations
docker compose run --rm backend alembic upgrade head

# Bring up updated services
docker compose up -d

# Verify all containers are running
docker compose ps
```

## 6. Smoke Tests

Run these immediately after deploy:

```bash
# API health
curl -f https://echelon.example.com/api/health

# Convergence endpoint returns data
curl -s https://echelon.example.com/api/convergence?res=5 | python3 -m json.tool | head -20

# Signals endpoint
curl -s https://echelon.example.com/api/signals/acled?days=7 | python3 -m json.tool | head -20

# Frontend loads
curl -s -o /dev/null -w "%{http_code}" https://echelon.example.com/

# Celery workers responding
docker compose exec celery-worker celery -A app.workers.celery_app inspect ping

# Flower dashboard
curl -s -o /dev/null -w "%{http_code}" http://localhost:5555/

# Check for errors in logs (last 5 minutes)
docker compose logs --since 5m --tail 50 backend
docker compose logs --since 5m --tail 50 celery-worker
```

If any smoke test fails, proceed to rollback.

## 7. Rollback Procedure

### Quick Rollback (Previous Image)

If the issue is in application code and the database migration is backward-compatible:

```bash
# Check the previous git tag
git log --oneline --tags -5

# Roll back to previous version
git checkout vPREVIOUS.TAG
docker compose build --no-cache
docker compose up -d
```

### Full Rollback (Including Database)

If the new release included a database migration that must be reversed:

```bash
# 1. Stop application services
docker compose stop backend celery-worker celery-beat

# 2. Downgrade the database migration
docker compose run --rm backend alembic downgrade -1

# 3. Roll back code
git checkout vPREVIOUS.TAG
docker compose build --no-cache
docker compose up -d
```

### Emergency Rollback (Restore from Backup)

If the database is in an inconsistent state:

```bash
# Follow the restore procedure in docs/backup-restore.md
# Use the pre-deploy backup taken in step 5
```

---

## Post-Release

- [ ] Verify Celery Beat tasks are running on schedule (check Flower)
- [ ] Monitor error rates for 30 minutes
- [ ] Update any external status page or announcements
- [ ] Close the release milestone in the issue tracker
