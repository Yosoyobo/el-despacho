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
def categoria(db):
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


# ═════════════════════════════════════════════════════════════════════════════
# Duplicar producto — «que se lleve absolutamente todos los datos» (Oscar)
# ═════════════════════════════════════════════════════════════════════════════

def _producto_completo(categoria):
    """Un producto con TODO lleno, para que el test note cualquier olvido."""
    from decimal import Decimal

    from apps.el_catalogo.models import Proveedor, Servicio
    from apps.el_catalogo.models.variacion import Variacion
    p1 = Proveedor.objects.create(razon_social="Telas del Norte", activo=True)
    p2 = Proveedor.objects.create(razon_social="Bordados Ana", activo=True)
    srv = Servicio.objects.create(
        nombre="Playera Dry Fit", categoria=categoria,
        descripcion_default="100% poliéster, cuello redondo",
        unidad="pz", precio_base=Decimal("220.00"), costo=Decimal("88.00"),
        activo=True, imagen_file_id="abc123", imagen_url="https://x/abc123",
        proveedor_principal=p1,
        detalles_costo={"sublimacion": ["35.00"], "mano_obra": "20.00"},
        procesos_default=[
            {"tipo": "impresion", "proveedor_id": p1.pk, "costo": "12.50", "por_pieza": True},
            {"tipo": "operativo", "descripcion": "Embalaje", "costo": "30.00",
             "por_pieza": False, "proveedor_id": p2.pk},
        ],
    )
    srv.proveedores.set([p1, p2])
    Variacion.objects.create(
        servicio=srv, nombre="Negra", costo=Decimal("90.00"),
        impresion_activa=True, impresion_costo=Decimal("15.00"),
        impresion_descripcion="Frente", descripcion="Talla estándar",
        disponible=True,
    )
    return srv


@pytest.fixture
def producto_completo(categoria):
    return _producto_completo(categoria)


def test_duplicar_producto_se_lleva_todos_los_datos(producto_completo, usuario_factory):
    """Campo por campo: si mañana se agrega uno y se olvida copiarlo, esto falla."""
    from apps.el_catalogo.duplicar import duplicar_servicio
    origen = producto_completo
    copia = duplicar_servicio(origen, actor=usuario_factory(rol="super_admin"))

    assert copia.pk != origen.pk
    assert copia.nombre == "Playera Dry Fit (copia)"
    for campo in ("descripcion_default", "unidad", "precio_base", "costo",
                  "categoria_id", "activo", "imagen_file_id", "imagen_url",
                  "proveedor_principal_id", "detalles_costo", "procesos_default"):
        assert getattr(copia, campo) == getattr(origen, campo), f"no se copió {campo}"
    # Los proveedores que lo surten.
    assert set(copia.proveedores.values_list("pk", flat=True)) == \
           set(origen.proveedores.values_list("pk", flat=True))
    # Y sus variaciones.
    assert copia.variaciones.count() == origen.variaciones.count() == 1
    v = copia.variaciones.first()
    assert v.nombre == "Negra" and v.impresion_costo == origen.variaciones.first().impresion_costo


def test_duplicar_no_se_lleva_la_historia_del_original(producto_completo, usuario_factory):
    """El historial de usos es lo que le pasó al original, no un dato suyo."""
    from apps.el_catalogo.duplicar import duplicar_servicio
    copia = duplicar_servicio(producto_completo, actor=usuario_factory(rol="super_admin"))
    assert copia.en_proyectos.count() == 0


