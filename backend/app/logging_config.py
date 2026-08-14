"""Centralized logging setup for the backend.

configure_logging() is called once from app/__init__.py, before any other
submodule runs — every module then just does
`logger = logging.getLogger(__name__)` and logs normally.

Logs go to both the console and a rotating file (backend/logs/app.log) so
they survive process restarts and don't grow unbounded.

Never log secrets: passwords, JWTs, JWT_SECRET_KEY, SMTP credentials, or
raw restricted-field/PII values before masking. Log usernames, roles,
filenames, outcomes, and counts instead.
"""

import logging
import logging.handlers
import os
from pathlib import Path

_LOG_DIR = Path(os.getenv("LOG_DIR", str(Path(__file__).resolve().parent.parent / "data" / "logs")))
_LOG_FILE = _LOG_DIR / "app.log"

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    _configured = True

    _LOG_DIR.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Quiet down noisy third-party loggers so our own events aren't buried.
    for noisy in ("httpx", "httpcore", "chromadb", "urllib3", "python_multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def tail(limit: int = 200) -> list[str]:
    """Last `limit` lines of the log file, oldest first. Used by the
    Training log / Security views in the UI — this is the only place that
    reads the log file back out."""
    if not _LOG_FILE.exists():
        return []
    with _LOG_FILE.open("r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return [line.rstrip("\n") for line in lines[-limit:]]
