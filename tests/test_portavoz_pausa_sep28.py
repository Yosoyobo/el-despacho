"""El Portavoz en pausa cuando no hay destino (decisión Oscar, 2026-09-28).

La cola llegó a 2,192 eventos hacia un n8n sin ningún flujo: sin destino, el
Portavoz ya no encola, pero CUENTA lo que no salió y desde cuándo. Estos tests
usan un Redis de mentira para no depender del real.
"""

from __future__ import annotations

import pytest

from lib import portavoz
from lib.portavoz_eventos import EventoPortavoz

# El conftest cambia `emitir` por una función vacía cuando no hay Redis real; aquí
# se prueba justo `emitir`, así que se guarda la verdadera al importar.
_EMITIR_REAL = portavoz.emitir


class _RedisFalso:
    def __init__(self):
        self.listas: dict[str, list[str]] = {}
        self.valores: dict[str, str] = {}

    def rpush(self, llave, valor):
        self.listas.setdefault(llave, []).append(valor)

    def incr(self, llave):
        self.valores[llave] = str(int(self.valores.get(llave, "0")) + 1)
        return int(self.valores[llave])

    def set(self, llave, valor, nx=False):
        if nx and llave in self.valores:
            return False
        self.valores[llave] = valor
        return True

    def get(self, llave):
        return self.valores.get(llave)

    def delete(self, *llaves):
        for ll in llaves:
            self.valores.pop(ll, None)
            self.listas.pop(ll, None)


@pytest.fixture
def redis_falso(monkeypatch):
    r = _RedisFalso()
    monkeypatch.setattr(portavoz, "_client", lambda: r)
    monkeypatch.setattr(portavoz, "emitir", _EMITIR_REAL)
    portavoz.olvidar_destino()
    yield r
    portavoz.olvidar_destino()


def _evento():
    return EventoPortavoz(tipo="cliente.creado", actor_id=None, actor_email=None, payload={"id": 1})


@pytest.mark.django_db
def test_sin_destino_no_encola_y_cuenta(redis_falso):
    portavoz.emitir(_evento())
    portavoz.emitir(_evento())
    assert portavoz.COLA not in redis_falso.listas
    assert redis_falso.get(portavoz.SIN_DESTINO) == "2"
    assert redis_falso.get(portavoz.SIN_DESTINO_DESDE)
    estado = portavoz.en_pausa()
    assert estado["pausado"] is True
    assert estado["no_enviados"] == 2


@pytest.mark.django_db
def test_con_destino_encola_como_siempre(redis_falso):
    from ajustes.models.credencial import Credencial

    Credencial.guardar("n8n_webhook_url", "http://n8n:5678/webhook/despacho")
    portavoz.emitir(_evento())
    assert len(redis_falso.listas[portavoz.COLA]) == 1
    assert portavoz.en_pausa() == {"pausado": False}


@pytest.mark.django_db
def test_configurar_destino_reinicia_la_pausa(redis_falso):
    from ajustes.models.credencial import Credencial

    portavoz.emitir(_evento())
    assert redis_falso.get(portavoz.SIN_DESTINO) == "1"
    Credencial.guardar("n8n_webhook_url", "http://n8n:5678/webhook/despacho")
    # La caché de «¿hay destino?» se invalidó al guardar: el siguiente evento sí sale.
    portavoz.emitir(_evento())
    assert len(redis_falso.listas[portavoz.COLA]) == 1
    assert redis_falso.get(portavoz.SIN_DESTINO) is None


def test_sin_base_ante_la_duda_encola(redis_falso, monkeypatch):
    """Si no se puede saber si hay destino, se encola: nunca se tira de más."""
    import ajustes.models.credencial as mod

    def _explota(*a, **k):
        raise RuntimeError("base caída")

    monkeypatch.setattr(mod.Credencial, "obtener", classmethod(lambda cls, clave: _explota()))
    portavoz.emitir(_evento())
    assert len(redis_falso.listas[portavoz.COLA]) == 1


@pytest.mark.django_db
def test_salud_informa_la_pausa_sin_alarmar(redis_falso, monkeypatch):
    from lib import salud
    from lib.site import redis_status

    monkeypatch.setattr(redis_status, "chequear", lambda: {"estado": "ok"})
    monkeypatch.setattr(
        redis_status, "detalles", lambda: {"disponible": True, "portavoz_cola": 0, "portavoz_dlq": 0}
    )
    portavoz.emitir(_evento())
    m = salud._m_cola()
    assert m["estado"] == "ok"
    assert "en pausa sin destino (1 sin enviar)" in m["detalle"]
