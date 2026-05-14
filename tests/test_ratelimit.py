"""Tests del rate-limit sliding window. Requiere Redis (CI lo levanta como service)."""

import time

import pytest

from lib.errors import RateLimitExcedido
from lib.ratelimit import intentar, reset


pytestmark = pytest.mark.redis


def test_dentro_del_limite_pasa():
    reset("test_login", "ip-1")
    for i in range(1, 6):
        assert intentar("test_login", "ip-1", limite=5, ventana_seg=60) == i
    reset("test_login", "ip-1")


def test_excede_levanta():
    reset("test_login", "ip-2")
    for _ in range(5):
        intentar("test_login", "ip-2", limite=5, ventana_seg=60)
    with pytest.raises(RateLimitExcedido):
        intentar("test_login", "ip-2", limite=5, ventana_seg=60)
    reset("test_login", "ip-2")


def test_reset_libera():
    reset("test_login", "ip-3")
    for _ in range(5):
        intentar("test_login", "ip-3", limite=5, ventana_seg=60)
    reset("test_login", "ip-3")
    # Después del reset, primer intento devuelve 1.
    assert intentar("test_login", "ip-3", limite=5, ventana_seg=60) == 1
    reset("test_login", "ip-3")


def test_aislamiento_por_identidad():
    reset("test_login", "ip-A")
    reset("test_login", "ip-B")
    for _ in range(5):
        intentar("test_login", "ip-A", limite=5, ventana_seg=60)
    # ip-B no debe verse afectada.
    assert intentar("test_login", "ip-B", limite=5, ventana_seg=60) == 1
    reset("test_login", "ip-A")
    reset("test_login", "ip-B")


def test_ventana_corta_expira():
    """Ventana de 1 segundo: tras dormir, el contador efectivo baja."""
    reset("test_login", "ip-corta")
    for _ in range(3):
        intentar("test_login", "ip-corta", limite=10, ventana_seg=1)
    time.sleep(1.2)
    # El sliding window debe limpiar entradas viejas.
    contador = intentar("test_login", "ip-corta", limite=10, ventana_seg=1)
    assert contador == 1
    reset("test_login", "ip-corta")
