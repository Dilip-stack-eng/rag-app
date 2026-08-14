#!/usr/bin/env bash
# Starts both services in one container. If either process dies, the whole
# container exits (rather than limping along with just one service up) so
# `docker run --restart` / an orchestrator notices and can recover it.
set -euo pipefail

# BACKEND_BIND_HOST defaults to 0.0.0.0 so a plain `docker run -p 8000:8000
# -p 8501:8501` (see README) can reach the backend directly. On a platform
# that only routes external traffic to a single port per service — e.g. a
# Render "web service" built straight from this Dockerfile, as opposed to
# the two-service render.yaml Blueprint — set BACKEND_BIND_HOST=127.0.0.1
# so the backend is reachable only from inside this container (the
# frontend still reaches it fine over loopback) and isn't mistakenly
# auto-detected as the public port instead of the frontend.
BACKEND_HOST="${BACKEND_BIND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
# PORT is set automatically by platforms like Render for whichever process
# should be externally reachable; falls back to 8501 for local `docker run`.
FRONTEND_PORT="${PORT:-8501}"

cd /app/backend
uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
backend_pid=$!

cd /app/frontend
export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:$BACKEND_PORT}"
streamlit run app.py \
    --server.port "$FRONTEND_PORT" \
    --server.address 0.0.0.0 \
    --server.headless true &
frontend_pid=$!

terminate() {
    kill -TERM "$backend_pid" "$frontend_pid" 2>/dev/null || true
}
trap terminate TERM INT

set +e
wait -n "$backend_pid" "$frontend_pid"
exit_code=$?
set -e

terminate
exit "$exit_code"
