"""Signed, expiring sessions for the single-user hosted application."""

from __future__ import annotations

import hashlib
import hmac
import time
from http.cookies import SimpleCookie

SESSION_COOKIE_NAME = "poetry_session"


def create_session_value(secret: str, max_age_seconds: int, *, now: int | None = None) -> str:
    issued_at = int(time.time()) if now is None else now
    expires_at = issued_at + max_age_seconds
    payload = str(expires_at)
    signature = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256)
    return f"{payload}.{signature.hexdigest()}"


def is_valid_session_value(secret: str, value: str, *, now: int | None = None) -> bool:
    try:
        expires_raw, supplied_signature = value.split(".", maxsplit=1)
        expires_at = int(expires_raw)
    except (TypeError, ValueError):
        return False

    current_time = int(time.time()) if now is None else now
    if expires_at < current_time:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        expires_raw.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(supplied_signature, expected)


def session_from_cookie_header(cookie_header: str) -> str:
    cookie = SimpleCookie()
    try:
        cookie.load(cookie_header)
    except Exception:
        return ""
    morsel = cookie.get(SESSION_COOKIE_NAME)
    return morsel.value if morsel is not None else ""
