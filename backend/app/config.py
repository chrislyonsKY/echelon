"""
Echelon Application Configuration

All settings sourced from environment variables via pydantic-settings.
Never hardcode values here — use .env or Railway environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Application ──────────────────────────────────────────────────────────
    secret_key: str
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:80"]
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str

    # ── Redis ────────────────────────────────────────────────────────────────
    redis_url: str
    celery_broker_url: str

    # ── GitHub OAuth ─────────────────────────────────────────────────────────
    github_client_id: str = ""
    github_client_secret: str = ""

    # ── Data API keys ─────────────────────────────────────────────────────────
    gfw_api_token: str = ""
    newsdata_api_key: str = ""
    newsapi_api_key: str = ""
    gnews_api_key: str = ""

    # ── Email ────────────────────────────────────────────────────────────────
    resend_api_key: str = ""
    resend_from_email: str = ""

    # ── BYOK encryption ───────────────────────────────────────────────────────
    byok_encryption_key: str = ""

    # ── Convergence scorer ────────────────────────────────────────────────────
    convergence_alert_threshold: float = 2.0
    convergence_baseline_days: int = 365

    # ── Feature flags ─────────────────────────────────────────────────────────
    enable_eo_change_detection: bool = True
    enable_server_side_byok_storage: bool = True


settings = Settings()
