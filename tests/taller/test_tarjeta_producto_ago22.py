"""S-Tarjeta-Producto (LC 2026-08-23) — las notas 12, 13 y 8 del buzón.

- **Nota 12**: quitar el PRODUCTO usa un bote de basura, no una ✕. El handoff lo
  daba por hecho («ya está en origin/main»); NO estaba — los cuatro botones del
  archivo seguían con la ✕. Los otros tres (proceso de venta, impresión, proceso
  de producción) la conservan a propósito: quitan un RENGLÓN, no el producto.
- **Nota 13** («la tarjeta nueva tarda en aparecer»): la causa NO era el peso del
  HTML —la hipótesis del handoff, que medida ahorra un 2 %— sino un N+1 de
  ~51 consultas por tarjeta. Ver el test de abajo, que es el que lo fija.
- **Nota 8** (dos tarjetas del mismo color): diagnosticada contra los datos de La
  Sede. Los cinco choques que existen son del texto («Caso A», la regla
  funcionando), así que no hubo cambio de código; queda un test que documenta la
  precedencia para que nadie la mueva por accidente.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.db import connection
from django.template.loader import render_to_string
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

RAIZ = Path(__file__).resolve().parents[2]
TPL_CARD = RAIZ / "el-taller/templates/proyectos/_producto_card.html"

BASE_FORMSET = {
    "productos-TOTAL_FORMS": "0", "productos-INITIAL_FORMS": "0",
    "productos-MIN_NUM_FORMS": "0", "productos-MAX_NUM_FORMS": "50",
}


def _sin_comentarios(texto: str) -> str:
    return re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "",
                  texto, flags=re.S)


@pytest.fixture
def catalogo():
    """Un catálogo con proveedor PRINCIPAL — es el FK que causaba el N+1."""
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(
        nombre="Producción", defaults={"orden": 10})
    prov = Proveedor.objects.create(razon_social="Crea Blanks", activo=True)

    def _servicios(n: int):
        salida = []
        for i in range(n):
            s = Servicio.objects.create(
                nombre=f"Producto {i}", precio_base="100", costo="40",
                categoria=cat, proveedor_principal=prov)
            s.proveedores.add(prov)
            salida.append(s)
        return salida

    return {"cat": cat, "prov": prov, "servicios": _servicios}


# ── Nota 12: el bote de basura ─────────────────────────────────────────────

def test_quitar_el_producto_usa_un_bote_de_basura():
    card = TPL_CARD.read_text(encoding="utf-8")
    i = card.index('class="producto-eliminar')
    boton = card[i:card.index("</button>", i)]
    # El bote canónico (Feather trash-2): la tapa, el cuerpo y las dos rayas.
    assert 'points="3 6 5 6 21 6"' in boton, "el botón no trae el bote"
    assert 'x1="10" y1="11"' in boton
    # Y ya NO la ✕.
    assert "M18 6L6 18M6 6l12 12" not in boton


def test_los_otros_botones_conservan_su_equis():
    """Quitar un renglón de proceso o de venta NO es quitar el producto: el
    icono es justo lo que los distingue, así que si alguien los homologa «por
    consistencia» se pierde la señal."""
    card = _sin_comentarios(TPL_CARD.read_text(encoding="utf-8"))
    for clase in ("venta-del", "proceso-del", "imp-reset"):
        i = card.index(f'class="{clase}')
        boton = card[i:card.index("</button>", i)]
        assert "M18 6L6 18M6 6l12 12" in boton, f"{clase} perdió su ✕"
        assert 'points="3 6 5 6 21 6"' not in boton, f"{clase} no debe llevar bote"


# ── Nota 13: el N+1 que hacía lenta la tarjeta nueva ───────────────────────

def _pintar(proyecto) -> None:
    """Arma y pinta el formset de productos — lo mismo que devuelve el
    autoguardado por OOB al crear una línea, y lo mismo que pinta el detalle."""
    from apps.el_catalogo.models import CategoriaServicio
    from apps.los_proyectos import views as V
    from apps.los_proyectos.forms import ProyectoProductoFormSetDetalle

    fs = ProyectoProductoFormSetDetalle(instance=proyecto)
    V._anotar_procesos(fs)
    render_to_string("proyectos/_formset_productos.html", {
        "formset": fs, "con_autosave": True,
        "categorias_disponibles": CategoriaServicio.objects.filter(activa=True),
        "proveedores_activos": V._proveedores_activos(),
    })


def _consultas_al_pintar(proyecto) -> int:
    """OJO — el formset se arma DENTRO de la medición, a propósito.

    Un `render` de calentamiento con el MISMO formset no sirve: el QuerySet del
    campo `servicio` se queda con su `_result_cache` y, con él, cada instancia
    ya trae su `proveedor_principal` resuelto. La segunda pasada da cero
    consultas y el N+1 desaparece de la medición aunque siga en el código —
    fue justo lo que pasó al escribir esta prueba. Se calienta con un formset
    DESECHABLE, que sí carga las plantillas y las cachés de proceso sin
    envenenar el que se mide.
    """
    _pintar(proyecto)  # calienta plantillas y cachés (mapa de alias, estados…)
    with CaptureQueriesContext(connection) as q:
        _pintar(proyecto)
    return len(q.captured_queries)


def test_el_queryset_de_producto_precarga_el_proveedor_principal(
    catalogo, proyecto_factory, usuario_factory,
):
    """La causa exacta: `label_from_instance` pide `s.proveedor_default` de CADA
    opción y eso toca el FK `proveedor_principal`. El queryset de la clase sí lo
    precargaba, pero el que se REARMA para una línea ya guardada —para que un
    producto archivado siga siendo una opción válida— lo había perdido."""
    from apps.los_proyectos.forms import ProyectoProductoFormSetDetalle
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="N+1", creado_por=admin)
    srv = catalogo["servicios"](1)[0]
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=1)

    form = ProyectoProductoFormSetDetalle(instance=p).forms[0]
    qs = form.fields["servicio"].queryset
    assert "proveedor_principal" in qs.query.select_related, (
        "sin select_related son ~51 consultas por tarjeta (medido en La Sede)"
    )
    precargados = {
        getattr(x, "prefetch_to", x) for x in qs._prefetch_related_lookups
    }
    assert "proveedores" in precargados, "también hace falta el prefetch de la M2M"


def test_el_costo_de_pintar_no_crece_con_el_catalogo(
    catalogo, proyecto_factory, usuario_factory,
):
    """La firma de un N+1 sobre las OPCIONES: cada producto del catálogo sumaba
    una consulta, así que un catálogo de 75 costaba 51 por tarjeta. Con el
    select_related, agregar 18 productos al catálogo no cuesta ni una."""
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    servicios = catalogo["servicios"](6)
    p = proyecto_factory(nombre="Catálogo chico", creado_por=admin)
    for s in servicios[:3]:
        ProyectoProducto.objects.create(proyecto=p, servicio=s, cantidad=1)

    con_pocos = _consultas_al_pintar(p)
    catalogo["servicios"](18)          # el catálogo crece; las líneas no
    con_muchos = _consultas_al_pintar(p)

    assert con_muchos - con_pocos <= 2, (
        f"pintar cuesta {con_pocos} consultas con 6 productos en el catálogo y "
        f"{con_muchos} con 24: sigue habiendo un N+1 sobre las opciones"
    )


def test_al_crear_un_producto_el_OOB_devuelve_el_formset_con_su_pk(
    client, catalogo, proyecto_factory, usuario_factory,
):
    """El contrato que evita la DUPLICACIÓN (el bug que motivó el rerender en
    V8): tras crear una línea inline, la respuesta trae el formset con el `pk`
    de la nueva. No se cambió a «devolver sólo la tarjeta» a propósito — el
    formset se re-ordena al recargar, así que un swap parcial desalinearía los
    índices y el siguiente autoguardado escribiría en la fila equivocada."""
    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(nombre="Alta inline", creado_por=admin)
    srv = catalogo["servicios"](1)[0]
    client.force_login(admin)

    datos = {
        **BASE_FORMSET, "nombre": p.nombre, "cliente": p.cliente_id,
        "estado": p.estado, "productos-TOTAL_FORMS": "1",
        "productos-0-servicio": srv.pk, "productos-0-cantidad": "2",
        "productos-0-incluir_en_calculo": "on",
    }
    resp = client.post(reverse("proyectos-detalle", args=[p.pk]), datos,
                       HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    nueva = p.productos.get()
    assert 'id="formset-productos"' in cuerpo, "no llegó el rerender del formset"
    assert f'value="{nueva.pk}"' in cuerpo, "la tarjeta nueva volvió sin su pk"


# ── Nota 8: la precedencia del color (diagnóstico, sin cambio de código) ───

def test_el_color_lo_dicta_el_texto_y_manda_el_alias():
    """Los cinco choques de color que hay hoy en La Sede son «Caso A»: los dos
    productos MENCIONAN el mismo color (el cliente «Cruz Azul» pinta de azul sus
    seis líneas, dos «blanco» salen del mismo gris…). Es la regla que se pidió,
    no un reparto colisionado, así que no se tocó el código. Este test fija la
    precedencia para que el diagnóstico siga siendo válido."""
    from apps.los_proyectos import colores

    # Entre textos manda el ORDEN en que se pasan: alias → catálogo → nota.
    assert colores.color_del_texto("Números Azules", "Playera Roja", "") == "#465fff"
    # Dentro de un texto, el que se menciona primero.
    assert colores.color_del_texto("Tote rojo con asa azul") == "#e11d48"
    # Sin color mencionado, no inventa: el reparto lo decide el modelo.
    assert colores.color_del_texto("Gorra Pana", "", "") == ""


def test_el_reparto_no_repite_un_color_ya_ocupado():
    """El «Caso B» que se buscaba (dos líneas con el MISMO color repartido) no
    puede pasar: el reparto salta lo ocupado."""
    from apps.los_proyectos import colores

    usados = list(colores.PALETA[:3])
    assert colores.elegir_color_libre(usados) == colores.PALETA[3]
