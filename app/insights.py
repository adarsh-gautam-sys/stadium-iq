"""Gemini-powered personalised multilingual insights with deterministic fallback.

Design decisions:
- Shared ``genai.Client`` initialised once at module level — reused across all requests.
  Per-request client creation would cause authentication overhead and connection churn.
- Async SDK (``client.aio.models.generate_content``) — never blocks the event loop.
- System instruction explicitly specifies the output language, preventing Gemini from
  defaulting to English regardless of the user's language preference.
- Low temperature (0.2) ensures consistent, factual output — this is safety-critical
  venue guidance, not creative writing.
- The deterministic fallback is structurally guaranteed to produce exactly 3 meaningful
  English strings from computed data — it never touches the Gemini API.
- Multilingual output is the primary reason AI is necessary: the deterministic engine
  cannot generate accurate, contextually appropriate guidance in 7 languages.
"""
from __future__ import annotations

import logging

from google import genai

from app.config import settings
from app.models import (
    AssistRequest,
    CrowdStatus,
    Language,
    NavigationGuidance,
    OperationalAlert,
    TransportOption,
    UserRole,
)

logger = logging.getLogger(__name__)

# ── Language display names for prompt injection ────────────────────────────────
LANGUAGE_NAMES: dict[Language, str] = {
    Language.en: "English",
    Language.es: "Spanish (Español)",
    Language.pt: "Portuguese (Português)",
    Language.fr: "French (Français)",
    Language.ar: "Arabic (العربية)",
    Language.de: "German (Deutsch)",
    Language.zh: "Chinese Simplified (中文)",
}

# ── Role-specific tone instructions ──────────────────────────────────────────
ROLE_TONE: dict[UserRole, str] = {
    UserRole.fan: (
        "Speak to a fan attending the match. Be warm, reassuring, and helpful. "
        "Use simple language that works for all ages."
    ),
    UserRole.staff: (
        "Speak to stadium operations staff. Be concise, professional, and operational. "
        "Focus on action items and key metrics."
    ),
    UserRole.volunteer: (
        "Speak to a stadium volunteer. Be encouraging, practical, and task-focused. "
        "Give clear, step-by-step guidance."
    ),
}

# ── Shared Gemini client — initialised once, never per-request ─────────────────
_gemini_client: genai.Client | None = None
if settings.gemini_api_key:
    try:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
        logger.info("Gemini client initialised (model=%s).", settings.gemini_model)
    except Exception as exc:
        logger.warning("Gemini init failed (%s); fallback active.", exc.__class__.__name__)

# ── System instruction — explicit guardrails ───────────────────────────────────
SYSTEM_INSTRUCTION = """\
You are a FIFA World Cup 2026 stadium intelligence assistant.
Your role: provide concise, practical, safety-conscious stadium guidance.
Rules you must follow:
- Use ONLY the crowd data, navigation, and transport information provided. Do not invent distances, times, or routes.
- Do not reference any data not explicitly given in the prompt.
- Personalise each insight using the user's name where natural.
- Be specific: reference actual crowd levels, estimated times, and transport modes from the input.
- Keep advice motivating and clear — fans may be under time pressure.
- IMPORTANT: Your entire response must be written in the language specified in the prompt.
  Do not use any other language, not even for technical terms.\
"""


def _fallback_insights(
    request: AssistRequest,
    navigation: NavigationGuidance,
    crowd: CrowdStatus,
    transport: list[TransportOption],
) -> list[str]:
    """Deterministic fallback — always computable from validated, computed data.

    Returns exactly 3 English insight strings. Never calls the Gemini API.
    Used when: (1) no API key configured; (2) Gemini call fails; (3) output is insufficient.
    """
    name = request.profile.name
    dest = request.navigation.destination.value.replace("_", " ")
    top_transport = transport[0] if transport else None

    insight_1 = (
        f"{name}, your route to the {dest} is approximately "
        f"{navigation.estimated_minutes} minutes from {request.venue.current_zone}. "
        f"Crowd level: {crowd.level_of_service} ({crowd.alert.upper()})."
    )

    insight_2 = (
        f"Current zone occupancy is {crowd.occupancy_pct}% — "
        f"{crowd.recommendation}"
    )

    if top_transport:
        insight_3 = (
            f"Recommended transport: {top_transport.mode} from {top_transport.departure_point}. "
            f"Estimated wait: {top_transport.estimated_wait_minutes} min, "
            f"journey: {top_transport.estimated_journey_minutes} min."
        )
    else:
        insight_3 = (
            f"{name}, follow the stadium wayfinding signs and ask any volunteer "
            "in a green vest if you need assistance."
        )

    return [insight_1, insight_2, insight_3]


