# ==============================================================================
# Multi-stage secure non-root Dockerfile for AI-DAX Lite Platform
# ==============================================================================

# Stage 1: Build dependencies and wheels
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt

# Stage 2: Minimal hardened runtime image
FROM python:3.11-slim AS runner

LABEL org.opencontainers.image.title="AI-DAX Lite" \
      org.opencontainers.image.description="Heterogeneous CPU Scheduling Telemetry & Bandit Platform" \
      org.opencontainers.image.authors="AI-DAX Research Team" \
      org.opencontainers.image.source="https://github.com/priyanrajj-hub/operatingsystemsprojectcapstone" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Create non-root system user and group
RUN groupadd -g 10001 aidax && \
    useradd -u 10001 -g aidax -s /sbin/nologin -M aidax && \
    mkdir -p /app/data /app/logs && \
    chown -R aidax:aidax /app

# Install wheels from builder stage
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application source code and static assets
COPY --chown=aidax:aidax pyproject.toml .
COPY --chown=aidax:aidax src/ ./src/
COPY --chown=aidax:aidax static/ ./static/

ENV PYTHONPATH="/app/src" \
    AIDAX_HOST="0.0.0.0" \
    AIDAX_PORT="8000" \
    PYTHONUNBUFFERED="1" \
    PYTHONDONTWRITEBYTECODE="1"

USER aidax

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')" || exit 1

ENTRYPOINT ["python", "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
