"""Server-side login throttling for POST /auth/login.

The Streamlit UI already has its own CAPTCHA + 3-attempt lockout, but that
logic lives entirely in the frontend — it never touches this API. Anyone
who calls /auth/login directly (curl, a script, a different client)
bypasses it completely and gets unlimited guesses. This module is the
backstop: it tracks failures per-username in-process and locks the
*account*, regardless of which client or how many browser tabs the
attempts came from.

In-memory and per-process by design — fine for this app's scale (a single
FastAPI worker). It resets on restart; that's an acceptable trade-off here
versus adding an external store for a login-attempt counter.
"""

import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
LOCKOUT_SECONDS = 60

# Extra seconds layered on top of LOCKOUT_SECONDS when an AI risk assessment
# (rag.assess_lockout(), applied in main.py's /auth/login) judges a failure
# burst likely automated rather than an ordinary human mistake. "low" adds
# nothing. This can only ever make a lockout longer than the deterministic
# baseline above — never shorter, and the baseline itself is never skipped
# regardless of what the AI assessment says or whether it's available at all.
RISK_EXTENSION_SECONDS = {"low": 0, "medium": 120, "high": 240}

_state_lock = Lock()
_state: dict[str, dict] = {}  # normalized username -> {"failures": int, "locked_until": float | None}


def _key(username: str) -> str:
    return username.strip().lower()


def is_locked(username: str) -> tuple[bool, int]:
    """Returns (locked, seconds_remaining)."""
    with _state_lock:
        entry = _state.get(_key(username))
        if not entry or not entry.get("locked_until"):
            return False, 0
        remaining = entry["locked_until"] - time.time()
        if remaining <= 0:
            _state.pop(_key(username), None)
            logger.info("Lockout expired: username=%s", username)
            return False, 0
        return True, int(remaining) + 1


def record_failure(username: str) -> tuple[bool, int]:
    """Records a failed attempt. Returns (just_locked, attempts_remaining)."""
    with _state_lock:
        key = _key(username)
        entry = _state.setdefault(key, {"failures": 0, "locked_until": None, "timestamps": []})
        entry["failures"] += 1
        entry["timestamps"].append(time.time())
        if entry["failures"] >= MAX_ATTEMPTS:
            entry["locked_until"] = time.time() + LOCKOUT_SECONDS
            logger.warning(
                "Account locked: username=%s failures=%d lockout_seconds=%d",
                username, entry["failures"], LOCKOUT_SECONDS,
            )
            return True, 0
        remaining = MAX_ATTEMPTS - entry["failures"]
        logger.info("Failed login recorded: username=%s attempts_remaining=%d", username, remaining)
        return False, remaining


def extend_lockout(username: str, extra_seconds: int) -> None:
    """Adds extra_seconds on top of an already-locked username's expiry —
    used after an AI risk assessment judges the failure burst likely
    automated (see RISK_EXTENSION_SECONDS). No-op if the username isn't
    currently locked, or if extra_seconds isn't positive: this function
    only ever lengthens an existing lock, it can't create one or shorten
    one, so a caller passing a bad value can't accidentally weaken it."""
    if extra_seconds <= 0:
        return
    with _state_lock:
        entry = _state.get(_key(username))
        if not entry or not entry.get("locked_until"):
            return
        entry["locked_until"] += extra_seconds
        logger.warning(
            "Lockout extended by AI risk assessment: username=%s extra_seconds=%d",
            username, extra_seconds,
        )


def record_success(username: str) -> None:
    with _state_lock:
        had_failures = _key(username) in _state
        _state.pop(_key(username), None)
        if had_failures:
            logger.info("Failure count reset after successful login: username=%s", username)


def list_status() -> list[dict]:
    """Snapshot of every username with a nonzero failure count, for the
    SuperAdmin-only Control Panel view. Only usernames that have failed at
    least once show up here — the whole point of this module being
    in-memory is that it doesn't accumulate a permanent record of everyone
    who has ever logged in successfully."""
    with _state_lock:
        now = time.time()
        result = []
        for username, entry in _state.items():
            locked_until = entry.get("locked_until")
            locked = bool(locked_until and locked_until > now)
            result.append({
                "username": username,
                "failures": entry["failures"],
                "locked": locked,
                "remaining_seconds": int(locked_until - now) + 1 if locked else 0,
            })
        return sorted(result, key=lambda r: (-r["locked"], -r["failures"]))


def get_attempt_span(username: str) -> tuple[int, float]:
    """Returns (attempt_count, seconds_between_first_and_last_recorded_failure)
    for the current burst of failures — e.g. 3 attempts within 8 seconds
    looks very different from 3 attempts spread over several minutes. Feeds
    rag.assess_lockout() (main.py's /auth/login), which may in turn call
    extend_lockout() above — this function itself only reads state, it
    doesn't lock or unlock anything."""
    with _state_lock:
        entry = _state.get(_key(username))
        if not entry or not entry.get("timestamps"):
            return 0, 0.0
        timestamps = entry["timestamps"]
        span = timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0.0
        return len(timestamps), span
