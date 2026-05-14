import base64

import pytest

from lib.boveda import cifrar, descifrar, rotar
from lib.errors import BovedaError


def test_round_trip():
    blob = cifrar("hola, n8n")
    assert descifrar(blob) == "hola, n8n"


def test_unicode():
    plain = "café — México ✅ 🔐"
    assert descifrar(cifrar(plain)) == plain


def test_blob_distinto_cada_vez():
    a = cifrar("misma cosa")
    b = cifrar("misma cosa")
    assert a != b  # nonce aleatorio


def test_blob_vacio_falla():
    with pytest.raises(BovedaError):
        descifrar("")


def test_blob_corrupto_falla():
    blob = cifrar("secreto")
    raw = bytearray(base64.urlsafe_b64decode(blob))
    raw[-1] ^= 0xFF  # flip último byte del tag
    tampered = base64.urlsafe_b64encode(bytes(raw)).decode("ascii")
    with pytest.raises(BovedaError):
        descifrar(tampered)


def test_blob_no_base64_falla():
    with pytest.raises(BovedaError):
        descifrar("no es base64 !!!@@@")


def test_no_cifrar_no_string():
    with pytest.raises(BovedaError):
        cifrar(123)  # type: ignore[arg-type]


def test_rotar_a_nueva_master_key():
    import secrets as _s
    blob = cifrar("dato a rotar")
    nueva = _s.token_hex(32)
    nuevo_blob = rotar(blob, nueva)
    # El blob nuevo no se puede descifrar con la master actual
    with pytest.raises(BovedaError):
        descifrar(nuevo_blob)
