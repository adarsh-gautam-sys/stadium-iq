"""Centralised application configuration using pydantic-settings.

All environment variables are declared here with explicit types and defaults.
Import ``settings`` from this module — never call ``os.getenv`` anywhere else.

Design decisions:
- ``extra="ignore"`` prevents crashes when the environment contains unrelated vars.
- ``case_sensitive=False`` accepts UPPER_CASE env var names (standard on Cloud Run).
- ``allowed_origins`` is an explicit list — wildcard CORS is never permitted.
- ``max_concurrent_llm_calls=3`` prevents 429 errors on free-tier Gemini quotas.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Gemini AI ──────────────────────────────────────────────────────────────
    gemini_api_key: str = ""              # Empty string → deterministic fallback
    gemini_model: str = "gemini-2.0-flash"

    # ── Google Cloud ───────────────────────────────────────────────────────────
    google_cloud_project: str = ""
    google_cloud_region: str = "us-central1"
    firestore_enabled: bool = False

    # ── Storage ────────────────────────────────────────────────────────────────
    local_data_dir: str = ""             # Override for tests (avoids WinError 5)

    # ── CORS — explicit list, never "*" ────────────────────────────────────────
    allowed_origins: list[str] = [
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
    ]
    port: int = 8080
    log_level: str = "INFO"

    # ── Concurrency ────────────────────────────────────────────────────────────
    max_concurrent_llm_calls: int = 3    # Semaphore cap — prevents Gemini 429s

    # ── Cache ──────────────────────────────────────────────────────────────────
    cache_max_size: int = 256
    cache_ttl_seconds: int = 3600        # 1 hour — appropriate for match-day usage

    # ── StadiumIQ domain knobs ─────────────────────────────────────────────────
    default_language: str = "en"
    crowd_amber_threshold: float = 70.0  # % occupancy → amber alert
    crowd_red_threshold: float = 85.0    # % occupancy → red alert


settings = Settings()
