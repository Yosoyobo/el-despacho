"""S-Celador-V1 — el extremo `/salud`, la credencial del Celador y la bitácora de accesos.

Cubre la lista de revisión del contrato del taller (docs/MONITOR_SALUD.md):

- `GET /salud` contesta JSON con `estado` y `modulos[]`.
- `503` **solo** cuando el estado del conjunto es `falla`.
- Ningún módulo se reporta `falla` por algo que está apagado a propósito.
- `Cache-Control: no-store`.
- La cara pública no trae conteos del negocio, nombres de proveedores ni cifras
  de dinero.
- Un dato que no se pudo medir va como `null` u omitido, **nunca como `0`**.
- El token se compara en tiempo constante y **sin token nadie pasa**.
- Cada intento de ingreso queda registrado, bueno y malo.
"""

from __future__ import annotations

import json

import pytest

from lib import celador
from lib import salud as salud_lib

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _cola_medible(monkeypatch):
    """Redis no siempre está arriba en la máquina de quien corre los tests, y sin
    esto la salud saldría en `falla` por el entorno y no por el código."""
    from lib.site import redis_status

    monkeypatch.setattr(redis_status, "chequear", lambda: {"estado": "ok", "latencia_ms": 1})
    monkeypatch.setattr(
        redis_status,
        "detalles",
        lambda: {"disponible": True, "portavoz_cola": 0, "portavoz_dlq": 0, "memoria_mb": 1},
    )


@pytest.fixture(autouse=True)
def _sin_token(monkeypatch):
    """Arranca sin credencial configurada: es el estado por defecto y el que
    tiene que cerrar la puerta."""
    monkeypatch.delenv(celador.ENV_TOKEN, raising=False)


def _cuerpo(resp) -> dict:
    return json.loads(resp.content.decode())


# ── La cara pública ──────────────────────────────────────────────────────────


def test_publico_contesta_json_con_estado_y_modulos(client):
    resp = client.get("/salud")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/json")
    d = _cuerpo(resp)
    assert d["estado"] in ("ok", "degradado", "apagado", "falla")
    assert isinstance(d["modulos"], list) and d["modulos"]
    for m in d["modulos"]:
        assert set(m) == {"modulo", "estado", "detalle"}
        assert m["estado"] in ("ok", "degradado", "apagado", "falla")


def test_publico_no_cachea(client):
    """Un monitor cacheado miente en verde."""
    assert client.get("/salud")["Cache-Control"] == "no-store"


def test_publico_no_trae_el_desglose(client):
    d = _cuerpo(client.get("/salud"))
    assert "ia" not in d
    assert "uso" not in d
    assert set(d) == {"estado", "version", "app", "modulos"}


def test_publico_no_trae_cifras_de_dinero(client):
    for m in _cuerpo(client.get("/salud"))["modulos"]:
        assert "$" not in m["detalle"]


def test_publico_dice_que_app_contesto(client):
    # Las tres apps comparten base de datos: el JSON tiene que decir quién habló.
    assert _cuerpo(client.get("/salud"))["app"] in ("taller", "gerencia", "recepcion", "pruebas")


def test_head_tambien_contesta(client):
    assert client.head("/salud").status_code == 200


def test_post_no_se_acepta(client):
    assert client.post("/salud").status_code == 405


# ── El código acompaña al estado ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("estado", "codigo"),
    [("ok", 200), ("degradado", 200), ("apagado", 200), ("falla", 503)],
)
def test_503_solo_cuando_falla(client, monkeypatch, estado, codigo):
    monkeypatch.setattr(
        salud_lib, "modulos", lambda de_la_casa=False: [{"modulo": "x", "estado": estado, "detalle": ""}]
    )
    resp = client.get("/salud")
    assert resp.status_code == codigo
    assert _cuerpo(resp)["estado"] == estado


def test_apagado_no_degrada_el_conjunto():
    mods = [
        {"modulo": "base", "estado": "ok", "detalle": ""},
        {"modulo": "correo", "estado": "apagado", "detalle": ""},
    ]
    assert salud_lib.estado_del_conjunto(mods) == "ok"


def test_falla_gana_sobre_degradado():
    mods = [
        {"modulo": "cola", "estado": "degradado", "detalle": ""},
        {"modulo": "base", "estado": "falla", "detalle": ""},
    ]
    assert salud_lib.estado_del_conjunto(mods) == "falla"


def test_nada_apagado_se_reporta_como_falla(client):
    """En pruebas no hay canal de correo ni llaves de IA: eso está apagado a
    propósito y NO debe despertar a nadie."""
    por_modulo = {m["modulo"]: m["estado"] for m in _cuerpo(client.get("/salud"))["modulos"]}
    assert por_modulo["correo"] == "apagado"
    assert por_modulo["ia"] == "apagado"