def build_gemini_prompt(
    request: AssistRequest,
    navigation: NavigationGuidance,
    crowd: CrowdStatus,
    transport: list[TransportOption],
) -> str:
    """Build a grounded, constrained Gemini prompt — data only, no hallucination room.

    All numbers come from the computed domain engine output, not from user free-text.
    The prompt explicitly specifies the output language and format to prevent deviation.
    """
    lang_name = LANGUAGE_NAMES[request.profile.language]
    role_tone = ROLE_TONE[request.profile.role]
    dest = request.navigation.destination.value.replace("_", " ")

    transport_lines = "\n".join(
        f"  - {opt.mode.title()}: wait {opt.estimated_wait_minutes} min, "
        f"journey {opt.estimated_journey_minutes} min. {opt.notes}"
        for opt in transport[:3]
    )

    party_note = f" (group of {request.profile.party_size})" if request.profile.party_size > 1 else ""

    return f"""\
OUTPUT LANGUAGE: {lang_name} — write every word of your response in {lang_name}. No exceptions.
TONE: {role_tone}

User profile:
- Name: {request.profile.name}{party_note}
- Role: {request.profile.role.value}
- Language: {lang_name}
- Accessibility: mobility aid={request.profile.mobility_aid.value}, \
visual={request.profile.visual_impairment}, hearing={request.profile.hearing_impairment}

Venue: {request.venue.venue.value.replace("_", " ").title()}
Current location: {request.venue.current_zone}
Match phase: {request.venue.match_phase.value.replace("_", " ")}

Navigation to {dest}:
- Route: {navigation.route_description}
- Estimated time: {navigation.estimated_minutes} minutes
- Crowd level: {navigation.crowd_level}
- Accessibility notes: {navigation.accessibility_notes}

Crowd status:
- Occupancy: {crowd.occupancy_pct}%
- Fruin Level of Service: {crowd.level_of_service} ({crowd.alert.upper()})
- Recommendation: {crowd.recommendation}

Transport options:
{transport_lines}

Task: Return EXACTLY 3 concise insights as plain sentences (no markdown bullets, symbols, or headers).
Each insight must:
1. Be under 35 words.
2. Reference specific numbers or route details from the data above.
3. Personalise using the user's name or role where natural.
4. Be written entirely in {lang_name}.
5. Be actionable and motivating.

Output only the 3 sentences, one per line, in {lang_name}.\
"""


async def generate_personalized_insights(
    request: AssistRequest,
    navigation: NavigationGuidance,
    crowd: CrowdStatus,
    transport: list[TransportOption],
    alerts: list[OperationalAlert],
) -> list[str]:
    """Generate Gemini multilingual insights with guaranteed deterministic fallback.

    The multilingual output is the primary structural reason this function exists —
    the deterministic system cannot produce guidance in Arabic, Chinese, or Portuguese.
    Gemini generates culturally appropriate, language-correct output in 7 languages.

    Falls back to deterministic English insights if:
    - No Gemini API key is configured (GEMINI_API_KEY='').
    - Gemini call fails for any reason (network, rate limit, model error).
    - Gemini returns fewer than 2 usable lines (insufficient output).
    """
    if _gemini_client is None:
        return _fallback_insights(request, navigation, crowd, transport)

    try:
        prompt = build_gemini_prompt(request, navigation, crowd, transport)
        response = await _gemini_client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={
                "system_instruction": SYSTEM_INSTRUCTION,
                "temperature": 0.2,         # Low temp — safety-critical venue guidance
                "max_output_tokens": 300,
            },
        )
        raw = (response.text or "").strip()
        lines = [
            line.lstrip("•-*123. ").strip()
            for line in raw.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        cleaned = [line for line in lines if len(line) > 10][:3]

        if len(cleaned) >= 2:
            return cleaned

        logger.warning("Gemini returned insufficient content (%d lines); using fallback.", len(cleaned))
        return _fallback_insights(request, navigation, crowd, transport)

    except Exception as exc:
        logger.warning("Gemini call failed (%s); using deterministic fallback.", exc.__class__.__name__)
        return _fallback_insights(request, navigation, crowd, transport)
