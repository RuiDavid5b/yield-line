"""
Unit tests for auth routes.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from stock_news.api.main import app
from stock_news.auth import routes as auth_routes
from stock_news.auth.dependencies import require_csrf

client = TestClient(app)


class TestRegister:
    def test_success_returns_201(self, monkeypatch):
        monkeypatch.setattr(auth_routes, "sign_up", lambda email, password: "sub-123")
        response = client.post(
            "/auth/register", json={"email": "a@example.com", "password": "Password1"}
        )
        assert response.status_code == 201

    def test_duplicate_email_returns_400(self, monkeypatch):
        def raise_exists(email, password):
            raise auth_routes.CognitoError("An account with this email already exists.")

        monkeypatch.setattr(auth_routes, "sign_up", raise_exists)

        response = client.post(
            "/auth/register", json={"email": "a@example.com", "password": "Password1"}
        )
        assert response.status_code == 400


class TestLogin:
    def test_success_sets_cookie_and_returns_csrf_token(self, monkeypatch):
        monkeypatch.setattr(
            auth_routes,
            "initiate_auth",
            lambda email, password: {
                "AccessToken": "at",
                "IdToken": "irrelevant-opaque-string",
                "RefreshToken": "rt",
                "ExpiresIn": 3600,
            },
        )
        monkeypatch.setattr(
            auth_routes, "verify_id_token", lambda token: {"sub": "sub-123"}
        )
        monkeypatch.setattr(
            auth_routes, "get_or_create_user", lambda db_session, sub, email: None
        )
        monkeypatch.setattr(
            auth_routes,
            "create_session",
            lambda sub, email, result: ("session-xyz", "csrf-abc"),
        )

        response = client.post(
            "/auth/login", json={"email": "a@example.com", "password": "Password1"}
        )

        assert response.status_code == 200
        assert response.json()["csrf_token"] == "csrf-abc"
        assert "session_id" in response.cookies

    def test_wrong_credentials_returns_401(self, monkeypatch):
        def raise_unauthorized(email, password):
            raise auth_routes.CognitoError("Incorrect email or password.")

        monkeypatch.setattr(auth_routes, "initiate_auth", raise_unauthorized)

        response = client.post(
            "/auth/login", json={"email": "a@example.com", "password": "wrong"}
        )
        assert response.status_code == 401

    def test_token_verification_failure_returns_500(self, monkeypatch):
        import jwt as jwt_module

        monkeypatch.setattr(
            auth_routes,
            "initiate_auth",
            lambda email, password: {
                "AccessToken": "at",
                "IdToken": "bad-token",
                "RefreshToken": "rt",
                "ExpiresIn": 3600,
            },
        )

        def raise_invalid(token):
            raise jwt_module.InvalidTokenError("bad signature")

        monkeypatch.setattr(auth_routes, "verify_id_token", raise_invalid)

        response = client.post(
            "/auth/login", json={"email": "a@example.com", "password": "Password1"}
        )

        assert response.status_code == 500


def _fake_id_token() -> str:
    import jwt

    return jwt.encode({"sub": "sub-123"}, "secret", algorithm="HS256")


class TestMeAndProtectedRoutes:
    def test_me_without_session_returns_401(self):
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_agent_ask_without_session_returns_401(self):
        response = client.post("/agent/ask", json={"question": "hi", "thread_id": "t1"})
        assert response.status_code == 401


@pytest.fixture
def session():
    return {"session_id": "session-123"}


class TestRequireCsrf:
    def test_missing_header_returns_403(self, session, monkeypatch):
        monkeypatch.setattr(
            "stock_news.auth.dependencies.validate_csrf",
            lambda session_id, token: False,
        )

        with pytest.raises(HTTPException) as exc_info:
            require_csrf(session=session, x_csrf_token=None)

        assert exc_info.value.status_code == 403

    def test_wrong_token_returns_403(self, session, monkeypatch):
        monkeypatch.setattr(
            "stock_news.auth.dependencies.validate_csrf",
            lambda session_id, token: False,
        )

        with pytest.raises(HTTPException) as exc_info:
            require_csrf(session=session, x_csrf_token="wrong-token")

        assert exc_info.value.status_code == 403

    def test_correct_token_passes(self, session, monkeypatch):
        monkeypatch.setattr(
            "stock_news.auth.dependencies.validate_csrf",
            lambda session_id, token: True,
        )

        assert (
            require_csrf(
                session=session,
                x_csrf_token="csrf-abc",
            )
            is None
        )
