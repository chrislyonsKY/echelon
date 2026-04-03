"""
Echelon Application Configuration

All settings sourced from environment variables via pydantic-settings.
Never hardcode values here — use .env or Railway environment variables.
"""
import logging
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_config_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("secret_key")
    @classmethod
    def secret_key_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("secret_key must be at least 32 characters")
        # Reject placeholder values that ship in .env.example
        _blocked = {"change_me", "replace_me", "your_secret", "example", "placeholder", "xxxxxxxx"}
        if any(p in v.lower() for p in _blocked):
            raise ValueError("secret_key contains a placeholder value — generate a real key: python -c 'import secrets; print(secrets.token_hex(32))'")
        return v

    # ── Application ──────────────────────────────────────────────────────────
    secret_key: str
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:80", "https://echelon-geoint.org", "https://www.echelon-geoint.org"]
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

    # ── NASA FIRMS (thermal anomalies) ──────────────────────────────────────────
    firms_map_key: str = ""

    # ── AISStream (real-time AIS) ────────────────────────────────────────────────
    aisstream_api_key: str = ""

    # ── YouTube Data API ──────────────────────────────────────────────────────
    youtube_api_key: str = ""

    # ── Ollama (self-hosted LLM) ────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"

    # ── Translation / multilingual ───────────────────────────────────────────
    translation_backend: str = ""
    translation_target_language: str = "en"

    # ── Convergence scorer ────────────────────────────────────────────────────
    convergence_alert_threshold: float = 2.0
    convergence_baseline_days: int = 365

    # ── Feature flags ─────────────────────────────────────────────────────────
    enable_eo_change_detection: bool = True
    enable_server_side_byok_storage: bool = True

    def warn_missing_optional(self) -> None:
        """Log warnings for missing optional integrations so operators know what's disabled."""
        optional_pairs = [
            (self.github_client_id and self.github_client_secret, "GitHub OAuth"),
            (self.gfw_api_token, "Global Fishing Watch ingestion"),
            (self.newsdata_api_key, "NewsData.io ingestion"),
            (self.firms_map_key, "NASA FIRMS ingestion"),
            (self.aisstream_api_key, "AISStream ingestion"),
            (self.resend_api_key and self.resend_from_email, "Email alerts via Resend"),
            (self.byok_encryption_key, "Server-side BYOK key storage"),
        ]
        for present, label in optional_pairs:
            if not present:
                _config_logger.warning("Optional integration disabled: %s (key not set)", label)


settings = Settings()
settings.warn_missing_optional()
