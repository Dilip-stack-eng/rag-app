import os
import warnings

from dotenv import load_dotenv

load_dotenv()

# All mutable runtime state (vector DB, uploads, quarantine, logs, local
# user/usage stores) lives under one data/ root, sibling to app/ — keeps the
# source tree free of anything that isn't version-controlled code.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA_DIR = os.path.join(_BACKEND_DIR, "data")

# ---- Gemini API (replaces the local Ollama model) ----
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-2.5-flash")
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
# Max tokens the model may generate in one answer — raised so elaborate/detailed
# answers (see prompts.json v4) aren't cut off early. Gemini's context window
# itself is large and fixed per model, not a client-tunable request option the
# way Ollama's num_ctx was, so there's no equivalent setting here anymore.
LLM_NUM_PREDICT = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "2048"))

if not GEMINI_API_KEY:
    warnings.warn(
        "GEMINI_API_KEY is not set — LLM calls will fail until you add it to backend/.env.",
        stacklevel=1,
    )

CHROMA_DIR = os.getenv("CHROMA_DIR", os.path.join(_DATA_DIR, "chroma"))
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "documents")

# ---- CORS ----
# Comma-separated list of allowed origins, e.g. "https://athena-frontend.onrender.com".
# Defaults to "*" for local development; set explicitly before deploying anywhere
# beyond localhost.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
TOP_K = int(os.getenv("TOP_K", "10"))

# Which system prompt version to use — see app/prompts.py for the full history
# and what each version does. Set to "v1"/"v2"/"v3"/"v4" to pin or roll back.
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v4")

# ---- Login lockout alerts ----
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)
# STARTTLS (upgrade a plaintext connection, typically port 587) is used by default.
# Set SMTP_PORT=465 for implicit TLS/SSL instead (STARTTLS is skipped automatically).
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() in ("1", "true", "yes")

ALERT_ADMIN_EMAIL = os.getenv("ALERT_ADMIN_EMAIL", "dilipkumar.sundaravadivel@athena.com")
ALERT_ADMIN_MOBILE = os.getenv("ALERT_ADMIN_MOBILE", "7092539546")
# Carrier email-to-SMS gateway domain, e.g. txt.att.net / vtext.com / tmomail.net.
# Leave blank to skip the SMS leg (email alert still sends).
ALERT_MOBILE_GATEWAY_DOMAIN = os.getenv("ALERT_MOBILE_GATEWAY_DOMAIN", "")

# ---- Upload virus scanning (YARA) ----
YARA_ENABLED = os.getenv("YARA_ENABLED", "true").strip().lower() in ("1", "true", "yes")
YARA_TIMEOUT_SECONDS = int(os.getenv("YARA_TIMEOUT_SECONDS", "30"))

# ---- Upload limits & storage ----
# Both directories live under backend/data/ — this app never mounts a static
# file server, so nothing under either path is ever web-reachable regardless.
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))
UPLOAD_ARCHIVE_DIR = os.getenv("UPLOAD_ARCHIVE_DIR", os.path.join(_DATA_DIR, "uploads"))
QUARANTINE_DIR = os.getenv("QUARANTINE_DIR", os.path.join(_DATA_DIR, "quarantine"))
# Zip-bomb guard for .docx (itself a zip archive): reject if the archive would
# expand past this many uncompressed MB, or if any single entry's compression
# ratio is absurd.
MAX_DOCX_UNCOMPRESSED_MB = int(os.getenv("MAX_DOCX_UNCOMPRESSED_MB", "200"))
MAX_ZIP_COMPRESSION_RATIO = int(os.getenv("MAX_ZIP_COMPRESSION_RATIO", "100"))

# ---- Built-in accounts ----
# The backend is the sole source of truth for auth (see app/auth/auth.py) —
# every login, including the frontend's quick-sign-in buttons, still goes
# through POST /auth/login and is validated against these same values.
# The frontend also has its own copy of these (frontend/.env) solely to
# send as the quick-sign-in buttons' password — keep both files in sync.
APP_USERNAME = os.getenv("APP_USERNAME", "ADMIN")
APP_PASSWORD = os.getenv("APP_PASSWORD", "12345")
SUPERADMIN_USERNAME = os.getenv("SUPERADMIN_USERNAME", "SuperAdmin")
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "12345")

# ---- JWT auth ----
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-insecure-secret-change-me-before-deploying")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))

if JWT_SECRET_KEY == "dev-insecure-secret-change-me-before-deploying":
    warnings.warn(
        "JWT_SECRET_KEY is using the default dev value — set a random secret in "
        "backend/.env before deploying anywhere beyond localhost.",
        stacklevel=1,
    )
