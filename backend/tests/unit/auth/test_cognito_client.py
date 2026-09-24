"""
Unit tests for auth.cognito_client - boto3 client mocked.
"""

import pytest
from botocore.exceptions import ClientError

from stock_news.auth import cognito_client


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "SomeOperation")


class TestSignUp:
    def test_returns_user_sub_on_success(self, monkeypatch):
        class FakeClient:
            def sign_up(self, **kwargs):
                return {"UserSub": "abc-123"}

        monkeypatch.setattr(cognito_client, "_client", lambda: FakeClient())

        result = cognito_client.sign_up("a@example.com", "password123")
        assert result == "abc-123"

    def test_username_exists_raises_friendly_error(self, monkeypatch):
        class FakeClient:
            def sign_up(self, **kwargs):
                raise _client_error("UsernameExistsException")

        monkeypatch.setattr(cognito_client, "_client", lambda: FakeClient())

        with pytest.raises(cognito_client.CognitoError, match="already exists"):
            cognito_client.sign_up("a@example.com", "password123")


class TestInitiateAuth:
    def test_wrong_password_and_unknown_user_give_identical_message(self, monkeypatch):
        class FakeClient:
            def __init__(self, code):
                self.code = code

            def initiate_auth(self, **kwargs):
                raise _client_error(self.code)

        monkeypatch.setattr(
            cognito_client, "_client", lambda: FakeClient("NotAuthorizedException")
        )
        with pytest.raises(cognito_client.CognitoError) as exc1:
            cognito_client.initiate_auth("a@example.com", "wrong")

        monkeypatch.setattr(
            cognito_client, "_client", lambda: FakeClient("UserNotFoundException")
        )
        with pytest.raises(cognito_client.CognitoError) as exc2:
            cognito_client.initiate_auth("nobody@example.com", "whatever")

        assert str(exc1.value) == str(exc2.value)
