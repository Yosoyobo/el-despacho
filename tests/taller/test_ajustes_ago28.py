"""LC 2026-08-28 — notas de Oscar sobre el deploy del 24 de agosto.

Sprint 1 · «Escribir sin pelearse»: el recuadro de Descripción de la tarjeta de
producto.

Dos síntomas, una sola causa. El campo crecía midiéndose en CADA tecla, y eso
traía:

1. «Aleatoriamente se hace más grande y más chico» — el alto dependía de cuándo
   se alcanzó a medir (ya se parchó una vez el 18-ago y volvió).
2. «No estoy pudiendo poner acentos ni ñs» — un acento o una ñ se escriben en
   DOS pulsaciones (´ + a) y el navegador las está «componiendo» en medio;
   medir el elemento ahí obliga a recalcular el diseño y puede cancelar esa
   composición, así que la letra sale sin acento.

La cura es la misma para los dos: el alto de reposo lo fija el CSS y sólo se
mide al entrar y al salir del campo — nunca a media composición.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.taller]

JS_UI_TALLER = Path("el-taller/static/js/ui.js")
JS_UI_GERENCIA = Path("la-gerencia/static/js/ui.js")
TPL_JS_TARJETA = Path("el-taller/templates/proyectos/_form_productos_js.html")
FORMS_PROYECTOS = Path("el-taller/apps/los_proyectos/forms.py")


# ── El campo ya no crece tecla por tecla ─────────────────────────────────────

def test_la_descripcion_crece_al_enfocar_no_al_teclear():
    """El widget declara el componente nuevo y ya no el auto-grow por tecla."""
    src = FORMS_PROYECTOS.read_text(encoding="utf-8")
    # El bloque del widget `nota` (la Descripción de la línea de producto).
    ini = src.index('"nota": forms.Textarea(')
    widget = src[ini:ini + 600]
    assert "data-crece-al-enfocar" in widget
    assert "data-autogrow" not in widget, (
        "La Descripción volvió al auto-grow por tecla: eso es lo que impedía "
        "escribir acentos y ñ, y lo que hacía que cambiara de tamaño sola."
    )


def test_el_js_de_la_tarjeta_ya_no_mide_el_textarea():
    """Nadie vuelve a medir la Descripción desde el JS del formset."""
    src = TPL_JS_TARJETA.read_text(encoding="utf-8")
    assert "autogrow" not in src, (
        "Volvió a aparecer un auto-grow en la tarjeta de producto. Medir el "
        "textarea en cada tecla es justo lo que rompía los acentos."
    )


def test_al_escribir_la_descripcion_se_sigue_repintando_el_color():
    """Quitar la medición no puede llevarse el color: una playera «negra» sale
    en negro justo mientras se escribe (regla de colores del 18-ago)."""
    src = TPL_JS_TARJETA.read_text(encoding="utf-8")
    assert "textarea[data-crece-al-enfocar]" in src
    assert "repintarColor" in src


# ── La guarda de composición (acentos y ñ) ───────────────────────────────────

@pytest.mark.parametrize("ruta", [JS_UI_TALLER, JS_UI_GERENCIA])
def test_ningun_manejador_de_texto_toca_el_tamano_a_media_composicion(ruta):
    """Todo handler de `input` que mida un textarea sale si se está componiendo.

    Sin esta guarda, escribir «café» o «año» pierde la letra acentuada: el
    navegador está a media composición y recalcular el diseño la cancela.
    """
    src = ruta.read_text(encoding="utf-8")
    # Cada bloque que reacciona a `input` sobre un textarea tiene que preguntar
    # por `isComposing` antes de tocar el alto.
    bloques = [b for b in src.split("addEventListener('input'") if "textarea" in b[:400]]
    assert bloques, "no encontré los manejadores de texto en ui.js"
    for b in bloques:
        assert "isComposing" in b[:400], (
            "Un manejador de texto dejó de respetar la composición: los acentos "
            "y la ñ se escriben en dos pulsaciones y se perderían."
        )
    # Y al terminar de componer sí se ajusta, para que el alto quede al día.
    assert "compositionend" in src


def test_el_componente_de_crecer_al_enfocar_existe_y_regresa_al_salir():
    src = JS_UI_TALLER.read_text(encoding="utf-8")
    assert "data-crece-al-enfocar" in src
    assert "focusin" in src and "focusout" in src, (
        "El recuadro tiene que volver a su tamaño al salir (pedido de Oscar)."
    )


def test_ui_js_sigue_en_dos_copias_identicas():
    """Regla §18: `ui.js` vive en El Taller y en La Gerencia, y no divergen."""
    assert JS_UI_TALLER.read_text(encoding="utf-8") == JS_UI_GERENCIA.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════════════
# El «@» para ligar un proveedor a un gasto — en TODAS partes
#
# Oscar: «el uso del @ para etiquetar proveedores en procesos adicionales,
# dentro de la página de editar un producto, no está funcionando. Asegurar que
# funcione en todos lados.»
#
# No estaba roto: existía sólo en la tarjeta del proyecto. Ahora es un
# componente compartido y lo usan las dos pantallas.
# ═════════════════════════════════════════════════════════════════════════════

JS_ARROBA = Path("el-taller/static/js/arroba_proveedor.js")
TPL_CARD = Path("el-taller/templates/proyectos/_producto_card.html")
TPL_FICHA = Path("el-taller/templates/catalogo/form.html")
TPL_BASE_TALLER = Path("el-taller/templates/base.html")


def test_el_componente_existe_y_se_carga():
    assert JS_ARROBA.exists()
    assert "arroba_proveedor.js" in TPL_BASE_TALLER.read_text(encoding="utf-8")


@pytest.mark.parametrize("tpl", [TPL_CARD, TPL_FICHA])
def test_las_dos_pantallas_con_gastos_declaran_el_arroba(tpl):
    """La tarjeta del proyecto y la ficha del producto, las dos."""
    src = tpl.read_text(encoding="utf-8")
    assert "data-arroba-fila" in src
    assert "data-arroba-proveedor" in src
    assert "catalogo-proveedor-buscar" in src, "falta la dirección del buscador"
    assert "data-proc-prov-chip" in src, "sin chip no se ve a quién quedó ligado"


def test_no_quedan_copias_del_autocompletado():
    """Copiarlo en cada pantalla es lo que hace que una se quede atrás."""
    js_tarjeta = TPL_JS_TARJETA.read_text(encoding="utf-8")
    assert "function ligar(fila" not in js_tarjeta
    # La tarjeta sólo atiende el aviso del componente para volver a guardar.
    assert "arroba:proveedor" in js_tarjeta


def test_la_ficha_guarda_el_proveedor_del_gasto():
    """Antes mandaba `proveedor_id: null` fijo: el vínculo no llegaba nunca."""
    src = TPL_FICHA.read_text(encoding="utf-8")
    assert "proveedor_id: null," not in src
    assert "data-proc-prov" in src


def test_el_proveedor_del_catalogo_viaja_al_proyecto():
    """El gasto que trae proveedor desde la ficha llega ligado a la tarjeta.

    Sin esto, la ficha guardaba un vínculo que el proyecto nunca usaba — y de
    ahí sale la deuda con ese proveedor.
    """
    js = TPL_JS_TARJETA.read_text(encoding="utf-8")
    aplicar = js[js.index("function aplicarProcesosDefault"):js.index("function aplicarCatFiltro")]
    assert "p.proveedor_id" in aplicar
    assert "data-proc-prov" in aplicar


@pytest.fixture
def categoria():
    from apps.el_catalogo.models import CategoriaServicio
    return CategoriaServicio.objects.create(nombre="Textiles")


def test_la_ficha_guarda_de_punta_a_punta_un_gasto_con_proveedor(
    client, usuario_factory, categoria
):
    """De la pantalla a la base: el proceso operativo conserva su proveedor."""
    import json

    from apps.el_catalogo.models import Proveedor, Servicio
    prov = Proveedor.objects.create(razon_social="Fletes del Centro", activo=True)
    srv = Servicio.objects.create(
        nombre="Gorra", categoria=categoria, precio_base=200, costo=80, activo=True,
    )
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(f"/catalogo/{srv.pk}/editar", {
        "nombre": "Gorra", "precio_base": "200.00", "costo": "80.00",
        "categoria": categoria.pk,
        "procesos_default_json": json.dumps([
            {"tipo": "operativo", "descripcion": "Flete a Tizayuca",
             "costo": "300.00", "por_pieza": False, "proveedor_id": prov.pk},
        ]),
    })
    assert resp.status_code == 302
    guardado = Servicio.objects.get(pk=srv.pk).procesos_default
    assert len(guardado) == 1
    assert guardado[0]["proveedor_id"] == prov.pk, (
        "el proveedor ligado con «@» tiene que llegar a la base"
    )
