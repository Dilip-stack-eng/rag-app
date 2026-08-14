#!/usr/bin/env bash
# Starts both services in one container. If either process dies, the whole
# container exits (rather than limping along with just one service up) so
# `docker run --restart` / an orchestrator notices and can recover it.
set -euo pipefail

cd /app/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
backend_pid=$!

cd /app/frontend
streamlit run app.py \
    --server.port 8501 \
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
