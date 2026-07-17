"""Unit tests for the Gemini insights layer (insights.py)."""
from __future__ import annotations

import pytest

from app.insights import _fallback_insights, build_gemini_prompt, generate_personalized_insights
from app.models import (
    AssistRequest,
    CrowdStatus,
    NavigationGuidance,
    TransportOption,
)


def _make_request(name: str = "Tester", language: str = "en") -> AssistRequest:
    return AssistRequest.model_validate({
        "profile": {"name": name, "role": "fan", "language": language,
                    "mobility_aid": "none", "visual_impairment": False,
                    "hearing_impairment": False, "party_size": 1},
        "venue": {"venue": "sofi_stadium", "section": "100", "current_zone": "Gate C",
                  "match_phase": "arrival", "crowd_density_pct": 60.0},
        "navigation": {"destination": "seat", "destination_detail": "Section 100, Row B, Seat 3",
                       "requires_elevator": False, "requires_accessible_route": False},
        "transport": {"transport_mode": "shuttle", "direction": "arriving", "distance_km": 3.0},
    })


def _make_nav() -> NavigationGuidance:
    return NavigationGuidance(
        route_description="Head to the nearest seat signage.",
        estimated_minutes=8.5,
        crowd_level="moderate",
        alternative_route="Use alternate gate.",
        accessibility_notes="Standard route.",
    )


def _make_crowd() -> CrowdStatus:
    return CrowdStatus(
        zone="Gate C", occupancy_pct=60.0, level_of_service="C",
        alert="green", recommendation="Allow extra time.",
    )


def _make_transport() -> list[TransportOption]:
    return [
        TransportOption(
            mode="shuttle", estimated_wait_minutes=10.0,
            estimated_journey_minutes=15.0,
            departure_point="Gate B Shuttle Bay",
            notes="Free FIFA shuttle.",
        )
    ]


def test_fallback_returns_three_strings() -> None:
    """Fallback returns exactly 3 non-empty insight strings."""
    req = _make_request()
    nav = _make_nav()
    crowd = _make_crowd()
    transport = _make_transport()
    insights = _fallback_insights(req, nav, crowd, transport)
    assert len(insights) == 3
    assert all(isinstance(s, str) and len(s) > 10 for s in insights)


def test_fallback_contains_user_name() -> None:
    """Fallback insight 1 contains the user's name."""
    req = _make_request(name="Santiago")
    nav = _make_nav()
    crowd = _make_crowd()
    transport = _make_transport()
    insights = _fallback_insights(req, nav, crowd, transport)
    assert any("Santiago" in i for i in insights)


def test_fallback_references_crowd_data() -> None:
    """Fallback insight 2 references crowd status information."""
    req = _make_request()
    nav = _make_nav()
    crowd = _make_crowd()
    transport = _make_transport()
    insights = _fallback_insights(req, nav, crowd, transport)
    # Insight 2 should reference occupancy
    assert "60" in insights[1] or "green" in insights[1].lower() or "Allow" in insights[1]


def test_fallback_references_transport() -> None:
    """Fallback insight 3 references transport information."""
    req = _make_request()
    nav = _make_nav()
    crowd = _make_crowd()
    transport = _make_transport()
    insights = _fallback_insights(req, nav, crowd, transport)
    assert "shuttle" in insights[2].lower() or "Gate B" in insights[2]


def test_fallback_works_with_no_transport() -> None:
    """Fallback works gracefully when transport list is empty."""
    req = _make_request()
    nav = _make_nav()
    crowd = _make_crowd()
    insights = _fallback_insights(req, nav, crowd, [])
    assert len(insights) == 3
    assert all(len(s) > 10 for s in insights)


def test_gemini_prompt_contains_user_name() -> None:
    """Built prompt includes the user's name."""
    req = _make_request(name="Hiroaki")
    nav = _make_nav()
    crowd = _make_crowd()
    transport = _make_transport()
    prompt = build_gemini_prompt(req, nav, crowd, transport)
    assert "Hiroaki" in prompt


def test_gemini_prompt_contains_estimated_minutes() -> None:
    """Built prompt includes the navigation estimated minutes."""
    req = _make_request()
    nav = _make_nav()
    crowd = _make_crowd()
    transport = _make_transport()
    prompt = build_gemini_prompt(req, nav, crowd, transport)
    assert "8.5" in prompt


def test_gemini_prompt_specifies_language() -> None:
    """Built prompt explicitly names the output language."""
    req = _make_request(language="es")
    nav = _make_nav()
    crowd = _make_crowd()
    transport = _make_transport()
    prompt = build_gemini_prompt(req, nav, crowd, transport)
    assert "Spanish" in prompt or "Español" in prompt


@pytest.mark.asyncio
async def test_generate_insights_without_key_uses_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a GEMINI_API_KEY, generate_personalized_insights uses fallback."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    req = _make_request()
    nav = _make_nav()
    crowd = _make_crowd()
    transport = _make_transport()
    insights = await generate_personalized_insights(req, nav, crowd, transport, [])
    assert len(insights) == 3
    assert all(len(s) > 10 for s in insights)
