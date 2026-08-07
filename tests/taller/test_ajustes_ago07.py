"""LC 2026-08-07 — notas de Oscar sobre el deploy del 4 de agosto.

Cubre el ticket completo:

* El Chalán: el resultado dice QUÉ acción se logró o falló (con el nombre de la
  entidad y el motivo), y las acciones se aplican por dependencia —clientes,
  luego proyectos, luego tareas— no en el orden en que el LLM las contó.
* El Chalán no asigna responsable a una tarea si no se lo pidieron.
* Tarjeta de producto: al elegir producto, el costo del catálogo SIEMPRE pisa.
* El título grande del proyecto se actualiza mientras escribes el nombre.
* Guardar fijo arriba a la derecha, con el grupo original escondido (Taller).
* Arrastrar tareas para ordenarlas, en las dos tablas.
* Cancelar pregunta por qué (se puede omitir) y todo cae en Estadísticas de
  cancelación.
* Al generar la cotización sale el modal de «¿pasar a Esperando respuesta?».
* Los gastos de proceso sin proveedor salen al pie del recuadro y se ligan.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

TPL_JS_PRODUCTOS = Path("el-taller/templates/proyectos/_form_productos_js.html")
TPL_DETALLE = Path("el-taller/templates/proyectos/detalle.html")
TPL_CHAT = Path("el-taller/templates/el_dictado/_chat_mensajes.html")
TPL_PANEL_TAREAS = Path("el-taller/templates/proyectos/_tareas_panel.html")
TPL_LISTA_TAREAS = Path("el-taller/templates/pizarron/lista.html")
JS_TALLER = Path("el-taller/static/js/ui.js")
JS_GERENCIA = Path("la-gerencia/static/js/ui.js")


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_user(
        email="jefa@lc.mx", password="x", rol="super_admin", nombre_completo="Jefa LC",
    )


@pytest.fixture
def otro_user(django_user_model):
    return django_user_model.objects.create_user(
        email="disena@lc.mx", password="x", rol="miembro", nombre_completo="Dani Diseño",
    )


@pytest.fixture
def cliente():
    from apps.la_cartera.models import Cliente
    return Cliente.objects.create(razon_social="Corriendo Club")


@pytest.fixture
def proyecto(cliente):
    from apps.los_proyectos.models import Proyecto
    return Proyecto.objects.create(nombre="Playeras Corriendo Club", cliente=cliente)


# ── (1) El Chalán: el resultado dice QUÉ falló ───────────────────────────────


@pytest.mark.parametrize(("payload", "esperado"), [
    ({"titulo": "Seguimiento de diseños"}, "Seguimiento de diseños"),
    ({"nombre": "Jeep Parte 2"}, "Jeep Parte 2"),
    ({"razon_social": "KARI KARI"}, "KARI KARI"),
    ({"campos": {"titulo": "Cotizar bordado"}}, "Cotizar bordado"),
    # Los prefijos de referencia estorban en la tarjeta.
    ({"cliente_slug": "$optimist"}, "optimist"),
    ({}, ""),
])
def test_el_resumen_dice_de_que_era_la_accion(payload, esperado):
    from apps.el_dictado.presentacion import resumen_accion
    assert resumen_accion("crear_tarea", payload) == esperado


def test_el_error_se_recorta_para_la_burbuja():
    from apps.el_dictado.presentacion import error_legible
    assert error_legible("  falta  el   proyecto ") == "falta el proyecto"
    largo = error_legible("x" * 500)
    assert len(largo) <= 160 and largo.endswith("…")
    assert error_legible(None) == ""


def test_la_burbuja_del_resultado_pinta_nombre_y_error():
    html = TPL_CHAT.read_text(encoding="utf-8")
    assert "a.resumen_visible" in html
    assert "a.error_visible" in html


def test_las_propiedades_del_modelo_exponen_resumen_y_error(admin_user):
    from apps.el_dictado.models import Dictado, DictadoAccion
    d = Dictado.objects.create(autor=admin_user, texto_crudo="x", estado="aplicado")
    a = DictadoAccion.objects.create(
        dictado=d, orden=0, tipo="crear_tarea", descripcion="d",
        payload={"titulo": "Seguimiento de diseños"},
        error_al_aplicar="Proyecto no encontrado.",
    )
    assert a.resumen_visible == "Seguimiento de diseños"
    assert a.error_visible == "Proyecto no encontrado."


# ── (2) El Chalán: orden de ejecución por dependencia ────────────────────────


def test_las_acciones_se_aplican_clientes_proyectos_tareas(admin_user):
    """El LLM las contó al revés; se aplican en orden de dependencia."""
    from apps.el_dictado.models import Dictado, DictadoAccion
    from apps.el_dictado.services import _orden_de_ejecucion
    d = Dictado.objects.create(autor=admin_user, texto_crudo="x", estado="esperando_confirmacion")
    tipos_al_reves = ["crear_tarea", "crear_proyecto", "crear_cliente", "crear_servicio"]
    for i, tipo in enumerate(tipos_al_reves):
        DictadoAccion.objects.create(dictado=d, orden=i, tipo=tipo, descripcion="d", payload={})
    orden = [a.tipo for a in _orden_de_ejecucion(list(d.acciones.all()))]
    assert orden == ["crear_servicio", "crear_cliente", "crear_proyecto", "crear_tarea"]


def test_dentro_del_mismo_escalon_manda_el_orden_del_chalan(admin_user):
    from apps.el_dictado.models import Dictado, DictadoAccion
    from apps.el_dictado.services import _orden_de_ejecucion
    d = Dictado.objects.create(autor=admin_user, texto_crudo="x", estado="esperando_confirmacion")
    for i in range(3):
        DictadoAccion.objects.create(
            dictado=d, orden=i, tipo="crear_tarea", descripcion="d", payload={"titulo": f"T{i}"})
    orden = [a.payload["titulo"] for a in _orden_de_ejecucion(list(d.acciones.all()))]
    assert orden == ["T0", "T1", "T2"]


def test_un_tipo_desconocido_va_al_final(admin_user):
    from apps.el_dictado.models import Dictado, DictadoAccion
    from apps.el_dictado.services import _orden_de_ejecucion
    d = Dictado.objects.create(autor=admin_user, texto_crudo="x", estado="esperando_confirmacion")
    DictadoAccion.objects.create(dictado=d, orden=0, tipo="registrar_egreso", descripcion="d", payload={})
    DictadoAccion.objects.create(dictado=d, orden=1, tipo="crear_cliente", descripcion="d", payload={})
    orden = [a.tipo for a in _orden_de_ejecucion(list(d.acciones.all()))]
    assert orden == ["crear_cliente", "registrar_egreso"]


# ── (3) El Chalán no asigna responsable si no se lo piden ────────────────────


def test_una_tarea_dictada_sin_responsable_queda_general(admin_user, proyecto):
    from apps.los_proyectos.tareas_ia import aplicar_tareas
    res = aplicar_tareas(
        proyecto=proyecto, usuario=admin_user,
        tareas=[{"titulo": "Mandar a imprimir", "responsable": ""}],
    )
    assert res["creadas"] == 1
    from apps.el_pizarron.models import Tarea
    assert Tarea.objects.get(titulo="Mandar a imprimir").asignada_a_id is None


def test_una_tarea_dictada_con_responsable_si_se_asigna(admin_user, otro_user, proyecto):
    from apps.los_proyectos.tareas_ia import aplicar_tareas
    aplicar_tareas(
        proyecto=proyecto, usuario=admin_user,
        tareas=[{"titulo": "Cotizar bordado", "asignada_id": otro_user.pk}],
    )
    from apps.el_pizarron.models import Tarea
    assert Tarea.objects.get(titulo="Cotizar bordado").asignada_a_id == otro_user.pk


def test_el_prompt_prohibe_adivinar_al_responsable():
    from apps.el_dictado.prompt import SYSTEM_PROMPT
    assert "asignado_slug` SÓLO si te dijeron a quién" in SYSTEM_PROMPT


# ── (4) Costo unitario: el catálogo siempre pisa ─────────────────────────────


def test_al_elegir_producto_el_costo_del_catalogo_pisa():
    js = TPL_JS_PRODUCTOS.read_text(encoding="utf-8")
    assert "if (costo) costo.value = datos.costo;" in js
    # El precio NO se pisa: ése se negocia por proyecto.
    assert "if (precio && !precio.value) precio.value = datos.precio;" in js


# ── (5) Título del proyecto en vivo ─────────────────────────────────────────


def test_el_titulo_del_proyecto_se_actualiza_al_escribir():
    html = TPL_DETALLE.read_text(encoding="utf-8")
    assert 'id="titulo-proyecto"' in html
    assert "titulo.textContent = nombre" in html


# ── (6) Guardar fijo arriba a la derecha ────────────────────────────────────


def test_el_guardar_fijo_es_del_taller_y_esconde_el_original():
    taller = JS_TALLER.read_text(encoding="utf-8")
    assert taller == JS_GERENCIA.read_text(encoding="utf-8"), "ui.js es dual-copy (regla §18)"
    # El interruptor lo pone el <body> del Taller; Gerencia no lo prende.
    assert "data-guardar-fijo" in taller
    assert "data-guardar-fijo" in Path("el-taller/templates/base.html").read_text(encoding="utf-8")
    assert "data-guardar-fijo" not in Path("la-gerencia/templates/base.html").read_text(encoding="utf-8")
    # Esconde el grupo original y arrastra los botones vecinos.
    assert "data-guardar-flotante-origen" in taller
    assert "esconderOriginal" in taller
    assert "grupo.botones.forEach" in taller
    # Sigue haciendo click en el botón real (no lo clona ni lo mueve).
    assert "real.click()" in taller
    assert "data-sin-guardar-flotante" in taller
    assert "#modal-slot" in taller


def test_la_barra_se_remonta_si_htmx_reemplaza_un_boton():
    """El «↶ Deshacer» llega por OOB en cada autoguardado del proyecto: sin esto
    el proxy se quedaría picando un nodo que ya no está en la página."""
    taller = JS_TALLER.read_text(encoding="utf-8")
    assert "grupoVigente" in taller
    assert "isConnected" in taller


def test_solo_los_botones_que_guardan_se_llevan_arriba():
    """«Filtrar», «Confirmar» o «Volver a mi cuenta» no son un Guardar."""
    taller = JS_TALLER.read_text(encoding="utf-8")
    assert "RE_GUARDA" in taller
    assert "guardar|crear|actualizar|registrar|emitir" in taller


# ── (7) Arrastrar tareas ────────────────────────────────────────────────────


def test_las_dos_tablas_de_tareas_traen_el_arrastre():
    for tpl in (TPL_PANEL_TAREAS, TPL_LISTA_TAREAS):
        html = tpl.read_text(encoding="utf-8")
        assert "data-tareas-orden" in html, tpl
        assert "data-tarea-asa" in html, tpl
        assert 'data-tarea-id="{{ t.pk }}"' in html, tpl
        assert "pizarron/_tareas_orden_js.html" in html, tpl


def test_reordenar_guarda_el_orden(client, admin_user, proyecto):
    from apps.el_pizarron.models import Tarea
    a = Tarea.objects.create(proyecto=proyecto, titulo="A", creado_por=admin_user)
    b = Tarea.objects.create(proyecto=proyecto, titulo="B", creado_por=admin_user)
    c = Tarea.objects.create(proyecto=proyecto, titulo="C", creado_por=admin_user)
    client.force_login(admin_user)
    resp = client.post("/tareas/reordenar", {"orden": [c.pk, a.pk, b.pk]})
    assert resp.status_code == 204
    c.refresh_from_db()
    a.refresh_from_db()
    b.refresh_from_db()
    assert (c.orden, a.orden, b.orden) == (0, 1, 2)
    assert list(Tarea.objects.filter(proyecto=proyecto).values_list("titulo", flat=True)) == ["C", "A", "B"]


def test_reordenar_ignora_lo_que_no_puedo_ver(client, otro_user, proyecto, admin_user):
    """Un pk ajeno se salta en silencio, no rompe el resto."""
    from apps.el_pizarron.models import Tarea
    mia = Tarea.objects.create(
        proyecto=proyecto, titulo="Mía", creado_por=otro_user, asignada_a=otro_user)
    ajena = Tarea.objects.create(proyecto=proyecto, titulo="Ajena", creado_por=admin_user)
    client.force_login(otro_user)
    resp = client.post("/tareas/reordenar", {"orden": [ajena.pk, mia.pk]})
    assert resp.status_code == 204
    ajena.refresh_from_db()
    mia.refresh_from_db()
    assert ajena.orden == 0, "una tarea que no ve no se le mueve"
    assert mia.orden == 1, "la suya sí toma su posición en la lista que mandó"


def test_reordenar_no_acepta_get(client, admin_user):
    client.force_login(admin_user)
    assert client.get("/tareas/reordenar").status_code == 405


# ── (8) Cancelación con motivo ──────────────────────────────────────────────


def test_los_motivos_base_estan_sembrados():
    from apps.los_proyectos.models import MotivoCancelacion
    slugs = set(MotivoCancelacion.objects.values_list("slug", flat=True))
    assert {"precio", "cliente_desistio", "tiempos", "otro"} <= slugs
    assert MotivoCancelacion.objects.filter(sistema=True).count() >= 4


def test_cancelar_sella_la_fecha_y_pide_el_motivo(client, admin_user, proyecto):
    client.force_login(admin_user)
    resp = client.post(
        f"/proyectos/{proyecto.pk}/cambiar-estado",
        {"estado": "cancelado"}, HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    proyecto.refresh_from_db()
    assert proyecto.estado == "cancelado"
    assert proyecto.cancelado_en is not None
    # Y avisa a la UI para que abra el «¿por qué se canceló?».
    assert "pedirMotivoCancelacion" in resp.headers.get("HX-Trigger", "")


def test_cambiar_a_otro_estado_no_pide_motivo(client, admin_user, proyecto):
    client.force_login(admin_user)
    resp = client.post(
        f"/proyectos/{proyecto.pk}/cambiar-estado",
        {"estado": "en_proceso_diseno"}, HTTP_HX_REQUEST="true",
    )
    assert "pedirMotivoCancelacion" not in resp.headers.get("HX-Trigger", "")


def test_guardar_el_motivo(client, admin_user, proyecto):
    from apps.los_proyectos.models import MotivoCancelacion
    client.force_login(admin_user)
    resp = client.post(
        f"/proyectos/{proyecto.pk}/motivo-cancelacion",
        {"motivo": "precio", "nota": "Se fueron con otro proveedor."},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    proyecto.refresh_from_db()
    assert proyecto.motivo_cancelacion == MotivoCancelacion.objects.get(slug="precio")
    assert proyecto.nota_cancelacion == "Se fueron con otro proveedor."


def test_el_motivo_se_puede_omitir(client, admin_user, proyecto):
    """Cancelar nunca se bloquea: sin motivo el proyecto queda «Sin información»."""
    client.force_login(admin_user)
    client.post(f"/proyectos/{proyecto.pk}/cambiar-estado", {"estado": "cancelado"},
                HTTP_HX_REQUEST="true")
    resp = client.get("/proyectos/cancelaciones/")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    assert "Sin información" in cuerpo
    assert "Agregar +" in cuerpo


def test_estadisticas_agrupan_por_motivo(client, admin_user, cliente):
    from apps.los_proyectos.models import MotivoCancelacion, Proyecto
    precio = MotivoCancelacion.objects.get(slug="precio")
    for i in range(3):
        Proyecto.objects.create(nombre=f"P{i}", cliente=cliente, estado="cancelado",
                                motivo_cancelacion=precio)
    Proyecto.objects.create(nombre="Sin razón", cliente=cliente, estado="cancelado")
    client.force_login(admin_user)
    resp = client.get("/proyectos/cancelaciones/")
    ctx = resp.context
    assert ctx["total"] == 4
    assert ctx["sin_info"] == 1
    primero = ctx["resumen"][0]
    assert primero["label"] == "Precio" and primero["n"] == 3 and primero["pct"] == 75


def test_el_boton_de_estadisticas_esta_en_las_dos_vistas():
    for tpl in ("el-taller/templates/proyectos/kanban.html",
                "el-taller/templates/proyectos/lista.html"):
        html = Path(tpl).read_text(encoding="utf-8")
        assert "proyectos-cancelaciones" in html, tpl
        assert "justify-center" in html, tpl


def test_cancelar_desde_el_chalan_tambien_sella_la_fecha(admin_user, proyecto):
    from apps.el_dictado.ejecutores.basicos import actualizar_proyecto
    from apps.el_dictado.models import Dictado, DictadoAccion
    d = Dictado.objects.create(autor=admin_user, texto_crudo="x", estado="esperando_confirmacion")
    accion = DictadoAccion.objects.create(
        dictado=d, orden=0, tipo="actualizar_proyecto", descripcion="d",
        payload={"proyecto_slug": proyecto.slug, "campos": {"estado": "cancelado"}},
    )
    actualizar_proyecto(accion, admin_user, {})
    proyecto.refresh_from_db()
    assert proyecto.estado == "cancelado"
    assert proyecto.cancelado_en is not None


# ── (9) Modal de «Esperando respuesta» al generar la cotización ─────────────


def test_al_generar_la_cotizacion_sale_el_modal(client, admin_user, proyecto):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    cat = CategoriaServicio.objects.create(nombre="Maquila")
    srv = Servicio.objects.create(nombre="Playera", categoria=cat,
                                  precio_base=Decimal("190.00"))
    ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, cantidad=10,
                                    precio_unitario=Decimal("190.00"))
    proyecto.estado = "por_cotizar"
    proyecto.save(update_fields=["estado"])
    client.force_login(admin_user)
    resp = client.post(f"/proyectos/{proyecto.pk}/cotizacion/generar", HTTP_HX_REQUEST="true")
    cuerpo = resp.content.decode()
    assert resp.status_code == 200
    assert 'id="modal-slot" hx-swap-oob="innerHTML"' in cuerpo
    assert "Esperando respuesta" in cuerpo


def test_si_el_proyecto_ya_avanzo_no_sale_el_modal(client, admin_user, proyecto):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    cat = CategoriaServicio.objects.create(nombre="Maquila")
    srv = Servicio.objects.create(nombre="Playera", categoria=cat, precio_base=Decimal("190"))
    ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, cantidad=10,
                                    precio_unitario=Decimal("190.00"))
    proyecto.estado = "en_proceso_diseno"
    proyecto.save(update_fields=["estado"])
    client.force_login(admin_user)
    resp = client.post(f"/proyectos/{proyecto.pk}/cotizacion/generar", HTTP_HX_REQUEST="true")
    assert 'id="modal-slot"' not in resp.content.decode()


# ── (10) Gastos sin proveedor ───────────────────────────────────────────────


@pytest.fixture
def linea_con_gasto(proyecto):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto, ProyectoProductoProceso
    cat = CategoriaServicio.objects.create(nombre="Maquila")
    srv = Servicio.objects.create(nombre="Playera", categoria=cat, precio_base=Decimal("190"))
    linea = ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, cantidad=10)
    proc = ProyectoProductoProceso.objects.create(
        producto=linea, tipo="operativo", descripcion="Adaptación y positivos",
        costo=Decimal("150.00"), por_pieza=False,
    )
    return {"linea": linea, "proc": proc}


def test_un_gasto_sin_proveedor_sale_al_pie_del_recuadro(proyecto, linea_con_gasto):
    from apps.los_proyectos.views import _gastos_sin_proveedor
    sueltos = _gastos_sin_proveedor(proyecto)
    assert len(sueltos) == 1
    assert sueltos[0]["nombre"] == "Adaptación y positivos"
    assert sueltos[0]["monto"] == Decimal("150.00")


def test_ligar_el_gasto_lo_saca_de_los_sueltos(client, admin_user, proyecto, linea_con_gasto):
    from apps.el_catalogo.models import Proveedor
    from apps.los_proyectos.views import _gastos_sin_proveedor, _proveedores_panel
    prov = Proveedor.objects.create(razon_social="Tessa Studio")
    client.force_login(admin_user)
    resp = client.post(
        f"/proyectos/{proyecto.pk}/gasto/{linea_con_gasto['proc'].pk}/proveedor",
        {"proveedor": prov.pk}, HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    proyecto.refresh_from_db()
    assert _gastos_sin_proveedor(proyecto) == []
    filas = _proveedores_panel(proyecto)
    assert any(f["proveedor"].pk == prov.pk and f["total"] == Decimal("150.00") for f in filas)


def test_un_proveedor_inventado_no_se_liga(client, admin_user, proyecto, linea_con_gasto):
    client.force_login(admin_user)
    resp = client.post(
        f"/proyectos/{proyecto.pk}/gasto/{linea_con_gasto['proc'].pk}/proveedor",
        {"proveedor": 99999}, HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 403
    linea_con_gasto["proc"].refresh_from_db()
    assert linea_con_gasto["proc"].proveedor_id is None


def test_el_recuadro_pinta_los_gastos_sueltos():
    html = Path("el-taller/templates/proyectos/_proveedores_panel.html").read_text(encoding="utf-8")
    assert "Gastos sin proveedor" in html
    assert "proyectos-ligar-gasto-proveedor" in html
    # No debe arrastrar el form del proyecto ni disparar el autoguardado.
    assert 'hx-params="none"' in html
    assert "event.stopPropagation()" in html
