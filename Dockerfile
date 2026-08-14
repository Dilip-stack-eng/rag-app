# Single image running both services (FastAPI backend on :8000, Streamlit
# frontend on :8501) — see docker-entrypoint.sh for how they're started
# together. Uses the same uv-managed dependency set as local dev
# (pyproject.toml / uv.lock), so no separate backend/frontend requirements
# files are involved here.
FROM python:3.12-slim

# Pinned to the uv version used to generate uv.lock locally, for reproducible builds.
COPY --from=ghcr.io/astral-sh/uv:0.12.4 /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependencies first, as their own layer — only re-installed when the
# lockfile actually changes, not on every source edit.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen

# App source. Deliberately not `COPY . .` — backend/.env, backend/data/,
# and other runtime/secret paths must never end up baked into the image
# (see .dockerignore); real config comes in via `docker run -e` /
# `--env-file` at container start, and runtime data via a volume mount.
COPY backend/app ./backend/app
COPY frontend/app.py frontend/.streamlit ./frontend/
COPY docker-entrypoint.sh ./

RUN chmod +x docker-entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

# backend/data/ (Chroma DB, uploads, quarantine, logs, users.json,
# token_usage.json) — mount a volume here to persist across container
# restarts, e.g. `docker run -v athena-data:/app/backend/data ...`.
VOLUME ["/app/backend/data"]

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
