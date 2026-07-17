FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Non-root user — never run as root in production
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --no-create-home appuser

WORKDIR /app

# Pin ALL deps with exact versions — avoids supply-chain drift
# Run pip-audit after updating to verify no CVEs
RUN pip install --no-cache-dir \
    fastapi==0.115.12 \
    "uvicorn[standard]==0.34.3" \
    pydantic==2.11.7 \
    pydantic-settings==2.9.1 \
    google-genai==1.19.0 \
    google-cloud-firestore==2.21.0 \
    google-cloud-logging==3.11.4 \
    cachetools==5.5.2 \
    httpx==0.28.1

COPY --chown=appuser:appgroup app ./app
COPY --chown=appuser:appgroup static ./static

USER appuser
ENV PORT=8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