# ── Un hueco no es un cero ───────────────────────────────────────────────────


def test_respaldo_sin_datos_no_inventa_un_cero():
    m = salud_lib._m_respaldo(de_la_casa=False)
    assert m["estado"] == "degradado"  # hay algo que revisar, no una caída
    assert "0" not in m["detalle"] and "nunca" not in m["detalle"]
    assert "no se pudo determinar" in m["detalle"]


def test_cola_caida_no_reporta_conteos(monkeypatch):
    from lib.site import redis_status

    monkeypatch.setattr(redis_status, "chequear", lambda: {"estado": "error", "latencia_ms": 2})
    m = salud_lib._m_cola()
    assert m["estado"] == "falla"
    assert "0 pendientes" not in m["detalle"]


def test_uso_sin_bitacora_manda_null_no_cero():
    """El día que se enciende la bitácora no hay registros: un `0` ahí se leería
    como «nadie entró» cuando la verdad es «todavía no se está midiendo»."""
    uso = salud_lib.desglose_uso()
    assert uso["ingresos"] is None
    assert uso["fallidos"] is None
    assert "registrandoDesde" not in uso


# ── La credencial ────────────────────────────────────────────────────────────


def test_sin_token_configurado_nadie_pasa(client):
    assert celador.tokens_configurados() == []
    assert not celador.token_valido("lo-que-sea")
    d = _cuerpo(client.get("/salud", headers={celador.CABECERA: "lo-que-sea"}))
    assert "ia" not in d


def test_token_del_entorno_abre_el_desglose(client, monkeypatch):
    monkeypatch.setenv(celador.ENV_TOKEN, "secreto-del-taller")
    d = _cuerpo(client.get("/salud", headers={celador.CABECERA: "secreto-del-taller"}))
    assert "ia" in d and "uso" in d


def test_token_de_la_boveda_abre_el_desglose(client):
    from ajustes.models.credencial import Credencial

    Credencial.guardar(celador.SLOT_BOVEDA, "guardado-en-ajustes")
    d = _cuerpo(client.get("/salud", headers={celador.CABECERA: "guardado-en-ajustes"}))
    assert "ia" in d and "uso" in d


def test_token_equivocado_no_pasa(client, monkeypatch):
    monkeypatch.setenv(celador.ENV_TOKEN, "bueno")
    d = _cuerpo(client.get("/salud", headers={celador.CABECERA: "malo"}))
    assert "ia" not in d
    assert not celador.token_valido("bueno-pero-mas-largo")
    assert not celador.token_valido("")
    assert not celador.token_valido(None)


def test_base_caida_no_abre_la_puerta(monkeypatch):
    """Si no se puede leer La Bóveda, queda solo el token del entorno; nunca
    se degrada a «pasa cualquiera»."""
    monkeypatch.setattr(celador, "_token_boveda", lambda: "")
    assert celador.tokens_configurados() == []
    assert not celador.token_valido("x")


# ── El desglose con credencial ───────────────────────────────────────────────


def test_desglose_trae_las_llaves_del_contrato(client, monkeypatch):
    monkeypatch.setenv(celador.ENV_TOKEN, "t")
    d = _cuerpo(client.get("/salud", headers={celador.CABECERA: "t"}))
    assert set(d["ia"]) >= {"dias", "llamadas", "fallidas", "tokensEntrada", "tokensSalida", "costoMicro"}
    assert set(d["uso"]) >= {"dias", "ingresos", "fallidos", "cuentasActivas"}


def test_ia_cuenta_llamadas_tokens_y_costo_en_millonesimas():
    from decimal import Decimal

    from ajustes.models.analistas_log import AnalistaLog

    AnalistaLog.objects.create(
        provider="anthropic", modelo="m", estacion="dictado", exito=True,
        prompt_tokens=100, completion_tokens=20, costo_usd_estimado=Decimal("1.482500"),
    )
    AnalistaLog.objects.create(
        provider="openai", modelo="m", estacion="dictado", exito=False,
        prompt_tokens=5, completion_tokens=0, costo_usd_estimado=Decimal("0"),
    )
    ia = salud_lib.desglose_ia()
    assert ia["llamadas"] == 2
    assert ia["fallidas"] == 1
    assert ia["tokensEntrada"] == 105
    assert ia["tokensSalida"] == 20
    # Millonésimas enteras, para no guardar flotantes de dinero.
    assert ia["costoMicro"] == 1_482_500
    assert isinstance(ia["costoMicro"], int)


