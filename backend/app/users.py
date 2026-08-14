"""Persistent, SuperAdmin-managed user accounts.

Complements the built-in env-configured ADMIN/SuperAdmin accounts
(frontend .env) — accounts created here are additional logins, stored
in backend/data/users.json. Passwords are hashed with bcrypt
(per-password salt, tunable work factor) — never stored in plain text,
and never as a fast unsalted hash that's cheap to brute-force offline.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import bcrypt

logger = logging.getLogger(__name__)

_USERS_FILE = Path(os.getenv("USERS_FILE", str(Path(__file__).resolve().parent.parent / "data" / "users.json")))

ROLES = ("ADMIN", "SuperAdmin")


def _load() -> list[dict]:
    if not _USERS_FILE.exists():
        return []
    return json.loads(_USERS_FILE.read_text(encoding="utf-8"))


def _save(users: list[dict]) -> None:
    _USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _matches(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Hash isn't a valid bcrypt hash (e.g. leftover from an older scheme) —
        # treat as no match rather than raising.
        return False


def list_users() -> list[dict]:
    return [{"username": u["username"], "role": u["role"]} for u in _load()]


def add_user(username: str, password: str, role: str) -> None:
    username = username.strip()
    if not username or not password:
        raise ValueError("Username and password are required")
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")

    users = _load()
    if any(u["username"].lower() == username.lower() for u in users):
        logger.warning("User creation rejected: username=%s already exists", username)
        raise ValueError(f"User '{username}' already exists")

    users.append({"username": username, "password_hash": _hash(password), "role": role})
    _save(users)
    logger.info("User created: username=%s role=%s", username, role)


def verify_user(username: str, password: str) -> Optional[str]:
    """Returns the user's role if credentials match, else None."""
    for u in _load():
        if u["username"].lower() == username.strip().lower() and _matches(password, u["password_hash"]):
            return u["role"]
    return None
