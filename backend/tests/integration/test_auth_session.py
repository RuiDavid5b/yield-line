"""
Integration tests for auth.session.
Skip if REDIS_URL isn't set.
"""

import pytest

from stock_news.auth import session as session_module

pytestmark = pytest.mark.requires_env("REDIS_URL")


def _fake_auth_result(expires_in=3600):
    return {
        "AccessToken": "at",
        "IdToken": "it",
        "RefreshToken": "rt",
        "ExpiresIn": expires_in,
    }


class TestCreateAndGetSession:
    def test_round_trips(self):
        session_id, csrf_token = session_module.create_session(
            "sub-1", "a@example.com", _fake_auth_result()
        )
        stored = session_module.get_session(session_id)

        assert stored["user_sub"] == "sub-1"
        assert stored["csrf_token"] == csrf_token
        session_module.delete_session(session_id)

    def test_unknown_session_id_returns_none(self):
        assert session_module.get_session("nonexistent") is None


class TestUpdateSessionTokens:
    def test_replaces_tokens_keeps_csrf_and_identity(self):
        session_id, csrf_token = session_module.create_session(
            "sub-1", "a@example.com", _fake_auth_result()
        )
        session_module.update_session_tokens(session_id, _fake_auth_result())
        updated = session_module.get_session(session_id)

        assert updated["csrf_token"] == csrf_token
        assert updated["user_sub"] == "sub-1"
        session_module.delete_session(session_id)


class TestValidateCsrf:
    def test_correct_token_passes(self):
        session_id, csrf_token = session_module.create_session(
            "sub-1", "a@example.com", _fake_auth_result()
        )
        assert session_module.validate_csrf(session_id, csrf_token) is True
        session_module.delete_session(session_id)

    def test_wrong_token_fails(self):
        session_id, _ = session_module.create_session(
            "sub-1", "a@example.com", _fake_auth_result()
        )
        assert session_module.validate_csrf(session_id, "wrong-token") is False
        session_module.delete_session(session_id)

    def test_unknown_session_fails(self):
        assert session_module.validate_csrf("nonexistent", "anything") is False
