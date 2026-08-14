"""Per-user daily LLM token quotas.

Every authenticated user (ADMIN or SuperAdmin alike) shares the same daily
token budget — tracked individually per username, reset at UTC midnight.
The budget itself is a single global setting: readable by anyone, but only
changeable by a SuperAdmin (enforced by the caller — see main.py's
require_role dependency on POST /token-limit; this module has no concept
of roles, it just does the bookkeeping).

Persisted to token_usage.json so usage survives a backend restart within
the same day — an in-memory-only counter would let someone reset their
quota just by restarting the server.
"""

import json
import logging
import os
import time
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

_STORE_FILE = Path(os.getenv("TOKEN_USAGE_FILE", str(Path(__file__).parent / "token_usage.json")))
_lock = Lock()

DEFAULT_DAILY_LIMIT = 50000


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _load() -> dict:
    if _STORE_FILE.exists():
        data = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
    else:
        data = {"daily_limit": DEFAULT_DAILY_LIMIT, "date": _today(), "usage": {}}

    if data.get("date") != _today():
        data["date"] = _today()
        data["usage"] = {}
        _STORE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return data


def _save(data: dict) -> None:
    _STORE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_daily_limit() -> int:
    with _lock:
        return _load().get("daily_limit", DEFAULT_DAILY_LIMIT)


def set_daily_limit(new_limit: int, changed_by: str) -> None:
    if new_limit <= 0:
        raise ValueError("Daily token limit must be a positive number")
    with _lock:
        data = _load()
        old_limit = data.get("daily_limit", DEFAULT_DAILY_LIMIT)
        data["daily_limit"] = new_limit
        _save(data)
    logger.warning("Daily token limit changed: %d -> %d by %s", old_limit, new_limit, changed_by)


def get_usage_today(username: str) -> int:
    with _lock:
        return _load().get("usage", {}).get(username, 0)


def record_usage(username: str, tokens: int) -> int:
    """Adds tokens to today's usage for username. Returns the new running total."""
    if tokens <= 0:
        return get_usage_today(username)
    with _lock:
        data = _load()
        usage = data.setdefault("usage", {})
        usage[username] = usage.get(username, 0) + tokens
        _save(data)
        new_total = usage[username]
    logger.info("Token usage recorded: user=%s tokens=%d today_total=%d", username, tokens, new_total)
    return new_total


def remaining_today(username: str) -> int:
    return max(0, get_daily_limit() - get_usage_today(username))


def status(username: str) -> dict:
    limit = get_daily_limit()
    used = get_usage_today(username)
    return {"used": used, "limit": limit, "remaining": max(0, limit - used)}
