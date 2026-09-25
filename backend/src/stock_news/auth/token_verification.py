"""
Verifies Cognito ID tokens against the user pool's JWKS (public signing
keys).
"""

from __future__ import annotations

import jwt
from jwt import PyJWKClient

from stock_news.config import get_settings

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        settings = get_settings()
        jwks_url = (
            f"https://cognito-idp.{settings.aws_region}.amazonaws.com/"
            f"{settings.cognito_user_pool_id}/.well-known/jwks.json"
        )
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


def verify_id_token(token: str) -> dict:
    """
    Verify a Cognito ID token's signature, issuer, audience, and
    expiry. Raises jwt.InvalidTokenError (or a subclass) on any failure -
    callers should treat that as "not authenticated," not attempt to
    read claims from a token that failed verification.
    """
    settings = get_settings()
    signing_key = _get_jwks_client().get_signing_key_from_jwt(token)

    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.cognito_client_id,
        issuer=f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_user_pool_id}",
        options={"require": ["exp", "iat", "sub"]},
    )

    if claims.get("token_use") != "id":
        raise jwt.InvalidTokenError("Token is not an ID token")

    return claims
