"""Gerencia → Ajustes → Documentos (S-NUC-Servicios, 2026-08-24).

Los márgenes y el pie de los PDF vivían como constantes y sólo se movían con
un despliegue. Oscar: «debemos poder editar todo lo posible de los PDFs en el
GUI de la gerencia».

Lo que cuidan estas pruebas:

1. Que **el selector de motor sirva de salida de emergencia**. Es la razón de
   que exista: si un formato se rompe frente a un cliente, hay que poder
   volver a Google con un clic y no esperando un despliegue.
2. Que **no se confíe en el `select`** — se puede manipular desde el navegador.
3. Que **el alto útil siga a los márgenes**. Del alto útil sale el hueco que se
   deja antes de las notas; si no se movieran juntos, volvería el error que
   costó varias rondas en agosto.
4. Que **sin configuración salga lo de siempre**.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def superadmin(usuario_factory):
    """La fixture del repo es `usuario_factory`; esto sólo le pone nombre."""
    return usuario_factory(rol="super_admin")


@pytest.fixture
def cfg():
    from ajustes.models import ConfiguracionDocumento

    return ConfiguracionDocumento.obtener()


# ── El modelo ──────────────────────────────────────────────────────────────


def test_la_fila_se_crea_al_leerla_y_es_una_sola(cfg):
    """Se crea al leer y no con una migración de datos: insertar en la misma
    tabla cuyo índice acaba de crearse es lo que tumbó el arranque (§14 Bug I)."""
    from ajustes.models import ConfiguracionDocumento

    otra = ConfiguracionDocumento.obtener()
    assert otra.pk == cfg.pk == 1
    assert ConfiguracionDocumento.objects.count() == 1


def test_los_defaults_son_los_de_siempre(cfg):
    """Quien no toque nada debe seguir viendo el documento de hoy."""
    assert cfg.motor == "auto"
    assert cfg.tamano_papel == "carta"
    assert cfg.margen_superior_pt == 36
    assert cfg.margen_inferior_pt == 43
    assert cfg.numerar_paginas is True


def test_el_alto_util_sigue_a_los_margenes(cfg):
    """Carta son 792 puntos; lo que cabe es eso menos los márgenes."""
    assert cfg.alto_util_pt == 792 - 36 - 43

    cfg.margen_superior_pt = 72
    assert cfg.alto_util_pt == 792 - 72 - 43, "el alto útil no siguió al margen"


def test_cambiar_de_hoja_cambia_el_alto_util(cfg):
    cfg.tamano_papel = "oficio"
    assert cfg.alto_util_pt == int(13.0 * 72) - 36 - 43


def test_como_pagina_trae_lo_que_espera_el_generador(cfg):
    p = cfg.como_pagina()
    for clave in ("margen_superior_pt", "margen_inferior_pt", "pie_texto",
                  "numerar_paginas", "ancho_in", "alto_in"):
        assert clave in p, f"falta {clave}"


# ── La pantalla ────────────────────────────────────────────────────────────


def test_la_pantalla_abre(client, superadmin):
    client.force_login(superadmin)
    r = client.get(reverse("ajustes-documentos"))
    assert r.status_code == 200
    assert b"Documentos" in r.content


def test_guardar_cambia_el_formato(client, superadmin, cfg):
    client.force_login(superadmin)
    r = client.post(reverse("ajustes-documentos"), {
        "motor": "google",
        "tamano_papel": "a4",
        "margen_superior_pt": "72",
        "margen_inferior_pt": "50",
        "margen_izquierdo_pt": "60",
        "margen_derecho_pt": "60",
        "pie_texto": "Learning Center",
        "numerar_paginas": "on",
        "interlineado": "1.2",
    })
    assert r.status_code == 302
    cfg.refresh_from_db()
    assert cfg.motor == "google"
    assert cfg.tamano_papel == "a4"
    assert cfg.margen_superior_pt == 72
    assert cfg.pie_texto == "Learning Center"


def test_un_motor_inventado_no_se_guarda(client, superadmin, cfg):
    """El `select` se puede manipular desde el navegador."""
    client.force_login(superadmin)
    client.post(reverse("ajustes-documentos"), {
        "motor": "weasyprint",
        "tamano_papel": "carta",
        "margen_superior_pt": "36", "margen_inferior_pt": "43",
        "margen_izquierdo_pt": "72", "margen_derecho_pt": "72",
        "interlineado": "1.02",
    })
    cfg.refresh_from_db()
    assert cfg.motor == "auto", "se guardó un motor que no existe"


def test_un_margen_absurdo_se_recorta(client, superadmin, cfg):
    """Tres pulgadas de margen ya dejan la hoja sin contenido."""
    client.force_login(superadmin)
    client.post(reverse("ajustes-documentos"), {
        "motor": "auto", "tamano_papel": "carta",
        "margen_superior_pt": "9999", "margen_inferior_pt": "43",
        "margen_izquierdo_pt": "72", "margen_derecho_pt": "72",
        "interlineado": "1.02",
    })
    cfg.refresh_from_db()
    assert cfg.margen_superior_pt == 216


def test_desmarcar_la_numeracion_la_apaga(client, superadmin, cfg):
    """Un checkbox desmarcado no viaja en el POST: su ausencia ES el apagado."""
    client.force_login(superadmin)
    client.post(reverse("ajustes-documentos"), {
        "motor": "auto", "tamano_papel": "carta",
        "margen_superior_pt": "36", "margen_inferior_pt": "43",
        "margen_izquierdo_pt": "72", "margen_derecho_pt": "72",
        "interlineado": "1.02",
    })
    cfg.refresh_from_db()
    assert cfg.numerar_paginas is False


def test_la_pantalla_esta_gateada(client, usuario_factory):
    """Va con el permiso de Ajustes, como las demás pantallas de configuración."""
    client.force_login(usuario_factory(rol="miembro"))
    r = client.get(reverse("ajustes-documentos"))
    assert r.status_code in (302, 403), "entró quien no tiene permiso de Ajustes"


# ── La salida de emergencia ────────────────────────────────────────────────


def test_forzar_google_evita_el_motor_propio(client, superadmin, monkeypatch):
    """La razón de ser del selector: volver al formato anterior sin desplegar."""
    from lib import documentos, gotenberg

    client.force_login(superadmin)
    client.post(reverse("ajustes-documentos"), {
        "motor": "google", "tamano_papel": "carta",
        "margen_superior_pt": "36", "margen_inferior_pt": "43",
        "margen_izquierdo_pt": "72", "margen_derecho_pt": "72",
        "interlineado": "1.02",
    })
    documentos.olvidar_configuracion()

    tocado = {"gotenberg": False}

    def _no_deberia(*a, **k):
        tocado["gotenberg"] = True
        return True

    monkeypatch.setattr(gotenberg, "disponible", _no_deberia)

    class _DriveFalso:
        def esta_configurado(self):
            return True

        def obtener_o_crear_subcarpeta(self, nombre):
            return "c"

        def html_a_pdf(self, html, nombre, carpeta_id=None, pagina=None):
            return {"id": "abc", "pdf_bytes": b"%PDF"}

    import lib.google_drive as gd
    monkeypatch.setattr(gd, "drive", _DriveFalso(), raising=False)

    res = documentos.generar_pdf(html="<p>x</p>", nombre="doc")
    assert res.motor == "google"
    assert not tocado["gotenberg"], "se consultó el motor propio pese a estar forzado a Google"
    documentos.olvidar_configuracion()
