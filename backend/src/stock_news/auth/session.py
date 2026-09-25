"""
Redis-backed server-side sessions. The browser only holds an
HttpOnly/Secure/SameSite cookie. Cognito tokens and the CSRF token live here,
never sent to the browser except the CSRF token itself, returned once in a
JSON response body for the frontend to hold in memory.
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

import redis

from stock_news.config import get_settings

SESSION_TTL_SECONDS = 30 * 24 * 60 * 60  # matches Cognito's refresh_token_validity
SESSION_KEY_PREFIX = "session:"


def _client() -> redis.Redis:
    return redis.Redis.from_url(str(get_settings().redis_url), decode_responses=True)


def create_session(user_sub: str, email: str, auth_result: dict) -> tuple[str, str]:
    """
    Create a new session after successful login. Returns (session_id, csrf_token).
    """
    session_id = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)

    data = {
        "user_sub": user_sub,
        "email": email,
        "access_token": auth_result["AccessToken"],
        "id_token": auth_result["IdToken"],
        "refresh_token": auth_result["RefreshToken"],
        "expires_at": time.time() + auth_result["ExpiresIn"],
        "csrf_token": csrf_token,
    }
    _client().set(
        f"{SESSION_KEY_PREFIX}{session_id}", json.dumps(data), ex=SESSION_TTL_SECONDS
    )
    return session_id, csrf_token


def get_session(session_id: str) -> dict[str, Any] | None:
    raw = _client().get(f"{SESSION_KEY_PREFIX}{session_id}")
    return json.loads(raw) if raw is not None else None


def update_session_tokens(session_id: str, auth_result: dict) -> None:
    """
    Called after a token refresh - keeps csrf_token and user identity,
    replaces only the Cognito tokens.
    """
    existing = get_session(session_id)
    if existing is None:
        return
    existing["access_token"] = auth_result["AccessToken"]
    existing["id_token"] = auth_result.get("IdToken", existing["id_token"])
    existing["expires_at"] = time.time() + auth_result["ExpiresIn"]
    if "RefreshToken" in auth_result:
        existing["refresh_token"] = auth_result["RefreshToken"]
    _client().set(
        f"{SESSION_KEY_PREFIX}{session_id}",
        json.dumps(existing),
        ex=SESSION_TTL_SECONDS,
    )


def delete_session(session_id: str) -> None:
    _client().delete(f"{SESSION_KEY_PREFIX}{session_id}")


def validate_csrf(session_id: str, submitted_token: str) -> bool:
    session = get_session(session_id)
    if session is None:
        return False
    return secrets.compare_digest(session["csrf_token"], submitted_token)
