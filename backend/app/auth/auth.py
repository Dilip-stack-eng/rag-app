"""JWT issuance and validation for the API.

The backend is the single source of truth for authentication — both the
built-in ADMIN/SuperAdmin accounts (config.py) and users created via
users.add_user() are checked here, in one place, and both get tokens from
the same issuer. Every protected route depends on require_role(...) so
role checks live at the API boundary instead of being trusted from
whatever the frontend UI happens to hide.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import users
from ..core import config

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def authenticate_user(username: str, password: str) -> Optional[str]:
    """Returns the role ('ADMIN' | 'SuperAdmin') if credentials are valid, else None."""
    if username == config.SUPERADMIN_USERNAME and password == config.SUPERADMIN_PASSWORD:
        role = "SuperAdmin"
    elif username == config.APP_USERNAME and password == config.APP_PASSWORD:
        role = "ADMIN"
    else:
        role = users.verify_user(username, password)

    if role:
        logger.info("Authentication succeeded: username=%s role=%s", username, role)
    else:
        logger.warning("Authentication failed: username=%s", username)
    return role


def account_exists(username: str) -> bool:
    """Whether username names a real account at all (built-in ADMIN/SuperAdmin
    or one created via users.add_user()) — independent of whether the password
    supplied alongside it was correct. Used to keep login-throttle lockout,
    AI risk assessment, and admin alert emails scoped to real accounts instead
    of triggering for made-up usernames that were never registered."""
    return username in (config.SUPERADMIN_USERNAME, config.APP_USERNAME) or users.user_exists(username)


def create_token(username: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=config.JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("Token rejected: expired")
        raise HTTPException(401, "Session expired, please log in again")
    except jwt.InvalidTokenError:
        logger.warning("Token rejected: invalid/malformed")
        raise HTTPException(401, "Invalid authentication token")


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> dict:
    if creds is None:
        logger.warning("Request rejected: no Authorization header")
        raise HTTPException(401, "Not authenticated")
    payload = _decode(creds.credentials)
    return {"username": payload["sub"], "role": payload["role"]}


def require_role(*roles: str):
    def _dependency(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            logger.warning(
                "Authorization denied: username=%s role=%s required=%s",
                user["username"], user["role"], "|".join(roles),
            )
            raise HTTPException(403, f"Requires role: {' or '.join(roles)}")
        return user

    return _dependency
