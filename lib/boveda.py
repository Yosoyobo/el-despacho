"""La Bóveda — cifrado simétrico AES-256-GCM para credenciales en DB.

Regla inviolable #2: si `BOVEDA_MASTER_KEY` no existe o no son 64 hex chars,
la app falla AL IMPORTAR este módulo. No hay arranque silencioso sin Bóveda.
"""

from __future__ import annotations

import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .errors import BovedaError

_NONCE_BYTES = 12


def _cargar_master_key() -> bytes:
    raw = os.environ.get("BOVEDA_MASTER_KEY", "").strip()
    if not raw:
        raise BovedaError(
            "BOVEDA_MASTER_KEY no está definida. Genera 64 hex chars con "
            "`python -c \"import secrets;print(secrets.token_hex(32))\"` y "
            "agrégala al .env antes de arrancar."
        )
    if len(raw) != 64:
        raise BovedaError(
            f"BOVEDA_MASTER_KEY debe tener 64 hex chars (32 bytes); recibí {len(raw)}."
        )
    try:
        return bytes.fromhex(raw)
    except ValueError as exc:
        raise BovedaError("BOVEDA_MASTER_KEY no es hexadecimal válido.") from exc


_MASTER_KEY = _cargar_master_key()
_AEAD = AESGCM(_MASTER_KEY)


def cifrar(plaintext: str) -> str:
    """Cifra un string UTF-8. Devuelve `nonce || ciphertext` en base64 URL-safe."""
    if not isinstance(plaintext, str):
        raise BovedaError("Solo se cifran strings; convierte antes de llamar.")
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ct = _AEAD.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
    return base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def descifrar(blob: str) -> str:
    """Descifra lo que devolvió `cifrar()`. Lanza BovedaError si fue manipulado."""
    if not blob:
        raise BovedaError("Blob vacío")
    try:
        raw = base64.urlsafe_b64decode(blob.encode("ascii"))
    except Exception as exc:
        raise BovedaError("Blob no es base64 URL-safe válido") from exc
    if len(raw) < _NONCE_BYTES + 16:
        raise BovedaError("Blob demasiado corto para ser un payload AES-GCM")
    nonce, ct = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    try:
        return _AEAD.decrypt(nonce, ct, associated_data=None).decode("utf-8")
    except Exception as exc:
        raise BovedaError("Descifrado falló: payload manipulado o llave incorrecta") from exc


def rotar(blob: str, nueva_master_key_hex: str) -> str:
    """Re-cifra un blob bajo una nueva master key. Útil para rotación programada."""
    plaintext = descifrar(blob)
    nueva = bytes.fromhex(nueva_master_key_hex)
    aead = AESGCM(nueva)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ct = aead.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
    return base64.urlsafe_b64encode(nonce + ct).decode("ascii")
