# ─────────────────────────────────────────────────────────────
# SCICS — SIUT Clinical ICD Coding System
# Dockerfile for the FastAPI backend + NLP pipeline
#
# Build:  docker compose build
# Run:    docker compose up
#
# NOT included in this image: the PyQt6 desktop UI (admin_dash.py,
# codingworkspace.py, chatbot.py, UI/) — the coder installs those
# on their workstation because they need a graphical display.
# ─────────────────────────────────────────────────────────────

FROM python:3.10-slim

# System packages needed by:
#   - medspaCy / scispaCy (compile some C extensions during pip install)
#   - psycopg2 (bundled with the -binary variant, but g++ is a safety net)
#   - HEALTHCHECK curl below
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ─── Layer 1: Python dependencies ────────────────────────────
# Copied and installed first so Docker caches this layer.
# Rebuilding after code changes skips the ~10-minute pip install.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ─── Layer 2: spaCy / scispaCy models ────────────────────────
# Installed during BUILD, not at container startup — otherwise
# every restart would re-download ~500MB.
#   en_core_web_sm        — general English NLP (used indirectly)
#   en_ner_bc5cdr_md      — clinical NER used by nlp/nlp_extractor.py;
#                           installed from scispaCy's release URL because
#                           it isn't on PyPI.
RUN python -m spacy download en_core_web_sm \
 && pip install --no-cache-dir \
    https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz

# ─── Layer 3: application code ───────────────────────────────
# Copied last because it changes on almost every commit.
# The .dockerignore file controls what actually gets copied.
COPY . .

# ─── Security: run as non-root ───────────────────────────────
# FastAPI/uvicorn should never run as root inside a container.
RUN useradd --create-home --shell /bin/bash khidmat \
 && chown -R khidmat:khidmat /app
USER khidmat

# The API listens on port 8000
EXPOSE 8000

# Liveness probe — main.py exposes GET / that returns 200 OK.
# start-period 60s gives the NLP models time to load on first boot.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Production entrypoint.
#   --host 0.0.0.0        must, else the container port isn't reachable from outside
#   --port 8000           matches EXPOSE and docker-compose port mapping
#   --timeout-keep-alive  matches the value from the Procfile
# NO --reload here (that's dev-only, watches files, wastes memory).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "120"]
