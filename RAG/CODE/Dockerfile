# syntax=docker/dockerfile:1.7
# =============================================================================
# Image du backend : API FastAPI, pipeline d'ingestion (OCR Tesseract fra+eng),
# workflow LangGraph et scripts d'évaluation.
# Contexte de build : le dossier RAG/ (voir docker-compose.yml).
# Base Ubuntu 24.04 LTS : Python 3.12 et Tesseract 5.3 dans les dépôts officiels.
# =============================================================================
ARG BASE_IMAGE=ubuntu:24.04

# ---------------------------------------------------------------- dépendances
FROM ${BASE_IMAGE} AS builder
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3.12 python3.12-venv ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN python3.12 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY CODE/requirements.txt /tmp/requirements.txt
# Un proxy d'entreprise qui réécrit TLS peut fournir son certificat comme secret de build :
# il sert uniquement pendant l'installation et n'est jamais copié dans l'image.
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -s /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install -r /tmp/requirements.txt

# ---------------------------------------------------------------- exécution
FROM ${BASE_IMAGE} AS runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3.12 tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng \
      ca-certificates tini \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --home-dir /app app
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app/CODE
COPY --chown=root:root CODE/ /app/CODE/
COPY --chown=root:root data/synthetic_data/referentials/ /app/data/synthetic_data/referentials/
COPY --chown=root:root data/sample_documents/ /app/data/sample_documents/
RUN mkdir -p /app/data/uploads && chown app:app /app/data/uploads
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp \
    DOCUMENTS_DIR=/app/data/sample_documents UPLOADS_DIR=/app/data/uploads
USER app
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=90s --retries=5 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "backend.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
