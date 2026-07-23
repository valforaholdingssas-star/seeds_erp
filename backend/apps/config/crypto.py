from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings


def _derive_key(raw: str) -> bytes:
    """Accept base64, hex, or arbitrary string; always produce 32 bytes."""
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("SEEDS_SECRETS_KEY no está configurada")
    try:
        decoded = base64.b64decode(raw, validate=True)
        if len(decoded) in (16, 24, 32):
            return hashlib.sha256(decoded).digest()
    except Exception:
        pass
    try:
        decoded = bytes.fromhex(raw)
        if len(decoded) >= 16:
            return hashlib.sha256(decoded).digest()
    except Exception:
        pass
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_secret(plaintext: str) -> bytes:
    key = _derive_key(settings.SEEDS_SECRETS_KEY)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt_secret(blob: bytes) -> str:
    key = _derive_key(settings.SEEDS_SECRETS_KEY)
    aesgcm = AESGCM(key)
    nonce, ciphertext = blob[:12], blob[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "••••"
    return f"••••{value[-4:]}"
