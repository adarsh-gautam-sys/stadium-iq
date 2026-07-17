"""Integration tests for StadiumIQ API layer.

Tests cover: happy path, health check, frontend, validation (422 errors),
security headers on both GET and POST, caching behaviour, lifespan preseed,
and response content correctness.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import HIGH_IMPACT_PAYLOAD, SAMPLE_PAYLOAD


# ── Happy path ────────────────────────────────────────────────────────────────

def test_assist_endpoint_returns_structured_response(client: TestClient) -> None:
    """POST /api/assist returns 200 with all required fields."""
    r = client.post("/api/assist", json=SAMPLE_PAYLOAD)
    assert r.status_code == 200
    d = r.json()
    assert "navigation" in d
    assert "crowd_status" in d
    assert "transport_options" in d
    assert "alerts" in d
    assert len(d["insights"]) == 3
    assert 0 < d["confidence_score"] <= 1
    assert d["methodology"]
    assert d["storage_status"].startswith("saved_locally:")


def test_navigation_fields_present(client: TestClient) -> None:
    """Navigation sub-object has all expected fields."""
    d = client.post("/api/assist", json=SAMPLE_PAYLOAD).json()
    nav = d["navigation"]
    assert nav["route_description"]
    assert nav["estimated_minutes"] > 0
    assert nav["crowd_level"] in ("low", "moderate", "high", "critical")
    assert nav["alternative_route"]
    assert "accessibility_notes" in nav


def test_crowd_status_fields_present(client: TestClient) -> None:
    """CrowdStatus sub-object has all expected fields."""
    d = client.post("/api/assist", json=SAMPLE_PAYLOAD).json()
    crowd = d["crowd_status"]
    assert crowd["level_of_service"] in ("A", "B", "C", "D", "E", "F")
    assert crowd["alert"] in ("green", "amber", "red")
    assert crowd["recommendation"]


def test_transport_options_returned(client: TestClient) -> None:
    """At least one transport option is returned."""
    d = client.post("/api/assist", json=SAMPLE_PAYLOAD).json()
    assert len(d["transport_options"]) >= 1
    opt = d["transport_options"][0]
    assert opt["mode"]
    assert opt["estimated_wait_minutes"] >= 0
    assert opt["estimated_journey_minutes"] >= 0


# ── Health check ───────────────────────────────────────────────────────────────

def test_health_returns_ok(client: TestClient) -> None:
    """GET /health returns status ok with version and cache_entries."""
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert "version" in d
    assert "cache_entries" in d


# ── Frontend ───────────────────────────────────────────────────────────────────

def test_index_serves_html(client: TestClient) -> None:
    """GET / returns 200 with HTML content type."""
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


# ── Validation — 422 errors ────────────────────────────────────────────────────

def test_missing_profile_section_returns_422(client: TestClient) -> None:
    """Missing required 'profile' section returns HTTP 422."""
    bad = {k: v for k, v in SAMPLE_PAYLOAD.items() if k != "profile"}
    assert client.post("/api/assist", json=bad).status_code == 422


def test_crowd_density_above_100_returns_422(client: TestClient) -> None:
    """crowd_density_pct > 100 returns HTTP 422."""
    bad = {**SAMPLE_PAYLOAD, "venue": {**SAMPLE_PAYLOAD["venue"], "crowd_density_pct": 101.0}}
    assert client.post("/api/assist", json=bad).status_code == 422


def test_crowd_density_below_zero_returns_422(client: TestClient) -> None:
    """crowd_density_pct < 0 returns HTTP 422."""
    bad = {**SAMPLE_PAYLOAD, "venue": {**SAMPLE_PAYLOAD["venue"], "crowd_density_pct": -1.0}}
    assert client.post("/api/assist", json=bad).status_code == 422


def test_invalid_venue_enum_returns_422(client: TestClient) -> None:
    """An unknown venue value returns HTTP 422."""
    bad = {**SAMPLE_PAYLOAD, "venue": {**SAMPLE_PAYLOAD["venue"], "venue": "wembley_stadium"}}
    assert client.post("/api/assist", json=bad).status_code == 422


def test_invalid_language_enum_returns_422(client: TestClient) -> None:
    """An unsupported language code returns HTTP 422."""
    bad = {**SAMPLE_PAYLOAD, "profile": {**SAMPLE_PAYLOAD["profile"], "language": "klingon"}}
    assert client.post("/api/assist", json=bad).status_code == 422


def test_party_size_above_max_returns_422(client: TestClient) -> None:
    """party_size > 20 returns HTTP 422."""
    bad = {**SAMPLE_PAYLOAD, "profile": {**SAMPLE_PAYLOAD["profile"], "party_size": 99}}
    assert client.post("/api/assist", json=bad).status_code == 422


def test_422_body_contains_detail_list(client: TestClient) -> None:
    """The 422 response body has a 'detail' list (Pydantic error format)."""
    bad = {**SAMPLE_PAYLOAD, "venue": {**SAMPLE_PAYLOAD["venue"], "crowd_density_pct": 999}}
    r = client.post("/api/assist", json=bad)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list)


# ── Security headers — on BOTH GET and POST ────────────────────────────────────

def test_security_headers_on_get(client: TestClient) -> None:
    """All 6 security headers present on GET / response."""
    r = client.get("/")
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-xss-protection") == "1; mode=block"
    assert "content-security-policy" in r.headers
    assert "referrer-policy" in r.headers
    assert "strict-transport-security" in r.headers


def test_security_headers_on_post(client: TestClient) -> None:
    """All 6 security headers present on POST /api/assist response."""
    r = client.post("/api/assist", json=SAMPLE_PAYLOAD)
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-xss-protection") == "1; mode=block"
    assert "content-security-policy" in r.headers
    assert "referrer-policy" in r.headers
    assert "strict-transport-security" in r.headers


def test_csp_has_frame_ancestors_none(client: TestClient) -> None:
    """CSP header includes frame-ancestors 'none' (clickjacking protection)."""
    r = client.get("/")
    csp = r.headers.get("content-security-policy", "")
    assert "frame-ancestors 'none'" in csp


# ── Caching ───────────────────────────────────────────────────────────────────

def test_repeated_identical_request_returns_consistent_results(client: TestClient) -> None:
    """Two identical requests return consistent navigation results."""
    r1 = client.post("/api/assist", json=SAMPLE_PAYLOAD).json()
    r2 = client.post("/api/assist", json=SAMPLE_PAYLOAD).json()
    assert r1["navigation"]["estimated_minutes"] == r2["navigation"]["estimated_minutes"]
    assert r1["crowd_status"]["level_of_service"] == r2["crowd_status"]["level_of_service"]


def test_different_payloads_produce_different_results(client: TestClient) -> None:
    """A high-density staff request produces different crowd status than default."""
    r1 = client.post("/api/assist", json=SAMPLE_PAYLOAD).json()
    r2 = client.post("/api/assist", json=HIGH_IMPACT_PAYLOAD).json()
    assert r1["crowd_status"]["occupancy_pct"] != r2["crowd_status"]["occupancy_pct"]


def test_cache_does_not_bleed_between_users(client: TestClient) -> None:
    """Different user names produce different insights — no cache bleed."""
    pa = {**SAMPLE_PAYLOAD, "profile": {**SAMPLE_PAYLOAD["profile"], "name": "Alice"}}
    pb = {**SAMPLE_PAYLOAD, "profile": {**SAMPLE_PAYLOAD["profile"], "name": "Bob"}}
    ra = client.post("/api/assist", json=pa).json()
    rb = client.post("/api/assist", json=pb).json()
    # Insights reference user names — Alice's and Bob's should differ
    assert ra["insights"] != rb["insights"]


# ── Lifespan preseed ──────────────────────────────────────────────────────────

def test_lifespan_preseeds_cache() -> None:
    """Startup must pre-seed at least 3 cache entries."""
    from app.main import app as fastapi_app
    with TestClient(fastapi_app) as c:
        data = c.get("/health").json()
        assert int(data["cache_entries"]) >= 3, "Preseed must populate >= 3 demo entries"


# ── Response content correctness ──────────────────────────────────────────────

def test_methodology_contains_fruin_citation(client: TestClient) -> None:
    """Methodology string cites the Fruin data source."""
    d = client.post("/api/assist", json=SAMPLE_PAYLOAD).json()
    assert "Fruin" in d["methodology"]
    assert "Gemini AI" in d["methodology"]


def test_name_trimming_applied(client: TestClient) -> None:
    """Leading/trailing whitespace in name is stripped before personalisation."""
    pa = {**SAMPLE_PAYLOAD, "profile": {**SAMPLE_PAYLOAD["profile"], "name": "  Priya  "}}
    r = client.post("/api/assist", json=pa).json()
    assert any("Priya" in insight for insight in r["insights"])


def test_high_crowd_triggers_amber_or_red_alert(client: TestClient) -> None:
    """Crowd density >= 70% triggers amber or red alert status."""
    payload = {**SAMPLE_PAYLOAD, "venue": {**SAMPLE_PAYLOAD["venue"], "crowd_density_pct": 75.0}}
    d = client.post("/api/assist", json=payload).json()
    assert d["crowd_status"]["alert"] in ("amber", "red")


def test_insights_are_non_empty_strings(client: TestClient) -> None:
    """All 3 insights are non-empty strings with meaningful content (> 10 chars)."""
    d = client.post("/api/assist", json=SAMPLE_PAYLOAD).json()
    assert len(d["insights"]) == 3
    assert all(isinstance(s, str) and len(s) > 10 for s in d["insights"])
