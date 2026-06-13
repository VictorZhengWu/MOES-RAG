# ============================================================================
# Marine & Offshore Expert System — Dockerfile
# ============================================================================
# Multi-stage build with two targets:
#   m8 — API Gateway + QA Engine + Retrieval + KG (lightweight, ~2GB)
#   m1 — Document Parsing Engine (heavy, ~8GB with docling+OCR)
#
# Build:
#   docker build -f deploy/Dockerfile --target m8 -t marine-m8 .
#   docker build -f deploy/Dockerfile --target m1 -t marine-m1 .
# ============================================================================

# ── Shared base image ─────────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies common to both targets
RUN pip install --upgrade pip setuptools wheel

# ── M8 target: Gateway + QA Engine + Retrieval + KG ───────────────────
FROM base AS m8

# Copy contracts first (shared dependency)
COPY contracts/ /app/contracts/

# Copy and install backend modules (order by dependency)
COPY m2-storage/ /app/m2-storage/
COPY m3-retrieval/ /app/m3-retrieval/
COPY m4-knowledge-graph/ /app/m4-knowledge-graph/
COPY m5-qa-engine/ /app/m5-qa-engine/
COPY m8-api-gateway/ /app/m8-api-gateway/

# Install all modules in development mode
RUN pip install -e /app/contracts/ && \
    pip install -e /app/m2-storage/ && \
    pip install -e /app/m3-retrieval/ && \
    pip install -e /app/m4-knowledge-graph/ && \
    pip install -e /app/m5-qa-engine/ && \
    pip install -e /app/m8-api-gateway/

# Install FlagEmbedding for BGE-M3 (the heavy ML dependency)
RUN pip install FlagEmbedding sentence-transformers

EXPOSE 8000

CMD ["python", "-c", "\
import os, uvicorn; \
from m8_gateway.core.app import create_app; \
from m8_gateway.core.config import GatewayConfig; \
mode = os.environ.get('DEPLOYMENT_MODE', 'personal'); \
config = GatewayConfig(deployment_mode=mode); \
uvicorn.run(create_app(config), host='0.0.0.0', port=8000)\
"]

# ── M1 target: Document Parsing Engine ────────────────────────────────
FROM base AS m1

# Install docling (heavy: ~2GB with transformers, ~4GB with GPU support)
RUN pip install docling docling-core

# Copy modules needed by M1
COPY contracts/ /app/contracts/
COPY m1-doc-parsing/ /app/m1-doc-parsing/
COPY m2-storage/ /app/m2-storage/

RUN pip install -e /app/contracts/ && \
    pip install -e /app/m2-storage/ && \
    pip install -e /app/m1-doc-parsing/

EXPOSE 8007

CMD ["python", "-c", "\
from m1_parser.standalone.web_server import main; \
main(host='0.0.0.0', port=8007)\
"]
