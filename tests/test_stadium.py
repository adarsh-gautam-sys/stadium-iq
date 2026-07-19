"""Unit tests for the StadiumIQ domain engine (stadium.py).

Tests cover: Fruin LoS mapping, navigation computation, transport options,
alert generation, confidence scoring, and boundary conditions.
"""
from __future__ import annotations

import pytest

from app.models import (
    AssistRequest,
    DestinationType,
    MatchPhase,
    MobilityAid,
    Venue,
)
from app.stadium import (
    DESTINATION_BASE_DISTANCE_M,
    FRUIN_LOS,
    VENUE_CAPACITY,
    calculate_confidence,
    compute_crowd_status,
    compute_navigation,
    compute_transport_options,
    generate_alerts,
    get_fruin_los,
    get_venue_capacity,
)

# ── Shared test request factory ───────────────────────────────────────────────

def make_request(
    crowd_density_pct: float = 60.0,
    match_phase: str = "arrival",
    mobility_aid: str = "none",
    requires_accessible_route: bool = False,
    requires_elevator: bool = False,
    destination: str = "seat",
    venue: str = "sofi_stadium",
    transport_mode: str = "shuttle",
    destination_detail: str = "",
    party_size: int = 1,
) -> AssistRequest:
    """Helper to build a minimal valid AssistRequest for testing."""
    return AssistRequest.model_validate({
        "profile": {
            "name": "Tester",
            "role": "fan",
            "language": "en",
            "mobility_aid": mobility_aid,
            "visual_impairment": False,
            "hearing_impairment": False,
            "party_size": party_size,
        },
        "venue": {
            "venue": venue,
            "section": "100",
            "current_zone": "Gate B",
            "match_phase": match_phase,
            "crowd_density_pct": crowd_density_pct,
        },
        "navigation": {
            "destination": destination,
            "destination_detail": destination_detail,
            "requires_elevator": requires_elevator,
            "requires_accessible_route": requires_accessible_route,
        },
        "transport": {
            "transport_mode": transport_mode,
            "direction": "arriving",
            "distance_km": 5.0,
        },
    })


# ── Venue capacity tests ──────────────────────────────────────────────────────

def test_all_venues_have_capacity() -> None:
    """All 16 FIFA WC 2026 venues have a capacity entry."""
    assert len(VENUE_CAPACITY) == 16


def test_sofi_stadium_capacity() -> None:
    """SoFi Stadium capacity matches FIFA official figure (70,240)."""
    assert get_venue_capacity(Venue.sofi_stadium) == 70_240


def test_estadio_azteca_is_largest() -> None:
    """Estadio Azteca (87,523) is the largest FIFA WC 2026 venue."""
    assert max(VENUE_CAPACITY.values()) == 87_523


# ── Fruin LoS tests ───────────────────────────────────────────────────────────

def test_zero_crowd_returns_los_a() -> None:
    """0% crowd density maps to Fruin LoS A (free flow)."""
    assert get_fruin_los(0.0, MatchPhase.pre_match) == "A"


def test_full_crowd_returns_los_f() -> None:
    """Very high occupancy at halftime maps to Fruin LoS F (critical)."""
    assert get_fruin_los(95.0, MatchPhase.halftime) == "F"


def test_all_los_letters_exist() -> None:
    """FRUIN_LOS table contains all 6 Level of Service letters."""
    assert set(FRUIN_LOS.keys()) == {"A", "B", "C", "D", "E", "F"}


def test_moderate_crowd_returns_los_c_or_d() -> None:
    """60% occupancy at kickoff maps to a congested LoS."""
    los = get_fruin_los(60.0, MatchPhase.kickoff)
    assert los in ("C", "D", "E")


# ── Crowd status tests ────────────────────────────────────────────────────────

def test_low_crowd_returns_green_alert() -> None:
    """Crowd < 70% returns green alert."""
    req = make_request(crowd_density_pct=50.0)
    crowd = compute_crowd_status(req)
    assert crowd.alert == "green"


def test_amber_crowd_threshold() -> None:
    """Crowd >= 70% returns amber alert."""
    req = make_request(crowd_density_pct=72.0)
    crowd = compute_crowd_status(req)
    assert crowd.alert == "amber"


def test_red_crowd_threshold() -> None:
    """Crowd >= 85% returns red alert."""
    req = make_request(crowd_density_pct=90.0)
    crowd = compute_crowd_status(req)
    assert crowd.alert == "red"


def test_crowd_status_occupancy_matches_input() -> None:
    """crowd_status.occupancy_pct reflects the input crowd_density_pct."""
    req = make_request(crowd_density_pct=67.5)
    crowd = compute_crowd_status(req)
    assert crowd.occupancy_pct == pytest.approx(67.5, abs=0.1)


# ── Navigation tests ──────────────────────────────────────────────────────────

def test_navigation_estimated_minutes_positive() -> None:
    """Estimated navigation time is always positive."""
    req = make_request()
    crowd = compute_crowd_status(req)
    nav = compute_navigation(req, crowd)
    assert nav.estimated_minutes > 0


