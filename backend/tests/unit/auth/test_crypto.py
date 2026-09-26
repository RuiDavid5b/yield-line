"""
Unit tests for auth.crypto.
"""

import base64

from stock_news.auth import crypto


class TestEncryptDecryptApiKey:
    def test_round_trips_through_mocked_kms(self, monkeypatch):
        stored_ciphertext = {}

        class FakeKmsClient:
            def encrypt(self, KeyId, Plaintext):
                stored_ciphertext["blob"] = b"encrypted:" + Plaintext
                return {"CiphertextBlob": stored_ciphertext["blob"]}

            def decrypt(self, CiphertextBlob):
                assert CiphertextBlob == stored_ciphertext["blob"]
                plaintext = CiphertextBlob.removeprefix(b"encrypted:")
                return {"Plaintext": plaintext}

        monkeypatch.setattr(crypto, "_kms_client", lambda: FakeKmsClient())

        ciphertext_b64 = crypto.encrypt_api_key("sk-real-secret-key")
        assert "sk-real-secret-key" not in ciphertext_b64

        decrypted = crypto.decrypt_api_key(ciphertext_b64)
        assert decrypted == "sk-real-secret-key"

    def test_ciphertext_is_valid_base64(self, monkeypatch):
        class FakeKmsClient:
            def encrypt(self, KeyId, Plaintext):
                return {"CiphertextBlob": b"\x00\x01\xff\xfe binary garbage"}

        monkeypatch.setattr(crypto, "_kms_client", lambda: FakeKmsClient())

        ciphertext_b64 = crypto.encrypt_api_key("any-key")
        base64.b64decode(ciphertext_b64)
