"""StadiumIQ — FastAPI application entry point.

Architecture:
- lifespan: initialises semaphore (inside running event loop), pre-seeds cache
  with 3 demo payloads, and configures Cloud Logging (graceful fallback to stdlib).
- Security middleware: attaches 6 strict HTTP security headers on every response.
- CORS: explicit allowlist — never wildcard in any environment.
- GET /: serves the landing / role-selection page (index.html).
- GET /fan: serves the Fan Dashboard (fan.html).
- GET /staff: serves the Staff Command Center (staff.html).
- GET /volunteer: serves the Volunteer Dashboard (volunteer.html).
- GET /health: liveness probe for Cloud Run — returns version and cache count.
- POST /api/assist: 5-stage pipeline:
    1. Cache fast-path (SHA-256 keyed TTLCache).
    2. Deterministic computation (Fruin LoS, route scoring, transport, alerts).
    3. Gemini multilingual insights (semaphore-guarded, deterministic fallback).
    4. Firestore / JSONL persistence.
    5. Build, cache, and return the structured response.
- ValidationError handler: structured 422 body matching the test expectations.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app import cache as app_cache
from app.config import settings
from app.insights import generate_personalized_insights
from app.models import AssistRequest, AssistResponse
from app.response_builder import ResponseComponents, build_response
from app.stadium import (
    calculate_confidence,
    compute_crowd_status,
    compute_navigation,
    compute_transport_options,
    generate_alerts,
)
from app.storage import save_record

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"

# ── Cloud Logging (graceful fallback) ─────────────────────────────────────────
try:
    import google.cloud.logging as _gcp_logging
    _GCP_LOGGING_AVAILABLE = True
except ImportError:
    _gcp_logging = None  # type: ignore[assignment]
    _GCP_LOGGING_AVAILABLE = False


def _setup_cloud_logging() -> None:
    """Configure Cloud Logging if project is set; fall back to stdlib logging."""
    if not settings.google_cloud_project or not _GCP_LOGGING_AVAILABLE:
        logging.basicConfig(level=settings.log_level)
        return
    try:
        client = _gcp_logging.Client(project=settings.google_cloud_project)
        client.setup_logging(log_level=getattr(logging, settings.log_level, logging.INFO))
    except Exception as exc:
        logging.basicConfig(level=settings.log_level)
        logger.warning("Cloud Logging unavailable (%s).", exc.__class__.__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup tasks before yield, shutdown after."""
    _setup_cloud_logging()
    app_cache.init_semaphore()    # Must be inside running event loop
    app_cache.preseed_cache()     # Pre-populate for 0ms demo latency
    logger.info(
        "StadiumIQ started. Cache: %d entries. Gemini: %s.",
        app_cache.cache_size(),
        "enabled" if settings.gemini_api_key else "fallback",
    )
    yield
    logger.info("StadiumIQ shutting down.")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="StadiumIQ — FIFA World Cup 2026 Stadium Intelligence",
    version="1.0.0",
    description=(
        "AI-powered stadium operations and fan experience platform for FIFA World Cup 2026. "
        "Provides multilingual navigation guidance, crowd density assessment (Fruin LoS), "
        "transport options, and operational alerts for fans, staff, and volunteers."
    ),
    contact={"name": "PromptWars 2026 Submission"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

# ── CORS — explicit allowlist ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ── Security headers middleware ────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next: Callable) -> JSONResponse:
    """Attach 6 security headers to every HTTP response — GET and POST."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self'",
        "frame-ancestors 'none'",
    ]
    response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
    )
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    return response


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve the StadiumIQ role-selection landing page."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/fan", include_in_schema=False)
async def fan_dashboard() -> FileResponse:
    """Serve the Fan Dashboard (mobile-first, green accent)."""
    return FileResponse(STATIC_DIR / "fan.html")


@app.get("/staff", include_in_schema=False)
async def staff_dashboard() -> FileResponse:
    """Serve the Staff Command Center (desktop, amber accent, KPI row, 2-column layout)."""
    return FileResponse(STATIC_DIR / "staff.html")


@app.get("/volunteer", include_in_schema=False)
async def volunteer_dashboard() -> FileResponse:
    """Serve the Volunteer Dashboard (mobile-first, teal accent, fan-assistance radar)."""
    return FileResponse(STATIC_DIR / "volunteer.html")


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe for Cloud Run. Returns version and cache entry count."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "cache_entries": str(app_cache.cache_size()),
        "gemini": "enabled" if settings.gemini_api_key else "fallback",
    }


@app.post(
    "/api/assist",
    response_model=AssistResponse,
    summary="Request multilingual stadium assistance — navigation, crowd status, transport, alerts.",
    tags=["stadium"],
)
async def assist(request: AssistRequest) -> AssistResponse:
    """Stadium assistance endpoint — 5-stage pipeline.

    Stage 1: Cache fast-path — return immediately if this exact request was seen before.
    Stage 2: Deterministic computation — Fruin LoS, route timing, transport options, alerts.
    Stage 3: Gemini insights — multilingual personalisation via semaphore-guarded LLM call.
    Stage 4: Persistence — save record to Firestore (prod) or local JSONL (dev).
    Stage 5: Build, cache, and return the structured AssistResponse.
    """
    # Stage 1: Cache fast-path
    cache_key = app_cache.make_cache_key(request)
    if cached := app_cache.get_cached(cache_key):
        return cached

    # Stage 2: Deterministic computation
    crowd = compute_crowd_status(request)
    nav = compute_navigation(request, crowd)
    transport = compute_transport_options(request)
    alerts = generate_alerts(request, crowd)

    # Stage 3: Gemini multilingual insights (semaphore-guarded)
    active_semaphore = app_cache.semaphore
    if active_semaphore is not None:
        async with active_semaphore:
            insights = await generate_personalized_insights(request, nav, crowd, transport, alerts)
    else:
        insights = await generate_personalized_insights(request, nav, crowd, transport, alerts)

    # Stage 4: Persist
    storage_status = await save_record({
        "venue": request.venue.venue.value,
        "role": request.profile.role.value,
        "language": request.profile.language.value,
        "destination": request.navigation.destination.value,
        "crowd_density_pct": request.venue.crowd_density_pct,
        "los": crowd.level_of_service,
        "alert": crowd.alert,
        "estimated_minutes": nav.estimated_minutes,
        "confidence_score": calculate_confidence(request),
    })

    # Stage 5: Build, cache, return
    result = build_response(ResponseComponents(
        navigation=nav,
        crowd_status=crowd,
        transport_options=transport,
        alerts=alerts,
        insights=insights,
        confidence_score=calculate_confidence(request),
        storage_status=storage_status,
    ))
    app_cache.set_cached(cache_key, result)
    return result


# ── Validation error handler ──────────────────────────────────────────────────
@app.exception_handler(ValidationError)
async def validation_handler(_request: Request, exc: ValidationError) -> JSONResponse:
    """Return structured 422 body matching test expectations."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(include_url=False)},
    )
