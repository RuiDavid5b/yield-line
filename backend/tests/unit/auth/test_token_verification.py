"""
Unit tests for auth.token_verification.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from stock_news.auth import token_verification


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    class FakeSettings:
        aws_region = "us-east-1"
        cognito_user_pool_id = "us-east-1_testpool"
        cognito_client_id = "test-client-id"

    monkeypatch.setattr(token_verification, "get_settings", lambda: FakeSettings())


def _make_token(private_key, **claim_overrides):
    now = int(time.time())
    claims = {
        "sub": "user-sub-123",
        "aud": "test-client-id",
        "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_testpool",
        "token_use": "id",
        "iat": now,
        "exp": now + 3600,
        **claim_overrides,
    }
    return jwt.encode(claims, private_key, algorithm="RS256")


def _patch_jwks(monkeypatch, public_key):
    class FakeSigningKey:
        key = public_key

    class FakeJWKSClient:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey()

    monkeypatch.setattr(
        token_verification, "_get_jwks_client", lambda: FakeJWKSClient()
    )


class TestVerifyIdToken:
    def test_valid_token_returns_claims(self, monkeypatch, rsa_keypair):
        private_key, public_key = rsa_keypair
        _patch_jwks(monkeypatch, public_key)
        token = _make_token(private_key)

        claims = token_verification.verify_id_token(token)

        assert claims["sub"] == "user-sub-123"

    def test_wrong_signing_key_rejected(self, monkeypatch, rsa_keypair):
        private_key, _ = rsa_keypair
        _, wrong_public_key = (
            rsa.generate_private_key(public_exponent=65537, key_size=2048),
            None,
        )
        wrong_public_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        ).public_key()
        _patch_jwks(
            monkeypatch, wrong_public_key
        )  # JWKS returns a DIFFERENT key than what signed the token
        token = _make_token(private_key)

        with pytest.raises(jwt.InvalidTokenError):
            token_verification.verify_id_token(token)

    def test_wrong_audience_rejected(self, monkeypatch, rsa_keypair):
        private_key, public_key = rsa_keypair
        _patch_jwks(monkeypatch, public_key)
        token = _make_token(private_key, aud="some-other-client-id")

        with pytest.raises(jwt.InvalidTokenError):
            token_verification.verify_id_token(token)

    def test_expired_token_rejected(self, monkeypatch, rsa_keypair):
        private_key, public_key = rsa_keypair
        _patch_jwks(monkeypatch, public_key)
        token = _make_token(private_key, exp=int(time.time()) - 10)

        with pytest.raises(jwt.InvalidTokenError):
            token_verification.verify_id_token(token)

    def test_access_token_masquerading_as_id_token_rejected(
        self, monkeypatch, rsa_keypair
    ):
        private_key, public_key = rsa_keypair
        _patch_jwks(monkeypatch, public_key)
        token = _make_token(private_key, token_use="access")

        with pytest.raises(jwt.InvalidTokenError):
            token_verification.verify_id_token(token)
