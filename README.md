# StadiumIQ — FIFA World Cup 2026 Stadium Intelligence Platform

> AI-powered stadium operations and fan experience platform for FIFA World Cup 2026 — multilingual navigation, crowd density management, transport intelligence, and real-time operational alerts.

**Live demo:** https://YOUR_CLOUD_RUN_URL (update after deployment)

## Features

- 🧭 **AI-Powered Navigation** — Real-time route guidance from any zone to any destination in the stadium
- 👥 **Crowd Intelligence** — Fruin Level of Service (A–F) crowd density assessment with amber/red alerts
- 🌍 **7-Language Support** — Gemini 2.0 Flash generates insights in English, Español, Português, Français, العربية, Deutsch, 中文
- ♿ **Full Accessibility** — Accessible route calculation, elevator routing, and impairment-specific guidance
- 🚌 **Transport Intelligence** — Match-phase-aware transport wait times for all 5 modes across 16 venues
- 👔 **Multi-Role Support** — Personalised guidance for fans, stadium staff, and volunteers
- 📊 **Operational Alerts** — Automated alerts at 70%/85% occupancy thresholds (FIFA Safety Manual)
- 💾 **Dual Persistence** — Firestore (production) / local JSONL (development) with automatic fallback

## API Quick Start

```bash
curl -X POST https://YOUR_CLOUD_RUN_URL/api/assist \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {"name": "Alex", "role": "fan", "language": "en", "mobility_aid": "none", "visual_impairment": false, "hearing_impairment": false, "party_size": 2},
    "venue": {"venue": "sofi_stadium", "section": "214", "current_zone": "Gate C", "match_phase": "arrival", "crowd_density_pct": 62.0},
    "navigation": {"destination": "seat", "destination_detail": "Section 214, Row H, Seat 7", "requires_elevator": false, "requires_accessible_route": false},
    "transport": {"transport_mode": "shuttle", "direction": "arriving", "distance_km": 3.5}
  }'
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for full system diagram.

## Local Development

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install fastapi uvicorn pydantic pydantic-settings google-genai cachetools httpx
cp .env.example .env   # then fill in GEMINI_API_KEY
uvicorn app.main:app --reload
```

## Tests

```bash
pip install pytest httpx pytest-asyncio
pytest
```

All tests pass without a Gemini API key — deterministic fallback is always active.

## Google Services Used

| Service | Role |
|---|---|
| Cloud Run | Serverless deployment — scales to zero |
| Gemini 2.0 Flash | Multilingual personalised insights |
| Firestore | Stadium assistance record persistence |
| Cloud Logging | Structured observability |
| Cloud Build | Container image builds |

## Data Sources

| Source | Usage |
|---|---|
| Fruin (1971) Pedestrian Planning and Design | Crowd Level of Service (A–F) thresholds |
| Transport for London (2010) Pedestrian Comfort Guidance | Walk speed standards (0.5–1.2 m/s) |
| FIFA WC 2026 Host Venue Programme (2023) | All 16 stadium capacities |
| FIFA Safety and Security Division (2021) Stadium Safety Manual | 70%/85% alert thresholds |
| FIFA WC 2026 Host City Transportation Operation Plans (2024) | Transport wait time baselines |