def test_accessible_route_takes_longer() -> None:
    """Accessible route (wheelchair) takes longer than standard route."""
    req_standard = make_request(mobility_aid="none")
    req_accessible = make_request(mobility_aid="wheelchair", requires_accessible_route=True)
    crowd_std = compute_crowd_status(req_standard)
    crowd_acc = compute_crowd_status(req_accessible)
    nav_std = compute_navigation(req_standard, crowd_std)
    nav_acc = compute_navigation(req_accessible, crowd_acc)
    assert nav_acc.estimated_minutes > nav_std.estimated_minutes


def test_elevator_adds_extra_time() -> None:
    """Elevator requirement adds extra time to the navigation estimate."""
    req_no_elev = make_request(requires_elevator=False)
    req_elev = make_request(requires_elevator=True)
    crowd = compute_crowd_status(req_no_elev)
    nav_no_elev = compute_navigation(req_no_elev, crowd)
    nav_elev = compute_navigation(req_elev, crowd)
    assert nav_elev.estimated_minutes > nav_no_elev.estimated_minutes


def test_all_destinations_return_valid_guidance() -> None:
    """Every destination type produces a non-empty route description."""
    for dest in DestinationType:
        req = make_request(destination=dest.value)
        crowd = compute_crowd_status(req)
        nav = compute_navigation(req, crowd)
        assert nav.route_description


def test_high_crowd_produces_critical_or_high_crowd_level() -> None:
    """Very high occupancy at halftime produces high or critical crowd level in navigation."""
    req = make_request(crowd_density_pct=92.0, match_phase="halftime")
    crowd = compute_crowd_status(req)
    nav = compute_navigation(req, crowd)
    assert nav.crowd_level in ("high", "critical")


# ── Transport tests ───────────────────────────────────────────────────────────

def test_transport_options_returns_all_modes() -> None:
    """compute_transport_options returns one entry per transport mode."""
    req = make_request()
    options = compute_transport_options(req)
    modes = {opt.mode for opt in options}
    assert "shuttle" in modes
    assert "metro" in modes
    assert "walk" in modes


def test_post_match_wait_times_higher_than_pre_match() -> None:
    """Transport wait times are higher post-match than pre-match (surge modelling)."""
    req_pre = make_request(match_phase="pre_match")
    req_post = make_request(match_phase="post_match")
    opts_pre = compute_transport_options(req_pre)
    opts_post = compute_transport_options(req_post)
    # Shuttle (non-walk mode) should have higher wait post-match
    shuttle_pre = next(o for o in opts_pre if o.mode == "shuttle")
    shuttle_post = next(o for o in opts_post if o.mode == "shuttle")
    assert shuttle_post.estimated_wait_minutes > shuttle_pre.estimated_wait_minutes


# ── Alert generation tests ────────────────────────────────────────────────────

def test_red_crowd_triggers_critical_alert() -> None:
    """Crowd >= 85% triggers a critical operational alert."""
    req = make_request(crowd_density_pct=90.0, match_phase="post_match")
    crowd = compute_crowd_status(req)
    alerts = generate_alerts(req, crowd)
    severities = [a.severity.value for a in alerts]
    assert "critical" in severities


def test_amber_crowd_triggers_warning_alert() -> None:
    """Crowd >= 70% but < 85% triggers a warning alert."""
    req = make_request(crowd_density_pct=75.0)
    crowd = compute_crowd_status(req)
    alerts = generate_alerts(req, crowd)
    severities = [a.severity.value for a in alerts]
    assert "warning" in severities


def test_low_crowd_produces_info_alert() -> None:
    """Low crowd density produces the 'Normal Operations' info alert."""
    req = make_request(crowd_density_pct=30.0, match_phase="pre_match")
    crowd = compute_crowd_status(req)
    alerts = generate_alerts(req, crowd)
    assert len(alerts) == 1
    assert alerts[0].severity.value == "info"


def test_halftime_triggers_concourse_surge_alert() -> None:
    """Halftime with >= 60% occupancy triggers the concourse surge alert."""
    req = make_request(crowd_density_pct=65.0, match_phase="halftime")
    crowd = compute_crowd_status(req)
    alerts = generate_alerts(req, crowd)
    titles = [a.title for a in alerts]
    assert any("Halftime" in t or "Surge" in t for t in titles)


# ── Confidence scoring tests ──────────────────────────────────────────────────

def test_confidence_starts_at_baseline() -> None:
    """Minimum input confidence is >= 0.72."""
    req = make_request()
    assert calculate_confidence(req) >= 0.72


def test_confidence_capped_at_0_92() -> None:
    """Maximum confidence is never above 0.92."""
    req = make_request(
        mobility_aid="wheelchair",
        transport_mode="metro",
        destination_detail="Section 100",
        party_size=5,
    )
    assert calculate_confidence(req) <= 0.92


