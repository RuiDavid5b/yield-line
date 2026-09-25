"""
FastAPI dependencies for session-based auth and CSRF protection.
"""

from __future__ import annotations

import time

from fastapi import Cookie, Depends, Header, HTTPException, status

from stock_news.auth.cognito_client import CognitoError, refresh_auth
from stock_news.auth.session import get_session, update_session_tokens, validate_csrf

SESSION_COOKIE_NAME = "session_id"
REFRESH_MARGIN_SECONDS = 5 * 60


def get_current_session(
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)
) -> dict:
    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    session = get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    if time.time() >= session.get("expires_at", 0) - REFRESH_MARGIN_SECONDS:
        try:
            auth_result = refresh_auth(session["refresh_token"])
        except CognitoError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired, please log in again",
            )
        update_session_tokens(session_id, auth_result)
        session["access_token"] = auth_result["AccessToken"]
        session["expires_at"] = time.time() + auth_result["ExpiresIn"]

    return {**session, "session_id": session_id}


def require_csrf(
    session: dict = Depends(get_current_session),
    x_csrf_token: str | None = Header(default=None),
) -> None:
    if x_csrf_token is None or not validate_csrf(session["session_id"], x_csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token",
        )
