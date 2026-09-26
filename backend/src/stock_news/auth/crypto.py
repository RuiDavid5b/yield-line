"""
KMS-backed encryption for user-provided LLM API keys.
"""

from __future__ import annotations

import base64

import boto3

from stock_news.config import get_settings


def _kms_client():
    return boto3.client("kms", region_name=get_settings().aws_region)


def encrypt_api_key(plaintext: str) -> str:
    """Returns base64-encoded ciphertext."""
    settings = get_settings()
    response = _kms_client().encrypt(
        KeyId=settings.byok_kms_key_alias, Plaintext=plaintext.encode("utf-8")
    )
    return base64.b64encode(response["CiphertextBlob"]).decode("ascii")


def decrypt_api_key(ciphertext_b64: str) -> str:
    """
    Decrypts a stored ciphertext back to plaintext.
    """
    ciphertext = base64.b64decode(ciphertext_b64)
    response = _kms_client().decrypt(CiphertextBlob=ciphertext)
    return response["Plaintext"].decode("utf-8")
