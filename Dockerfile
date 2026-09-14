# syntax=docker/dockerfile:1
# Multi-stage production container for SparkRail Shadow Backend
FROM python:3.11-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final runtime image
FROM python:3.11-slim as runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -u 10001 -m -s /bin/bash sparkrail

# Copy installed Python packages from builder
COPY --from=builder /root/.local /home/sparkrail/.local
ENV PATH=/home/sparkrail/.local/bin:$PATH
ENV PYTHONPATH=/app

# Copy application source code and scripts
COPY --chown=sparkrail:sparkrail src/ /app/src/
COPY --chown=sparkrail:sparkrail scripts/ /app/scripts/

# Create runtime directories for data and audit trails
RUN mkdir -p /app/data && chown -R sparkrail:sparkrail /app/data

USER sparkrail

# Default execution mode is SHADOW
ENV SPARKRAIL_MODE=shadow
ENV ALLOW_DEV_BYPASS=false
ENV SPARKRAIL_LIVE_ENABLED=false
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