def test_duplicar_desde_la_pantalla_abre_la_copia(producto_completo, client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.post(f"/catalogo/{producto_completo.pk}/duplicar")
    assert resp.status_code == 302
    copia = Servicio.objects.exclude(pk=producto_completo.pk).get()
    # Abre la copia para ponerle nombre, no la lista.
    assert resp["Location"] == f"/catalogo/{copia.pk}/editar"


def test_duplicar_pide_permiso_de_crear(producto_completo, client, usuario_factory):
    from apps.el_catalogo.models import Servicio

    from cuentas.models.permiso_usuario import PermisoUsuario
    u = usuario_factory(rol="miembro")
    PermisoUsuario.objects.update_or_create(
        usuario=u, modulo="catalogo", permiso="crear", defaults={"activo": False})
    client.force_login(u)
    resp = client.post(f"/catalogo/{producto_completo.pk}/duplicar")
    assert resp.status_code == 403
    assert Servicio.objects.count() == 1


def test_duplicar_solo_por_post(producto_completo, client, usuario_factory):
    """Un GET no puede crear productos (ni un rastreador ni un enlace pegado)."""
    from apps.el_catalogo.models import Servicio
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get(f"/catalogo/{producto_completo.pk}/duplicar")
    assert resp.status_code == 405
    assert Servicio.objects.count() == 1


# ═════════════════════════════════════════════════════════════════════════════
# El precio se pone con un botón, y el porcentaje significa lo mismo en toda
# la app (decisión de Oscar: markup sobre el costo)
# ═════════════════════════════════════════════════════════════════════════════

def test_el_markup_es_lo_que_se_le_suma_al_costo(categoria):
    """Costo 100 y precio 200 son 100%: «el doble de lo que me cuesta».

    Antes esto medía el margen sobre el precio y con esos números daba 50%.
    """
    from decimal import Decimal

    from apps.el_catalogo.models import Servicio
    srv = Servicio(nombre="X", categoria=categoria,
                   costo=Decimal("100.00"), precio_base=Decimal("200.00"))
    assert round(srv.margen_porcentaje, 1) == 100.0
    srv.precio_base = Decimal("150.00")
    assert round(srv.margen_porcentaje, 1) == 50.0
    srv.precio_base = Decimal("130.00")
    assert round(srv.margen_porcentaje, 1) == 30.0


def test_sin_costo_no_se_puede_medir(categoria):
    from decimal import Decimal

    from apps.el_catalogo.models import Servicio
    srv = Servicio(nombre="X", categoria=categoria,
                   costo=Decimal("0"), precio_base=Decimal("200.00"))
    assert srv.margen_porcentaje == 0.0


def test_el_boton_y_la_columna_dicen_lo_mismo(categoria):
    """El contrato que hace útil el cambio: picas +50% y la columna dice 50%."""
    from decimal import Decimal

    from apps.el_catalogo.models import Servicio
    costo = Decimal("88.00")
    for pct in (30, 50, 70, 100):
        # Esto es exactamente lo que hace el botón en la pantalla.
        precio = costo * (1 + Decimal(pct) / 100)
        srv = Servicio(nombre="X", categoria=categoria, costo=costo, precio_base=precio)
        assert round(srv.margen_porcentaje) == pct


def test_ordenar_por_markup_mide_lo_mismo_que_la_columna(categoria, client, usuario_factory):
    """La lista ordena en SQL; si las dos fórmulas se separan, el orden miente."""
    from decimal import Decimal

    from apps.el_catalogo.models import Servicio
    barato = Servicio.objects.create(nombre="Poco markup", categoria=categoria,
                                     costo=Decimal("100"), precio_base=Decimal("130"))
    caro = Servicio.objects.create(nombre="Mucho markup", categoria=categoria,
                                   costo=Decimal("100"), precio_base=Decimal("300"))
    client.force_login(usuario_factory(rol="super_admin"))
    resp = client.get("/catalogo/?orden=-margen")
    filas = list(resp.context["servicios"])
    assert [f.pk for f in filas][:2] == [caro.pk, barato.pk]
    # Y el número que se pinta es el mismo que el que ordenó.
    assert round(filas[0].margen_porcentaje) == 200
    assert round(filas[0].margen_calc) == 200


def test_los_botones_de_precio_estan_en_la_ficha(categoria, client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    srv = Servicio.objects.create(nombre="Gorra", categoria=categoria,
                                  costo=100, precio_base=200)
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get(f"/catalogo/{srv.pk}/editar").content.decode()
    assert 'data-markup-rapido' in html
    for pct in ("30", "50", "70", "100"):
        assert f'data-markup="{pct}"' in html


def test_el_nombre_del_producto_es_el_titulo(categoria, client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    srv = Servicio.objects.create(nombre="Playera Dry Fit", categoria=categoria,
                                  costo=100, precio_base=200)
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get(f"/catalogo/{srv.pk}/editar").content.decode()
    assert 'id="titulo-producto"' in html
    assert ">Playera Dry Fit</h1>" in html
    assert "Editar producto</h1>" not in html
    assert "<title>Playera Dry Fit — Productos</title>" in html


# ═════════════════════════════════════════════════════════════════════════════
# Un solo selector de proveedores, y el primero manda
# ═════════════════════════════════════════════════════════════════════════════

def _prov(razon):
    from apps.el_catalogo.models import Proveedor
    return Proveedor.objects.create(razon_social=razon, activo=True)


def test_el_primero_que_se_marca_queda_como_principal(categoria, client, usuario_factory):
    """Aunque alfabéticamente vaya después: el orden lo manda la pantalla."""
    from apps.el_catalogo.models import Servicio
    alfa, zeta = _prov("Alfa Textiles"), _prov("Zeta Bordados")
    client.force_login(usuario_factory(rol="super_admin"))
    client.post("/catalogo/nuevo", {
        "nombre": "Sudadera", "descripcion_default": "", "costo": "50",
        "precio_base": "100", "categoria": categoria.pk,
        "proveedores": [str(alfa.pk), str(zeta.pk)],
        "proveedores_orden": f"{zeta.pk},{alfa.pk}",
    })
    srv = Servicio.objects.get(nombre="Sudadera")
    assert srv.proveedor_principal_id == zeta.pk
    assert srv.proveedor_default == zeta


def test_sin_orden_manda_como_llegaron_las_casillas(categoria, client, usuario_factory):
    """Un POST viejo (o el alta rápida) sigue funcionando."""
    from apps.el_catalogo.models import Servicio
    alfa, zeta = _prov("Alfa Textiles"), _prov("Zeta Bordados")
    client.force_login(usuario_factory(rol="super_admin"))
    client.post("/catalogo/nuevo", {
        "nombre": "Gorra", "descripcion_default": "", "costo": "50",
        "precio_base": "100", "categoria": categoria.pk,
        "proveedores": [str(zeta.pk), str(alfa.pk)],
    })
    assert Servicio.objects.get(nombre="Gorra").proveedor_principal_id == zeta.pk


def test_quitar_al_principal_corona_al_siguiente(categoria, client, usuario_factory):
    """Antes se quedaba apuntando a quien ya no surte y había que avisarlo."""
    from apps.el_catalogo.models import Servicio
    alfa, zeta = _prov("Alfa Textiles"), _prov("Zeta Bordados")
    srv = Servicio.objects.create(nombre="Playera", categoria=categoria,
                                  costo=50, precio_base=100, proveedor_principal=zeta)
    srv.proveedores.set([alfa, zeta])
    client.force_login(usuario_factory(rol="super_admin"))
    client.post(f"/catalogo/{srv.pk}/editar", {
        "nombre": "Playera", "descripcion_default": "", "costo": "50",
        "precio_base": "100", "categoria": categoria.pk,
        "proveedores": [str(alfa.pk)],
        "proveedores_orden": str(alfa.pk),
    })
    srv.refresh_from_db()
    assert srv.proveedor_principal_id == alfa.pk


def test_sin_proveedores_no_hay_principal(categoria, client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    zeta = _prov("Zeta Bordados")
    srv = Servicio.objects.create(nombre="Termo", categoria=categoria,
                                  costo=50, precio_base=100, proveedor_principal=zeta)
    srv.proveedores.set([zeta])
    client.force_login(usuario_factory(rol="super_admin"))
    client.post(f"/catalogo/{srv.pk}/editar", {
        "nombre": "Termo", "descripcion_default": "", "costo": "50",
        "precio_base": "100", "categoria": categoria.pk,
    })
    srv.refresh_from_db()
    assert srv.proveedor_principal_id is None


def test_la_ficha_abre_con_el_principal_al_frente(categoria, client, usuario_factory):
    """La ★ tiene que señalar al principal guardado, no al primero alfabético."""
    from apps.el_catalogo.models import Servicio
    alfa, zeta = _prov("Alfa Textiles"), _prov("Zeta Bordados")
    srv = Servicio.objects.create(nombre="Playera", categoria=categoria,
                                  costo=50, precio_base=100, proveedor_principal=zeta)
    srv.proveedores.set([alfa, zeta])
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get(f"/catalogo/{srv.pk}/editar").content.decode()
    assert f'value="{zeta.pk},{alfa.pk}"' in html


def test_el_orden_no_deja_pasar_ids_inventados(categoria, client, usuario_factory):
    """El campo viene del navegador: sólo cuentan los que quedaron ligados."""
    from apps.el_catalogo.models import Servicio
    alfa = _prov("Alfa Textiles")
    client.force_login(usuario_factory(rol="super_admin"))
    client.post("/catalogo/nuevo", {
        "nombre": "Mochila", "descripcion_default": "", "costo": "50",
        "precio_base": "100", "categoria": categoria.pk,
        "proveedores": [str(alfa.pk)],
        "proveedores_orden": f"999999,{alfa.pk}",
    })
    assert Servicio.objects.get(nombre="Mochila").proveedor_principal_id == alfa.pk


def test_el_control_de_proveedores_es_uno_solo():
    src = TPL_FICHA.read_text(encoding="utf-8")
    assert 'id="prov-picker"' not in src, "volvió el segundo desplegable"
    assert 'name="proveedor_principal"' not in src, "volvió el selector del ★"
    assert src.count('data-multi-buscable="proveedor"') == 1


# ═════════════════════════════════════════════════════════════════════════════
# Camino a la ficha del producto desde su tarjeta en el proyecto
# ═════════════════════════════════════════════════════════════════════════════

def test_la_tarjeta_lleva_a_la_ficha_del_producto():
    src = TPL_CARD.read_text(encoding="utf-8")
    assert "data-editar-producto" in src
    assert "catalogo-editar" in src
    # En otra pestaña: el proyecto se está capturando y no hay por qué salirse.
    i = src.index("data-editar-producto")
    assert 'target="_blank"' in src[i - 200:i + 200]


def test_el_enlace_sigue_al_producto_elegido():
    """Si se cambia de producto sin recargar, el enlace tiene que ir al nuevo."""
    js = TPL_JS_TARJETA.read_text(encoding="utf-8")
    assert "function actualizarEnlaceFicha" in js
    tramo = js[js.index("function actualizarEnlaceFicha"):]
    assert "'/catalogo/' + pk + '/editar'" in tramo[:600]
    # Y se llama al elegir producto y al montar cada tarjeta.
    assert js.count("actualizarEnlaceFicha(card)") >= 2
