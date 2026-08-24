"""S-Visual-Cotizacion-Kanban (LC 2026-08-23).

Dos zonas que no se tocan entre sí:

1. **El semáforo de estatus de la cotización** existía sólo en el recuadro del
   detalle del proyecto; la PÁGINA de la cotización mostraba una pastilla
   estática. Se extrajo a `cotizaciones/_semaforo.html` y ahora las DOS
   pantallas usan el mismo partial — eso es lo que garantiza que no divergan.
2. **El estilo del Kanban**: el distintivo de color se mudó de la ficha a la
   columna (contorno del color + pestaña rellena, fondo blanco), y la ficha
   quedó sin contorno.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

RAIZ = Path(__file__).resolve().parents[2]
TPL_SEMAFORO = RAIZ / "el-taller/templates/cotizaciones/_semaforo.html"
TPL_PANEL = RAIZ / "el-taller/templates/proyectos/_cotizaciones_panel.html"
TPL_COLUMNA = RAIZ / "el-taller/templates/proyectos/_kanban_columna.html"
CSS_TALLER = RAIZ / "el-taller/static/css/input.css"


def _sin_comentarios(texto: str) -> str:
    """El HTML sin los `{% comment %}`: los de este sprint CITAN las clases
    viejas para explicar cómo revertir, y si no se quitan el test las «ve»."""
    return re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "",
                  texto, flags=re.S)


@pytest.fixture
def cot_factory(usuario_factory, proyecto_factory):
    """Un proyecto con una línea y un helper para generar versiones."""
    from apps.cotizaciones import services
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(
        nombre="Producción", defaults={"orden": 10})
    srv = Servicio.objects.create(
        nombre="Taza", precio_base="100", costo="30", categoria=cat)
    proyecto = proyecto_factory(nombre="Semáforo de prueba", creado_por=admin)
    ProyectoProducto.objects.create(
        proyecto=proyecto, servicio=srv, cantidad=3, incluir_en_calculo=True)

    def _generar():
        return services.generar_desde_proyecto(proyecto, admin)

    return {"admin": admin, "proyecto": proyecto, "generar": _generar}


# ── 1. El semáforo, extraído y compartido ──────────────────────────────────

def test_el_recuadro_del_proyecto_ya_no_tiene_su_propia_copia():
    """Lo que evita que las dos pantallas divergan: el panel INCLUYE el partial
    en vez de traer su propio `cot-step`. Si alguien vuelve a copiarlo aquí, el
    día que se arregle uno el otro se queda atrás."""
    panel = TPL_PANEL.read_text(encoding="utf-8")
    assert 'include "cotizaciones/_semaforo.html"' in panel
    assert "cot-step" not in panel, "el panel volvió a tener su propia copia"


def test_la_pagina_de_la_cotizacion_pinta_el_semaforo_con_los_pasos_del_catalogo(
    client, cot_factory,
):
    """Y los pasos salen del CATÁLOGO de Gerencia, nunca de literales: un paso
    nuevo allá tiene que aparecer aquí solo."""
    from apps.cotizaciones.models import EstadoCotizacion, invalidar_cache_estados_cot
    EstadoCotizacion.objects.create(
        slug="revision_cliente", label="Revisión cliente", color="#f79009", orden=15)
    invalidar_cache_estados_cot()

    cot = cot_factory["generar"]()
    client.force_login(cot_factory["admin"])
    cuerpo = client.get(reverse("cotizaciones:detalle", args=[cot.pk])).content.decode()

    assert "cot-tracker" in cuerpo
    assert 'id="cot-semaforo"' in cuerpo
    assert "Revisión cliente" in cuerpo, "el semáforo no lee el catálogo"


def test_el_semaforo_va_arriba_del_titulo(client, cot_factory):
    """Oscar: «ponerlo arriba, encima del título». El `<h1>` lo pinta
    `_page_header.html`, así que basta comparar posiciones en el HTML."""
    cot = cot_factory["generar"]()
    client.force_login(cot_factory["admin"])
    cuerpo = client.get(reverse("cotizaciones:detalle", args=[cot.pk])).content.decode()
    assert cuerpo.index("cot-tracker") < cuerpo.index("<h1")


def test_el_paso_actual_se_marca_y_los_previos_quedan_hechos(client, cot_factory):
    from apps.cotizaciones import services
    cot = cot_factory["generar"]()
    services.marcar_estado_proyecto(cot, "aprobada", cot_factory["admin"])
    client.force_login(cot_factory["admin"])
    pasos = client.get(
        reverse("cotizaciones:detalle", args=[cot.pk])).context["semaforo"]["pasos"]
    fases = {p["slug"]: p["fase"] for p in pasos}
    assert fases["generada"] == "done"
    assert fases["aprobada"] == "current"
    assert fases["pagada"] == "future"


def test_el_semaforo_mueve_el_estatus_y_se_repinta(client, cot_factory):
    cot = cot_factory["generar"]()
    client.force_login(cot_factory["admin"])
    resp = client.post(reverse("cotizaciones:semaforo", args=[cot.pk]),
                       {"estado": "enviada"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    cot.refresh_from_db()
    assert cot.estado == "enviada"
    # Devuelve el semáforo, no la página entera.
    cuerpo = resp.content.decode()
    assert "cot-tracker" in cuerpo and "<html" not in cuerpo


def test_sin_permiso_de_editar_el_semaforo_sale_SIN_controles(client, cot_factory,
                                                              usuario_factory):
    """Un diseñador ve el estatus pero no lo mueve: los pasos son `<div>`, no
    `<button>`. Y el endpoint tampoco lo deja por la puerta de atrás."""
    cot = cot_factory["generar"]()
    disenador = usuario_factory(rol="disenador")
    from cuentas.models import PermisoUsuario
    PermisoUsuario.objects.update_or_create(
        usuario=disenador, modulo="cotizaciones", permiso="ver",
        defaults={"activo": True})
    client.force_login(disenador)
    ctx = client.get(reverse("cotizaciones:detalle", args=[cot.pk])).context["semaforo"]
    assert ctx["editable"] is False

    resp = client.post(reverse("cotizaciones:semaforo", args=[cot.pk]),
                       {"estado": "enviada"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 403
    cot.refresh_from_db()
    assert cot.estado == "generada"


def test_una_version_pasada_CONSERVA_sus_controles(client, cot_factory):
    """OJO — esto contradice a propósito la nota del handoff («sólo la última
    versión cambia de estatus»). Esa regla es de junio y la reemplazó D3 (LC
    2026-07): cada versión tiene su propio tracker editable, y hay una prueba
    que lo fija (`test_cambiar_estado_de_una_version_pasada`). Al extraer el
    semáforo se CONSERVÓ el comportamiento vigente, que es lo que pedía el
    handoff; si algún día se decide volver a la regla vieja, hay que cambiarlo
    en las DOS pantallas y tirar aquella prueba, no sólo en una."""
    v1 = cot_factory["generar"]()
    cot_factory["generar"]()  # v2, la más reciente
    client.force_login(cot_factory["admin"])
    ctx = client.get(reverse("cotizaciones:detalle", args=[v1.pk])).context["semaforo"]
    assert ctx["editable"] is True


def test_el_semaforo_no_acepta_GET(client, cot_factory):
    cot = cot_factory["generar"]()
    client.force_login(cot_factory["admin"])
    assert client.get(reverse("cotizaciones:semaforo", args=[cot.pk])).status_code == 405


# ── 2. El estilo del Kanban ────────────────────────────────────────────────

def test_la_columna_lleva_el_color_en_su_contorno_y_la_pestana_rellena():
    col = _sin_comentarios(TPL_COLUMNA.read_text(encoding="utf-8"))
    cabecera = col[:col.index("kanban-dropzone")]
    assert "--ec: {{ col.slug|color_estado }}" in cabecera
    assert "border-color: color-mix" in cabecera
    assert "kanban-tab" in cabecera
    # Contorno DELGADO: se fue la franja de 4px de arriba.
    assert "border-t-4" not in cabecera
    # Fondo blanco (antes gris, igual que la página).
    assert "bg-white" in cabecera and "bg-gray-50" not in cabecera


def test_la_ficha_ya_no_lleva_contorno():
    col = _sin_comentarios(TPL_COLUMNA.read_text(encoding="utf-8"))
    tarjeta = col[col.index("data-arr-item"):col.index("kanban-card") + 200]
    assert "border-2" not in tarjeta
    assert "color_estado" not in tarjeta
    # Lo que la separa del fondo blanco de la columna es la sombra.
    assert "shadow-theme-sm" in tarjeta


def test_la_pestana_es_legible_sobre_cualquier_color_del_catalogo():
    """El relleno se oscurece un punto a propósito y no es capricho: con el color
    PURO, el blanco sobre el ámbar de la casa queda en 2.35:1 y no se lee.

    Esto MIDE el contraste real leyendo el porcentaje del CSS, en vez de
    comprobar que la cadena está ahí: si alguien sube el 68% «para que se vea
    más el color», el peor caso baja de 4.5 y la prueba lo dice.
    """
    from apps.los_proyectos.models.estado import ESTADOS_BASE

    css = CSS_TALLER.read_text(encoding="utf-8")
    bloque = css[css.index(".kanban-tab {"):]
    bloque = bloque[:bloque.index("}")]
    assert "color: #ffffff" in bloque, "la pestaña dejó de llevar texto blanco"
    m = re.search(r"color-mix\(in srgb, var\(--ec[^)]*\) (\d+)%, #000000\)", bloque)
    assert m, "no se pudo leer la mezcla de la pestaña"
    mezcla = int(m.group(1)) / 100

    def contraste_con_blanco(hexa: str) -> float:
        def canal(v: float) -> float:
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        rgb = [int(hexa[i:i + 2], 16) * mezcla for i in (1, 3, 5)]
        lum = 0.2126 * canal(rgb[0]) + 0.7152 * canal(rgb[1]) + 0.0722 * canal(rgb[2])
        return 1.05 / (lum + 0.05)

    peor = min(contraste_con_blanco(e[2]) for e in ESTADOS_BASE)
    assert peor >= 4.5, (
        f"el texto blanco de la pestaña queda en {peor:.2f}:1 con la mezcla al "
        f"{m.group(1)}% — WCAG AA pide 4.5 para texto normal"
    )


def test_la_columna_inactiva_no_compite_con_el_tablero_real():
    """Los resultados «fuera del tablero» son de búsqueda: su pestaña va tenue
    y su contorno suave, para que el tablero real siga siendo el protagonista."""
    css = CSS_TALLER.read_text(encoding="utf-8")
    assert ".kanban-columna-fuera .kanban-tab" in css
    col = TPL_COLUMNA.read_text(encoding="utf-8")
    # El contorno se suaviza en la plantilla porque va inline: un `style` gana a
    # cualquier clase, así que el CSS no podría hacerlo.
    assert "{% if solo_lectura %}32{% else %}70{% endif %}" in col


def test_las_tres_pantallas_que_usan_la_columna_siguen_pintando(
    client, usuario_factory, proyecto_factory,
):
    """Kanban de Proyectos · tablero del Dashboard · resultados fuera."""
    admin = usuario_factory(rol="super_admin")
    proyecto_factory(nombre="Gorras Nike", creado_por=admin, estado="entregado")
    client.force_login(admin)

    for url in (reverse("proyectos-kanban"), reverse("taller-home")):
        resp = client.get(url)
        assert resp.status_code == 200
        assert "kanban-columna" in resp.content.decode(), url

    fuera = client.get(reverse("taller-buscar-proyectos"), {"q": "gorras"})
    assert fuera.status_code == 200
    cuerpo = fuera.content.decode()
    assert "kanban-columna-fuera" in cuerpo and "Gorras Nike" in cuerpo
