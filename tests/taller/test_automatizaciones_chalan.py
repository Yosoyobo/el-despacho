"""El Chalán opera las automatizaciones de n8n (S-NUC-Servicios, 2026-08-24).

Oscar: «integra el MCP para que el chalán pueda hacer y deshacer flujos» — y
desde el principio, con *muchos guardrails*.

Lo que estas pruebas cuidan, en orden de lo que dolería:

1. Que **prender no se pueda sin permiso**. Una automatización activa le manda
   correos a clientes: que un modelo la encienda sin que nadie la mire sería
   regalarle la voz del despacho.
2. Que **no se adivine cuál flujo es**. Con dos que coinciden, se pregunta; no
   se elige uno.
3. Que **sin llave, todo esto se apague solo** en vez de fallar cuando se use.
4. Que las tres acciones estén en **los tres lugares del contrato** — es lo que
   se olvida.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db

FLUJOS = [
    {"id": "1", "nombre": "CFDI por correo", "activo": False,
     "pasos": 3, "disparador": "IMAP", "actualizado": "2026-08-24"},
    {"id": "2", "nombre": "Aviso de cobranza", "activo": True,
     "pasos": 4, "disparador": "Cron", "actualizado": "2026-08-20"},
    {"id": "3", "nombre": "Aviso de entrega", "activo": False,
     "pasos": 2, "disparador": "Webhook", "actualizado": "2026-08-19"},
]


class _Accion:
    def __init__(self, payload):
        self.payload = payload


@pytest.fixture
def con_n8n(monkeypatch):
    from lib import n8n

    monkeypatch.setattr(n8n, "esta_configurado", lambda: True)
    monkeypatch.setattr(n8n, "listar_flujos", lambda: list(FLUJOS))
    hecho = {}
    monkeypatch.setattr(n8n, "activar", lambda i: hecho.update(activar=i) or True)
    monkeypatch.setattr(n8n, "desactivar", lambda i: hecho.update(desactivar=i) or True)
    monkeypatch.setattr(n8n, "borrar", lambda i: hecho.update(borrar=i) or True)
    return hecho


# ── El permiso, que es lo que sostiene todo ────────────────────────────────


def test_sin_permiso_no_se_prende_nada(con_n8n, usuario_factory):
    """Es el caso que importa: una automatización activa le escribe a clientes."""
    from apps.el_dictado.ejecutores.automatizacion import activar_automatizacion

    with pytest.raises(ValueError, match="permiso"):
        activar_automatizacion(_Accion({"flujo_id": "1"}), usuario_factory(rol="miembro"))
    assert "activar" not in con_n8n, "se prendió pese a no tener permiso"


def test_con_permiso_si_se_prende(con_n8n, usuario_factory):
    from apps.el_dictado.ejecutores.automatizacion import activar_automatizacion

    r = activar_automatizacion(_Accion({"flujo_id": "1"}), usuario_factory(rol="super_admin"))
    assert con_n8n["activar"] == "1"
    assert "prendida" in r["resumen"]


def test_apagar_y_quitar_tambien_piden_permiso(con_n8n, usuario_factory):
    from apps.el_dictado.ejecutores.automatizacion import (
        borrar_automatizacion,
        desactivar_automatizacion,
    )

    pobre = usuario_factory(rol="miembro")
    for fn in (desactivar_automatizacion, borrar_automatizacion):
        with pytest.raises(ValueError, match="permiso"):
            fn(_Accion({"flujo_id": "1"}), pobre)


# ── No adivinar ────────────────────────────────────────────────────────────


def test_se_puede_pedir_por_nombre(con_n8n, usuario_factory):
    """Quien habla dice «el de las facturas», no un identificador."""
    from apps.el_dictado.ejecutores.automatizacion import activar_automatizacion

    activar_automatizacion(_Accion({"flujo_id": "CFDI por correo"}),
                           usuario_factory(rol="super_admin"))
    assert con_n8n["activar"] == "1"


def test_un_nombre_ambiguo_no_se_adivina(con_n8n, usuario_factory):
    """Dos se llaman «Aviso de…». Elegir uno sería peor que preguntar."""
    from apps.el_dictado.ejecutores.automatizacion import activar_automatizacion

    with pytest.raises(ValueError, match="varias"):
        activar_automatizacion(_Accion({"flujo_id": "Aviso"}),
                               usuario_factory(rol="super_admin"))
    assert "activar" not in con_n8n


def test_un_flujo_que_no_existe_lo_dice(con_n8n, usuario_factory):
    from apps.el_dictado.ejecutores.automatizacion import activar_automatizacion

    with pytest.raises(ValueError, match="No hay ninguna"):
        activar_automatizacion(_Accion({"flujo_id": "el que no está"}),
                               usuario_factory(rol="super_admin"))


def test_sin_decir_cual_se_rechaza(con_n8n, usuario_factory):
    from apps.el_dictado.ejecutores.automatizacion import activar_automatizacion

    with pytest.raises(ValueError, match="cuál"):
        activar_automatizacion(_Accion({}), usuario_factory(rol="super_admin"))


# ── Borrar apaga primero ───────────────────────────────────────────────────


def test_borrar_apaga_antes(con_n8n, usuario_factory):
    """Si algo falla a media operación, queda apagada y no a medio camino
    ejecutándose."""
    from apps.el_dictado.ejecutores.automatizacion import borrar_automatizacion

    borrar_automatizacion(_Accion({"flujo_id": "2"}), usuario_factory(rol="super_admin"))
    assert con_n8n["desactivar"] == "2"
    assert con_n8n["borrar"] == "2"


# ── Sin llave, todo esto se apaga solo ─────────────────────────────────────


def test_sin_llave_se_avisa_en_vez_de_fallar(monkeypatch, usuario_factory):
    from lib import n8n

    monkeypatch.setattr(n8n, "esta_configurado", lambda: False)
    from apps.el_dictado.ejecutores.automatizacion import activar_automatizacion

    with pytest.raises(ValueError, match="llave de n8n"):
        activar_automatizacion(_Accion({"flujo_id": "1"}), usuario_factory(rol="super_admin"))


def test_sin_llave_la_lectura_lo_dice_clarito(monkeypatch, usuario_factory):
    from capacidades.lecturas import _h_listar_flujos
    from lib import n8n

    monkeypatch.setattr(n8n, "esta_configurado", lambda: False)
    r = _h_listar_flujos(usuario_factory(rol="super_admin"))
    assert r["disponible"] is False
    assert "Ajustes" in r["nota"]


def test_la_lectura_lista_lo_que_hay(monkeypatch, usuario_factory):
    from capacidades.lecturas import _h_listar_flujos
    from lib import n8n

    monkeypatch.setattr(n8n, "esta_configurado", lambda: True)
    monkeypatch.setattr(n8n, "listar_flujos", lambda: list(FLUJOS))
    r = _h_listar_flujos(usuario_factory(rol="super_admin"))
    assert r["total"] == 3
    assert r["flujos"][0]["nombre"] == "CFDI por correo"


# ── Los tres lugares del contrato ──────────────────────────────────────────


def test_las_tres_acciones_estan_en_los_tres_lugares():
    """Sumar un ejecutor obliga a tocar tres sitios, y lo que se olvida es
    siempre alguno de los otros dos: sin catálogo el Chalán no la conoce, y sin
    prompt la propone mal."""
    from pathlib import Path

    from apps.el_dictado.ejecutores import EJECUTORES

    from lib.dictado_catalogo import COMANDOS_DICTADO

    raiz = Path(__file__).resolve().parent.parent.parent
    prompt = (raiz / "el-taller/apps/el_dictado/prompt.py").read_text()
    tipos_catalogo = {c["tipo"] for c in COMANDOS_DICTADO}

    for tipo in ("activar_automatizacion", "desactivar_automatizacion",
                 "borrar_automatizacion"):
        assert tipo in EJECUTORES, f"{tipo}: falta el ejecutor"
        assert tipo in tipos_catalogo, f"{tipo}: falta en el catálogo"
        assert tipo in prompt, f"{tipo}: falta en el prompt"


def test_el_gating_es_el_de_ajustes():
    """No un permiso propio: tocar automatizaciones es tocar la configuración
    del despacho."""
    from lib.dictado_catalogo import COMANDOS_DICTADO

    for c in COMANDOS_DICTADO:
        if c["tipo"].endswith("_automatizacion"):
            assert c["gating"] == "automatizacion"


def test_crear_flujos_si_esta_expuesto_pero_nace_apagado():
    """**Esto cambió el 2026-08-24, a pedido de Oscar** («a ver qué puede hacer
    con los guardrails que pusimos»). Antes se exigía lo contrario, porque un
    modelo inventando el grafo de nodos de n8n produce flujos que se ven bien y
    no corren.

    Esa objeción sigue en pie; lo que la vuelve intentable son las trancas: la
    automatización nace APAGADA, se revisa contra los nodos que conocemos y hay
    recetas de las que partir. El detalle vive en
    `tests/taller/test_crear_automatizacion.py`; aquí sólo queda fijado que la
    acción existe y por qué es segura intentarla."""
    from apps.el_dictado.ejecutores import EJECUTORES

    assert "crear_automatizacion" in EJECUTORES
