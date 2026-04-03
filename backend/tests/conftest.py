"""
Test configuration — set required env vars before any app imports.
"""
import os

# Set dummy env vars so app.config.Settings() doesn't fail during import.
# These are never used for real connections in unit tests.
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars!!")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
