"""Tests del Portavoz worker: contador de intentos + descarte a DLQ."""

import json

import pytest

from lib import portavoz_worker as pw

pytestmark = pytest.mark.redis


@pytest.fixture
def r_limpio():
    import redis

    cli = redis.Redis.from_url("redis://localhost:6379/15", decode_responses=True)
    cli.delete(pw.COLA, pw.DLQ)
    yield cli
    cli.delete(pw.COLA, pw.DLQ)


def _evento_crudo(tipo="cliente.creado", intentos=0):
    return json.dumps({"tipo": tipo, "actor_id": 1, "payload": {}, "_intentos": intentos})


def test_reencolar_incrementa_intentos(r_limpio):
    raw = _evento_crudo()
    pw._reencolar_con_intento(r_limpio, raw)
    items = r_limpio.lrange(pw.COLA, 0, -1)
    assert len(items) == 1
    assert json.loads(items[0])["_intentos"] == 1
    assert r_limpio.llen(pw.DLQ) == 0


def test_reencolar_descarta_a_dlq_al_agotar(r_limpio):
    # Empieza con intentos = MAX_INTENTOS - 1 → próximo intento = MAX_INTENTOS → DLQ
    raw = _evento_crudo(intentos=pw.MAX_INTENTOS - 1)
    pw._reencolar_con_intento(r_limpio, raw)
    assert r_limpio.llen(pw.COLA) == 0
    assert r_limpio.llen(pw.DLQ) == 1
    desc = json.loads(r_limpio.lindex(pw.DLQ, 0))
    assert desc["_intentos"] == pw.MAX_INTENTOS


def test_json_corrupto_va_directo_a_dlq(r_limpio):
    pw._reencolar_con_intento(r_limpio, "esto no es JSON {")
    assert r_limpio.llen(pw.DLQ) == 1
    assert r_limpio.llen(pw.COLA) == 0


def test_multiples_reencolados(r_limpio):
    raw = _evento_crudo()
    # 4 re-encolados consecutivos: el 5to (intento=5) va a DLQ.
    for _ in range(pw.MAX_INTENTOS - 1):
        items = r_limpio.lrange(pw.COLA, 0, -1)
        if items:
            r_limpio.delete(pw.COLA)
            raw = items[0]
        pw._reencolar_con_intento(r_limpio, raw)
    assert r_limpio.llen(pw.COLA) == 1
    assert r_limpio.llen(pw.DLQ) == 0
    raw = r_limpio.lpop(pw.COLA)
    # Quinto intento → DLQ.
    pw._reencolar_con_intento(r_limpio, raw)
    assert r_limpio.llen(pw.DLQ) == 1
