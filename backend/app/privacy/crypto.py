"""Encryption at rest for medical text, uploaded files and cached audio (Fernet: AES-128-CBC + HMAC-SHA256).

Key: DATA_ENCRYPTION_KEY (a Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
If it is not set, a key is derived from JWT_SECRET_KEY so development still works; production should set its own key
and keep it outside the database and the code repository.

Values written before encryption was turned on are read back unchanged (no "mmenc1:" prefix), so nothing breaks.
"""
from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import LargeBinary, Text, TypeDecorator

from app.core.config import settings

log = logging.getLogger("medimemory.privacy")
PREFIX = "mmenc1:"
BIN_PREFIX = b"MMENC1"
_fernet: Fernet | None = None


def key_source() -> str:
    import os
    return "DATA_ENCRYPTION_KEY" if os.getenv("DATA_ENCRYPTION_KEY", "").strip() else "derived from the JWT secret (set DATA_ENCRYPTION_KEY in production)"


def _f() -> Fernet:
    global _fernet
    if _fernet is None:
        import os
        raw = os.getenv("DATA_ENCRYPTION_KEY", "").strip()
        if raw:
            try:
                Fernet(raw.encode())
                key = raw.encode()
            except ValueError:  # any long random string (e.g. Render's "Generate" value) is turned into a key
                key = base64.urlsafe_b64encode(hashlib.sha256(b"medimemory-data-key|" + raw.encode()).digest())
        else:
            log.warning("DATA_ENCRYPTION_KEY is not set; deriving the data key from JWT_SECRET_KEY.")
            key = base64.urlsafe_b64encode(hashlib.sha256(b"medimemory-data-key|" + settings.jwt_secret.encode()).digest())
        _fernet = Fernet(key)
    return _fernet


def reset_key_cache() -> None:
    global _fernet
    _fernet = None


def encrypt_text(value: str | None) -> str | None:
    if value is None or value.startswith(PREFIX):
        return value
    return PREFIX + _f().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str | None) -> str | None:
    if value is None or not value.startswith(PREFIX):
        return value
    try:
        return _f().decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken:
        log.error("Could not decrypt a stored value (wrong DATA_ENCRYPTION_KEY?)")
        return "[encrypted: key mismatch]"


def encrypt_bytes(data: bytes) -> bytes:
    if data.startswith(BIN_PREFIX):
        return data
    return BIN_PREFIX + _f().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    if not data.startswith(BIN_PREFIX):
        return data
    return _f().decrypt(data[len(BIN_PREFIX):])


class EncryptedText(TypeDecorator):
    """A TEXT column stored encrypted. Not searchable in SQL; filter in Python after loading."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_text(value)

    def process_result_value(self, value, dialect):
        return decrypt_text(value)


class EncryptedBytes(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt_bytes(value)

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt_bytes(value)
