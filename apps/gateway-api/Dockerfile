# syntax=docker/dockerfile:1
# Multi-stage backend image (FR-031–FR-033).
# Build context: apps/gateway-api (self-contained: pyproject.toml + uv.lock + gateway_api/).
# Size is uncapped (R1 resolved) — the Polish model is baked in; multi-stage is
# used only for hygiene (build tooling stays out of the runtime image).

# ---- Stage 1: builder (deps + Polish model) ----
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install runtime deps (no dev group) against the locked versions.
COPY pyproject.toml uv.lock README.md ./
COPY gateway_api/ ./gateway_api/

# Resolve deps and bake in the Polish model. An OPTIONAL corporate CA can be
# supplied as the build secret `ca_cert` (for TLS-inspecting proxies). When
# absent the secret file is empty and this is a normal build. The CA is used
# only inside this builder stage and never reaches the runtime image.
RUN --mount=type=secret,id=ca_cert,required=false \
    set -eu; \
    if [ -s /run/secrets/ca_cert ]; then \
      apt-get update && apt-get install -y --no-install-recommends ca-certificates; \
      cat /run/secrets/ca_cert >> /etc/ssl/certs/ca-certificates.crt; \
      export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
             REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
             PIP_CERT=/etc/ssl/certs/ca-certificates.crt; \
    fi; \
    uv venv /opt/venv; \
    uv sync --frozen --no-dev --system-certs; \
    export VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH; \
    python -m spacy download pl_core_news_lg

# ---- Stage 2: slim runtime ----
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# curl is needed for the container HEALTHCHECK.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY gateway_api/ ./gateway_api/

USER appuser
EXPOSE 8000

# --start-period absorbs interpreter boot so the orchestrator does not flap (D3).
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=5 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "gateway_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
