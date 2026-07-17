"""Shared pytest fixtures and environment isolation for StadiumIQ tests.

Design decisions:
- ``_isolate_env`` autouse fixture ensures every test runs with a clean env:
  no GEMINI_API_KEY (forces deterministic fallback), no FIRESTORE_ENABLED,
  and LOCAL_DATA_DIR pointing to a project-local path (avoids WinError 5).
- ``_TEST_DATA_DIR`` uses a project-local path — not %TEMP% — because Windows
  sandboxed environments may deny access to the system temp directory.
- The ``client`` fixture returns a synchronous TestClient, which is appropriate
  for testing FastAPI apps without running a real async server.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Use project-local path — avoids Windows WinError 5 on %TEMP%
_TEST_DATA_DIR = Path(__file__).resolve().parent.parent / ".pytest_tmp_data"

# ── Minimal valid payload — used across all test files ────────────────────────
SAMPLE_PAYLOAD: dict = {
    "profile": {
        "name": "TestUser",
        "role": "fan",
        "language": "en",
        "mobility_aid": "none",
        "visual_impairment": False,
        "hearing_impairment": False,
        "party_size": 1,
    },
    "venue": {
        "venue": "sofi_stadium",
        "section": "114",
        "current_zone": "Gate A",
        "match_phase": "arrival",
        "crowd_density_pct": 60.0,
    },
    "navigation": {
        "destination": "seat",
        "destination_detail": "Section 114, Row C, Seat 4",
        "requires_elevator": False,
        "requires_accessible_route": False,
    },
    "transport": {
        "transport_mode": "shuttle",
        "direction": "arriving",
        "distance_km": 3.0,
    },
}

HIGH_IMPACT_PAYLOAD: dict = {
    "profile": {
        "name": "HighImpactUser",
        "role": "staff",
        "language": "en",
        "mobility_aid": "none",
        "visual_impairment": False,
        "hearing_impairment": False,
        "party_size": 1,
    },
    "venue": {
        "venue": "metlife_stadium",
        "section": "OPS",
        "current_zone": "North Concourse",
        "match_phase": "post_match",
        "crowd_density_pct": 92.0,
    },
    "navigation": {
        "destination": "exit",
        "destination_detail": "",
        "requires_elevator": False,
        "requires_accessible_route": False,
    },
    "transport": {
        "transport_mode": "car",
        "direction": "departing",
        "distance_km": 5.0,
    },
}


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate every test from real env vars and clean up tmp files after."""
    _TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOCAL_DATA_DIR", str(_TEST_DATA_DIR))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("FIRESTORE_ENABLED", raising=False)
    yield
    for f in _TEST_DATA_DIR.glob("*.jsonl"):
        f.unlink(missing_ok=True)


@pytest.fixture()
def client() -> TestClient:
    """Return a synchronous TestClient for the FastAPI app."""
    return TestClient(app)