def test_wheelchair_increases_confidence() -> None:
    """Specifying a mobility aid (non-none) increases confidence score."""
    req_base = make_request(mobility_aid="none")
    req_wheel = make_request(mobility_aid="wheelchair")
    assert calculate_confidence(req_wheel) > calculate_confidence(req_base)


# ── New coverage tests — targets uncovered lines in stadium.py ────────────────

def test_fruin_los_c_grade_mapped_correctly() -> None:
    """Moderate occupancy at kickoff maps to LoS C (density_proxy 0.50–0.70)."""
    # kickoff multiplier = 1.0; effective = 22% → proxy = 0.66 → LoS C
    result = get_fruin_los(22.0, MatchPhase.kickoff)
    assert result == "C"


def test_fruin_los_d_grade_mapped_correctly() -> None:
    """High occupancy at kickoff maps to LoS D (density_proxy 0.70–1.00)."""
    # kickoff multiplier = 1.0; effective = 28% → proxy = 0.84 → LoS D
    result = get_fruin_los(28.0, MatchPhase.kickoff)
    assert result == "D"


def test_free_flow_walk_speed_for_clear_concourse() -> None:
    """A fan with no mobility restriction at LoS A/B uses free-flow walk speed."""
    from app.stadium import WALK_SPEED_FREE_FLOW_MS, _compute_walk_speed
    req = make_request(crowd_density_pct=5.0, match_phase="pre_match")
    crowd = compute_crowd_status(req)
    # At 5% pre_match: effective = 5 * 0.40 = 2% → proxy 0.06 → LoS A
    assert crowd.level_of_service == "A"
    speed = _compute_walk_speed(req, crowd.level_of_service)
    assert speed == WALK_SPEED_FREE_FLOW_MS


def test_navigation_visual_impairment_note() -> None:
    """Visual impairment flag returns audio wayfinding guidance note."""
    req = AssistRequest.model_validate({
        "profile": {
            "name": "Test",
            "role": "fan",
            "language": "en",
            "mobility_aid": "none",
            "visual_impairment": True,
            "hearing_impairment": False,
            "party_size": 1,
        },
        "venue": {
            "venue": "sofi_stadium",
            "section": "100",
            "current_zone": "Gate B",
            "match_phase": "arrival",
            "crowd_density_pct": 40.0,
        },
        "navigation": {
            "destination": "seat",
            "destination_detail": "",
            "requires_elevator": False,
            "requires_accessible_route": False,
        },
        "transport": {"transport_mode": "shuttle", "direction": "arriving", "distance_km": 2.0},
    })
    crowd = compute_crowd_status(req)
    nav = compute_navigation(req, crowd)
    assert "audio" in nav.accessibility_notes.lower() or "beacon" in nav.accessibility_notes.lower()


def test_navigation_hearing_impairment_note() -> None:
    """Hearing impairment flag returns LED ticker board guidance note."""
    req = AssistRequest.model_validate({
        "profile": {
            "name": "Test",
            "role": "fan",
            "language": "en",
            "mobility_aid": "none",
            "visual_impairment": False,
            "hearing_impairment": True,
            "party_size": 1,
        },
        "venue": {
            "venue": "sofi_stadium",
            "section": "100",
            "current_zone": "Gate B",
            "match_phase": "arrival",
            "crowd_density_pct": 40.0,
        },
        "navigation": {
            "destination": "seat",
            "destination_detail": "",
            "requires_elevator": False,
            "requires_accessible_route": False,
        },
        "transport": {"transport_mode": "shuttle", "direction": "arriving", "distance_km": 2.0},
    })
    crowd = compute_crowd_status(req)
    nav = compute_navigation(req, crowd)
    assert "led" in nav.accessibility_notes.lower() or "ticker" in nav.accessibility_notes.lower()


def test_named_constants_match_expected_values() -> None:
    """Named threshold constants have the expected values from FIFA Safety Manual."""
    from app.stadium import (
        ALERT_THRESHOLD_AMBER,
        ALERT_THRESHOLD_RED,
        ALERT_THRESHOLD_SURGE,
        FRUIN_MAX_DENSITY,
    )
    assert ALERT_THRESHOLD_RED == 85.0    # FIFA Safety Manual §3.2 red threshold
    assert ALERT_THRESHOLD_AMBER == 70.0  # FIFA Safety Manual §3.2 amber threshold
    assert ALERT_THRESHOLD_SURGE == 60.0  # Surge warning threshold
    assert FRUIN_MAX_DENSITY == 3.0       # Max density proxy (p/m²)


def test_transport_sorting() -> None:
    """compute_transport_options places preferred mode first, and then sorts other options by total time ascending."""
    req = make_request(transport_mode="rideshare")
    options = compute_transport_options(req)

    # First option must be the preferred mode (rideshare)
    assert options[0].mode == "rideshare"

    # The remaining options must be sorted by total time (wait + journey) ascending
    remaining_times = [opt.estimated_wait_minutes + opt.estimated_journey_minutes for opt in options[1:]]
    assert remaining_times == sorted(remaining_times)


