# Simple RAG (Gemini + Chroma + Streamlit + FastAPI)

Upload documents, embed and store them in ChromaDB, and ask questions
answered by Google's Gemini API using retrieved context.

## Architecture

- **backend/** — FastAPI service: chunks uploads, embeds via the Gemini API, stores/retrieves
  vectors in a local persistent ChromaDB collection, and generates answers via the Gemini API.
- **frontend/** — Streamlit UI: upload documents and chat with them via the backend API.

## Prerequisites

1. Get a Gemini API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
2. Set `GEMINI_API_KEY` in `backend/.env` (see `backend/.env.example`).
   (To use different models, set `GEMINI_LLM_MODEL` / `GEMINI_EMBED_MODEL`.)
3. [`uv`](https://docs.astral.sh/uv/) — manages a single Python 3.12 environment
   (pinned in `.python-version`) for both services. Python 3.12 is required
   specifically because `yara-python` only ships prebuilt Windows wheels up
   to that version.

## Setup

From the repo root:
```
uv sync
```
This creates one shared `.venv/` covering both `backend/` and `frontend/`.

## Run

Backend (from the repo root):
```
uv run --directory backend uvicorn app.main:app --reload --port 8000
```

Frontend (from the repo root, in a separate terminal):
```
uv run --directory frontend streamlit run app.py
```

Then open the Streamlit URL, upload a `.txt` or `.pdf` file in the sidebar, and ask questions in the chat box.

## API

- `POST /upload` — multipart file upload (`.txt` or `.pdf`), chunks + embeds + stores it.
- `POST /query` — `{"question": "...", "top_k": 4}` → `{"answer": "...", "sources": [...]}`.
- `GET /documents` — list ingested source filenames.
- `DELETE /documents` — clear the vector store.
- `GET /health` — health check.

## Config

All settings are environment variables (see `backend/.env.example` and `frontend/.env.example`):

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(none)* | Gemini API key — required |
| `GEMINI_LLM_MODEL` | `gemini-2.5-flash` | Chat/generation model |
| `GEMINI_EMBED_MODEL` | `gemini-embedding-001` | Embedding model |
| `GEMINI_MAX_OUTPUT_TOKENS` | `2048` | Max tokens generated per answer |
| `CHROMA_DIR` | `backend/data/chroma` | Local Chroma persistence directory |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1000` / `200` | Text chunking params (characters) |
| `TOP_K` | `4` | Number of chunks retrieved per query |
| `CORS_ORIGINS` | `*` | Comma-separated allowed frontend origin(s) |
| `YARA_ENABLED` | `true` | Toggle malware scanning on uploads |
| `USERS_FILE` / `TOKEN_USAGE_FILE` / `LOG_DIR` | *(inside `backend/data/`)* | Override to relocate onto a persistent disk (e.g. on Render) |
| `BACKEND_URL` (frontend) | `http://localhost:8000` | Where Streamlit sends API requests |

## Running with Docker

A single `Dockerfile` at the repo root builds one image that runs both
services together (backend on `:8000`, frontend on `:8501` — see
`docker-entrypoint.sh`). Secrets and runtime data are deliberately kept out
of the image itself (see `.dockerignore`):

```
docker build -t athena .

docker run -p 8501:8501 -p 8000:8000 \
  --env-file backend/.env \
  -v athena-data:/app/backend/data \
  athena
```

- `--env-file backend/.env` supplies `GEMINI_API_KEY` and everything else
  in [Config](#config) at container start — it's read from your local file,
  never baked into the image.
- `-v athena-data:/app/backend/data` persists the Chroma DB, uploads,
  quarantine, `users.json`, and `token_usage.json` across container
  restarts. Omit it for a throwaway/ephemeral run.
- Open `http://localhost:8501` once it's up. The container exits if either
  service crashes, so `docker run --restart unless-stopped` is worth adding
  for anything longer-lived than a local test.

## Deploying to Render

This repo includes `render.yaml`, a Blueprint that deploys `backend/` and
`frontend/` as two separate web services with a small persistent disk
attached to the backend (for ChromaDB, uploads, quarantine, `users.json`,
`token_usage.json`, and logs — Render's filesystem is otherwise ephemeral
and wipes on every restart/redeploy).

1. Push this repo to GitHub/GitLab.
2. In the Render dashboard: **New → Blueprint**, select the repo. Render
   reads `render.yaml` and proposes both services.
3. Before applying, fill in the env vars marked `sync: false` in
   `render.yaml` (Render prompts for these in the UI) — at minimum
   `GEMINI_API_KEY`, `APP_PASSWORD`, `SUPERADMIN_PASSWORD`.
4. Apply. Once both services are live, Render has assigned each a URL —
   copy them across the two services (this can't be pre-filled since the
   URLs don't exist until the services are created):
   - `athena-frontend` → set `BACKEND_URL` to the `athena-backend` URL.
   - `athena-backend` → set `CORS_ORIGINS` to the `athena-frontend` URL.
5. Redeploy both services so the new env vars take effect.

Notes:
- The backend's `plan: starter` is required because persistent disks aren't
  available on Render's free tier. The frontend can be downgraded to `plan:
  free` if you don't mind its cold-start sleep after inactivity.
- Malware scanning uses `yara-python`, a pip package with prebuilt wheels
  for common Linux Python versions — no Docker image or apt packages
  required, unlike the ClamAV approach this replaced.
- Re-upload your documents after the first deploy — a fresh Chroma
  collection starts empty.
