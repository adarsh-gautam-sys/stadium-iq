"""Unit tests for the StadiumIQ caching layer (cache.py)."""
from __future__ import annotations

import pytest

from app.cache import (
    cache_size,
    get_cached,
    make_cache_key,
    preseed_cache,
    set_cached,
)
from app.models import AssistRequest, AssistResponse, CrowdStatus, NavigationGuidance


def _make_req(**kwargs: object) -> AssistRequest:
    base = {
        "profile": {"name": "CacheTest", "role": "fan", "language": "en",
                    "mobility_aid": "none", "visual_impairment": False,
                    "hearing_impairment": False, "party_size": 1},
        "venue": {"venue": "sofi_stadium", "section": "A1", "current_zone": "Gate A",
                  "match_phase": "arrival", "crowd_density_pct": 50.0},
        "navigation": {"destination": "seat", "destination_detail": "",
                       "requires_elevator": False, "requires_accessible_route": False},
        "transport": {"transport_mode": "shuttle", "direction": "arriving", "distance_km": 2.0},
    }
    base.update(kwargs)
    return AssistRequest.model_validate(base)


def _make_response() -> AssistResponse:
    return AssistResponse(
        navigation=NavigationGuidance(
            route_description="Test route", estimated_minutes=5.0,
            crowd_level="low", alternative_route="Alt route", accessibility_notes="None",
        ),
        crowd_status=CrowdStatus(
            zone="Gate A", occupancy_pct=50.0, level_of_service="B",
            alert="green", recommendation="Move freely.",
        ),
        transport_options=[],
        alerts=[],
        insights=["Insight 1", "Insight 2", "Insight 3"],
        confidence_score=0.80,
        methodology="Test methodology.",
        storage_status="pre_seeded",
    )


def test_make_cache_key_is_deterministic() -> None:
    """Same request always produces the same cache key."""
    req = _make_req()
    assert make_cache_key(req) == make_cache_key(req)


def test_make_cache_key_differs_for_different_requests() -> None:
    """Different requests produce different cache keys."""
    req_a = _make_req()
    req_b = AssistRequest.model_validate({
        "profile": {"name": "Other", "role": "staff", "language": "es",
                    "mobility_aid": "none", "visual_impairment": False,
                    "hearing_impairment": False, "party_size": 2},
        "venue": {"venue": "metlife_stadium", "section": "B2", "current_zone": "Gate D",
                  "match_phase": "post_match", "crowd_density_pct": 90.0},
        "navigation": {"destination": "exit", "destination_detail": "",
                       "requires_elevator": False, "requires_accessible_route": False},
        "transport": {"transport_mode": "car", "direction": "departing", "distance_km": 10.0},
    })
    assert make_cache_key(req_a) != make_cache_key(req_b)


def test_cache_miss_returns_none() -> None:
    """A non-existent key returns None (cache miss)."""
    assert get_cached("nonexistent_key_xyz_99999") is None


def test_cache_set_and_get_roundtrip() -> None:
    """Storing and retrieving a response works correctly."""
    req = _make_req()
    resp = _make_response()
    key = make_cache_key(req)
    set_cached(key, resp)
    assert get_cached(key) == resp


def test_preseed_populates_at_least_three_entries() -> None:
    """preseed_cache() populates at least 3 entries without errors."""
    preseed_cache()
    assert cache_size() >= 3


def test_cache_key_is_sha256_hex() -> None:
    """Cache key is a valid 64-character hex string (SHA-256)."""
    req = _make_req()
    key = make_cache_key(req)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)
