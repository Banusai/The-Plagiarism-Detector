from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import ADMIN_PASSWORD, ADMIN_TOKEN_SECRET, ADMIN_USERNAME

bearer_scheme = HTTPBearer(auto_error=False)
TOKEN_TTL_SECONDS = 8 * 60 * 60


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode_b64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def ensure_admin_configured() -> None:
    if not ADMIN_USERNAME or not ADMIN_PASSWORD or len(ADMIN_TOKEN_SECRET) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Administrator login is not configured. Set ADMIN_USERNAME, "
                "ADMIN_PASSWORD and a random ADMIN_TOKEN_SECRET (at least 32 characters) in backend/.env."
            ),
        )


def authenticate_admin(username: str, password: str) -> str:
    ensure_admin_configured()
    username_ok = hmac.compare_digest(username.encode(), ADMIN_USERNAME.encode())
    password_ok = hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode())
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator username or password.",
        )

    payload = {
        "sub": ADMIN_USERNAME,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    encoded_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(
        ADMIN_TOKEN_SECRET.encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_b64url(signature)}"


def require_admin(
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    ensure_admin_configured()
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator login required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        encoded_payload, encoded_signature = credentials.credentials.split(".", 1)
        expected = hmac.new(
            ADMIN_TOKEN_SECRET.encode(),
            encoded_payload.encode(),
            hashlib.sha256,
        ).digest()
        supplied = _decode_b64url(encoded_signature)
        if not hmac.compare_digest(expected, supplied):
            raise ValueError("Invalid signature")
        payload = json.loads(_decode_b64url(encoded_payload))
        if payload.get("sub") != ADMIN_USERNAME or int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("Expired or invalid token")
        return str(payload["sub"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator session is invalid or expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