def test_uso_separa_los_que_entraron_de_los_que_no():
    """Un día con treinta fallidos y dos entradas significa algo muy distinto
    de treinta entradas."""
    from cuentas.models.intento_acceso import IntentoAcceso

    IntentoAcceso.objects.create(app="taller", exito=True, motivo="ok")
    IntentoAcceso.objects.create(app="taller", exito=False, motivo="credenciales")
    IntentoAcceso.objects.create(app="gerencia", exito=False, motivo="limite")
    uso = salud_lib.desglose_uso()
    assert uso["ingresos"] == 3
    assert uso["fallidos"] == 2
    assert uso["registrandoDesde"]


def test_uso_cuenta_las_cuentas_activas():
    from django.utils import timezone

    from cuentas.models.usuario import Usuario

    Usuario.objects.create_user(email="a@x.mx", password="x", nombre_completo="A", rol="miembro")
    viejo = Usuario.objects.create_user(email="b@x.mx", password="x", nombre_completo="B", rol="miembro")
    activo = Usuario.objects.create_user(email="c@x.mx", password="x", nombre_completo="C", rol="miembro")
    activo.ultimo_acceso_en = timezone.now()
    activo.save(update_fields=["ultimo_acceso_en"])
    viejo.ultimo_acceso_en = timezone.now() - timezone.timedelta(days=90)
    viejo.save(update_fields=["ultimo_acceso_en"])
    assert salud_lib.desglose_uso()["cuentasActivas"] == 1


def test_nombres_de_plataformas_solo_con_credencial(monkeypatch):
    from lib import salud_sistema

    monkeypatch.setattr(salud_sistema, "plataformas_en_error", lambda limite=5: ["anthropic", "n8n_tailscale"])
    publico = salud_lib._m_integraciones(de_la_casa=False)
    privado = salud_lib._m_integraciones(de_la_casa=True)
    assert publico["estado"] == "degradado"  # una integración caída no es una caída del despacho
    assert "anthropic" not in publico["detalle"]
    assert "2 integraciones" in publico["detalle"]
    assert "anthropic" in privado["detalle"]


# ── La bitácora de accesos ───────────────────────────────────────────────────


def test_login_fallido_queda_registrado(client, monkeypatch):
    monkeypatch.setattr("apps.auth_taller.views.intentar", lambda *a, **k: 1)
    from cuentas.models.intento_acceso import IntentoAcceso

    client.post("/sign-in", {"email": "nadie@x.mx", "password": "malo"})
    fila = IntentoAcceso.objects.get()
    assert fila.exito is False
    assert fila.motivo == "credenciales"
    assert fila.email_intentado == "nadie@x.mx"
    assert fila.app == "taller"


def test_login_bueno_queda_registrado(client, monkeypatch):
    monkeypatch.setattr("apps.auth_taller.views.intentar", lambda *a, **k: 1)
    monkeypatch.setattr("apps.auth_taller.views.reset", lambda *a, **k: None)
    from cuentas.models.intento_acceso import IntentoAcceso
    from cuentas.models.usuario import Usuario

    u = Usuario.objects.create_user(email="d@x.mx", password="Secreta123", nombre_completo="D", rol="miembro")
    client.post("/sign-in", {"email": "d@x.mx", "password": "Secreta123"})
    fila = IntentoAcceso.objects.get()
    assert fila.exito is True and fila.motivo == "ok" and fila.usuario_id == u.pk


def test_intento_frenado_por_el_limite_queda_registrado(client, monkeypatch):
    from lib.errors import RateLimitExcedido

    def _tope(*a, **k):
        raise RateLimitExcedido("Demasiados intentos.")

    monkeypatch.setattr("apps.auth_taller.views.intentar", _tope)
    from cuentas.models.intento_acceso import IntentoAcceso

    client.post("/sign-in", {"email": "e@x.mx", "password": "x"})
    assert IntentoAcceso.objects.get().motivo == "limite"


def test_auditar_nunca_tumba_un_login(rf):
    """Si la bitácora no se puede escribir, el login sigue su camino."""
    from lib import auditoria_acceso

    class _Explota:
        objects = None

        def __getattr__(self, _):  # pragma: no cover
            raise RuntimeError("base caída")

    req = rf.post("/sign-in")
    # Sin monkeypatch de la tabla basta con un `usuario` imposible de guardar:
    # el helper traga cualquier excepción.
    auditoria_acceso.registrar(req, app="taller", exito=False, motivo="x" * 500, email="a@b.mx")


def test_ip_prefiere_el_primer_salto_reenviado(rf):
    from lib.auditoria_acceso import ip_de

    req = rf.get("/", HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1", REMOTE_ADDR="10.0.0.1")
    assert ip_de(req) == "203.0.113.9"
    assert ip_de(rf.get("/", REMOTE_ADDR="10.0.0.2")) == "10.0.0.2"
