import json

import pytest

from lib.errors import PortavozError
from lib.portavoz import firmar, verificar
from lib.portavoz_eventos import EventoPortavoz


def test_evento_serializa_a_json():
    e = EventoPortavoz(
        tipo="cliente.creado",
        actor_id=1,
        actor_email="oscar@bautista.mx",
        payload={"cliente_id": 42, "razon_social": "Café Azul SA"},
    )
    d = e.serializar()
    blob = json.dumps(d, ensure_ascii=False)
    parsed = json.loads(blob)
    assert parsed["tipo"] == "cliente.creado"
    assert parsed["payload"]["cliente_id"] == 42
    assert "emitido_en" in parsed
    assert parsed["schema_version"] == 1


def test_firma_hmac_es_estable():
    body = b'{"tipo":"x"}'
    a = firmar(body, "secreto")
    b = firmar(body, "secreto")
    assert a == b
    assert len(a) == 64  # hex SHA256


def test_firma_distinta_si_cambia_secret():
    body = b'{"tipo":"x"}'
    assert firmar(body, "uno") != firmar(body, "dos")


def test_verificar_acepta_firma_valida():
    body = b'{"tipo":"x"}'
    f = firmar(body, "secreto")
    assert verificar(body, "secreto", f) is True


def test_verificar_rechaza_firma_invalida():
    body = b'{"tipo":"x"}'
    assert verificar(body, "secreto", "deadbeef" * 8) is False
    assert verificar(body, "secreto", "") is False


def test_firmar_sin_secret_falla():
    with pytest.raises(PortavozError):
        firmar(b"x", "")
