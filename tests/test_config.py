"""Unit tests for StadiumIQ configuration (config.py)."""
from __future__ import annotations

import pytest

from app.config import settings


def test_default_gemini_model() -> None:
    """Default Gemini model is gemini-2.0-flash."""
    assert settings.gemini_model == "gemini-2.0-flash"


def test_default_allowed_origins_contains_localhost() -> None:
    """Default allowed origins include localhost."""
    assert any("localhost" in o for o in settings.allowed_origins)


def test_max_concurrent_llm_calls_default() -> None:
    """Default concurrent LLM call limit is 3."""
    assert settings.max_concurrent_llm_calls == 3


def test_gemini_api_key_defaults_to_empty() -> None:
    """Default Gemini API key is empty (triggers fallback mode)."""
    assert settings.gemini_api_key == ""


def test_firestore_disabled_by_default() -> None:
    """Firestore is disabled by default (local JSONL fallback active)."""
    assert settings.firestore_enabled is False


def test_cache_ttl_default() -> None:
    """Default cache TTL is 3600 seconds (1 hour)."""
    assert settings.cache_ttl_seconds == 3600


def test_crowd_amber_threshold_default() -> None:
    """Amber alert threshold is 70% by default."""
    assert settings.crowd_amber_threshold == 70.0


def test_crowd_red_threshold_default() -> None:
    """Red alert threshold is 85% by default."""
    assert settings.crowd_red_threshold == 85.0


def test_env_var_overrides_gemini_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """GEMINI_MODEL env var overrides the default model setting."""
    import pytest
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    from importlib import reload
    import app.config as conf
    reload(conf)
    assert conf.settings.gemini_model == "gemini-2.5-pro"
    # Reset after test
    reload(conf)


def test_port_default() -> None:
    """Default port is 8080 (Cloud Run standard)."""
    assert settings.port == 8080
