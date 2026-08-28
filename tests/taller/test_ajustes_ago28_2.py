"""LC 2026-08-28 · Sprint 2 — Tareas ligadas al producto · Buscar más en el
Dashboard · Duplicar proyecto alcanzable.

Tres pedidos de Oscar del 28 de agosto:

1. «En cada tarjeta de producto involucrado, hasta abajo, podamos crear rápido
   tareas ligadas a este producto, pudiendo etiquetar gente y usando inteligencia
   para leer instrucciones con fechas, horarios, lugares.»
2. «En búsqueda del dashboard mostrar también clientes, etc. en resultados fuera
   del tablero» → clientes, productos y proveedores.
3. «Agregar botones de duplicar a: proyectos» — ya existía, enterrado al pie del
   detalle; faltaba alcanzarlo desde la lista y el Kanban.
"""

from __future__ import annotations

from datetime import date, time
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

TPL_CARD = Path("el-taller/templates/proyectos/_producto_card.html")
TPL_FILAS = Path("el-taller/templates/proyectos/_filas.html")
TPL_KANBAN_COL = Path("el-taller/templates/proyectos/_kanban_columna.html")
TPL_RESULTADOS = Path("el-taller/templates/taller_home/_kanban_resultados_fuera.html")


# ── helpers ──────────────────────────────────────────────────────────────────


def _res(texto: str):
    return SimpleNamespace(texto=texto, provider="anthropic", modelo="claude-sonnet-4-6",
                           costo_usd=0.0, prompt_tokens=1, completion_tokens=1, latencia_ms=1)


def _mock_analizar(monkeypatch, texto: str):
    import lib.analistas as la
    monkeypatch.setattr(la, "analizar", lambda *a, **k: _res(texto))


@pytest.fixture()
def entorno(usuario_factory, cliente_factory, proyecto_factory):
    """Un proyecto con una línea de producto, y su dueño con todos los permisos."""
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin, razon_social="Optimist Marketing")
    proyecto = proyecto_factory(cliente=cli, creado_por=admin, nombre="Gorras Verano")
    cat = CategoriaServicio.objects.create(nombre="Textiles")
    srv = Servicio.objects.create(nombre="Gorra trucker", categoria=cat, precio_base=100)
    linea = ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv, cantidad=30)
    return {"admin": admin, "cliente": cli, "proyecto": proyecto,
            "servicio": srv, "linea": linea}


# ═════════════════════════════════════════════════════════════════════════════
# 1 · La tarea queda LIGADA a la línea de producto
# ═════════════════════════════════════════════════════════════════════════════


def test_la_tarea_dictada_nace_ligada_al_producto(entorno):
    from apps.los_proyectos.tareas_ia import aplicar_tareas
    res = aplicar_tareas(
        proyecto=entorno["proyecto"], usuario=entorno["admin"],
        producto=entorno["linea"],
        tareas=[{"titulo": "Mandar el arte", "fecha": "2026-09-01"}],
    )
    assert res["creadas"] == 1
    from apps.el_pizarron.models import Tarea
    assert Tarea.objects.get(titulo="Mandar el arte").producto_id == entorno["linea"].pk


def test_quitar_la_linea_NO_borra_la_tarea(entorno):
    """`SET_NULL`, no `CASCADE`: el trabajo asignado sobrevive a que alguien
    quite el producto del proyecto. La tarea queda huérfana, no desaparece."""
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.tareas_ia import aplicar_tareas
    aplicar_tareas(proyecto=entorno["proyecto"], usuario=entorno["admin"],
                   producto=entorno["linea"], tareas=[{"titulo": "Bordar"}])
    entorno["linea"].delete()
    t = Tarea.objects.get(titulo="Bordar")
    assert t.pk and t.producto_id is None
    assert t.proyecto_id == entorno["proyecto"].pk


def test_un_producto_de_otro_proyecto_no_se_liga(entorno, proyecto_factory, usuario_factory):
    """El pk del producto viaja por la URL: una tarea no puede colgar de una
    línea que es de otro proyecto."""
    from apps.el_catalogo.models import Servicio
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.models import ProyectoProducto
    from apps.los_proyectos.tareas_ia import aplicar_tareas

    ajeno = proyecto_factory(creado_por=entorno["admin"], nombre="Otro")
    srv2 = Servicio.objects.create(nombre="Playera", categoria=entorno["servicio"].categoria, precio_base=50)
    linea_ajena = ProyectoProducto.objects.create(proyecto=ajeno, servicio=srv2, cantidad=1)
    aplicar_tareas(proyecto=entorno["proyecto"], usuario=entorno["admin"],
                   producto=linea_ajena, tareas=[{"titulo": "Colgada de nadie"}])
    assert Tarea.objects.get(titulo="Colgada de nadie").producto_id is None


# ── La IA entiende hora y lugar ──────────────────────────────────────────────


def test_el_dictado_saca_hora_y_lugar(entorno, monkeypatch):
    """«entregar el martes a las 4 en la bodega de Optimist»."""
    from apps.los_proyectos import tareas_ia
    _mock_analizar(monkeypatch, '''{"tareas": [{"titulo": "Entregar gorras",
        "responsable": "", "fecha": "2026-09-01", "hora": "16:00",
        "lugar": "la bodega de Optimist", "tipo": "entrega", "prioridad": "media",
        "detalle": ""}]}''')
    res = tareas_ia.interpretar_tareas(
        proyecto=entorno["proyecto"], texto="entregar el martes a las 4 en la bodega de Optimist",
        usuario=entorno["admin"], producto=entorno["linea"])
    assert res["ok"]
    t = res["tareas"][0]
    assert t["hora"] == "16:00"
    assert t["lugar"] == "la bodega de Optimist"


def test_la_hora_y_el_lugar_llegan_a_la_tarea(entorno):
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.tareas_ia import aplicar_tareas
    aplicar_tareas(proyecto=entorno["proyecto"], usuario=entorno["admin"],
                   producto=entorno["linea"],
                   tareas=[{"titulo": "Entregar", "fecha": "2026-09-01",
                            "hora": "16:00", "lugar": "Bodega de Optimist"}])
    t = Tarea.objects.get(titulo="Entregar")
    assert t.hora == time(16, 0)
    assert t.destino_etiqueta == "Bodega de Optimist"
    assert t.fecha_compromiso == date(2026, 9, 1)


def test_sin_hora_la_tarea_no_inventa_una(entorno):
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.tareas_ia import aplicar_tareas
    aplicar_tareas(proyecto=entorno["proyecto"], usuario=entorno["admin"],
                   tareas=[{"titulo": "Sin hora", "hora": ""}])
    assert Tarea.objects.get(titulo="Sin hora").hora is None


@pytest.mark.parametrize("basura", ["a las 4", "25:00", "16", None, 4, "16:99"])
def test_una_hora_que_no_se_entiende_queda_vacia(basura):
    from apps.los_proyectos.tareas_ia import _hora
    assert _hora(basura) == ""


# ── El pin NO se inventa ─────────────────────────────────────────────────────


def test_un_lugar_desconocido_no_pone_pin(entorno, monkeypatch):
    """Sin dirección guardada que empate, la tarea guarda sólo la etiqueta. Un
    pin inventado manda a alguien al lugar equivocado."""
    from apps.los_proyectos import tareas_ia
    _mock_analizar(monkeypatch, '''{"tareas": [{"titulo": "Entregar",
        "fecha": "2026-09-01", "lugar": "por allá lejos"}]}''')
    res = tareas_ia.interpretar_tareas(proyecto=entorno["proyecto"], texto="x",
                                       usuario=entorno["admin"])
    t = res["tareas"][0]
    assert t["lugar"] == "por allá lejos"
    assert t["lat"] is None and t["lng"] is None


def test_un_lugar_que_empata_con_una_sede_si_pone_pin(entorno, monkeypatch):
    from apps.checador.models.sede import SedeLC
    SedeLC.objects.create(nombre="Taller Cuajimalpa", lat="19.35", lng="-99.29", activa=True)
    from apps.los_proyectos import tareas_ia
    _mock_analizar(monkeypatch, '''{"tareas": [{"titulo": "Recoger",
        "fecha": "2026-09-01", "lugar": "en el Taller Cuajimalpa"}]}''')
    res = tareas_ia.interpretar_tareas(proyecto=entorno["proyecto"], texto="x",
                                       usuario=entorno["admin"])
    t = res["tareas"][0]
    assert t["lat"] == pytest.approx(19.35)
    assert t["lng"] == pytest.approx(-99.29)


def test_dos_lugares_que_empatan_no_ponen_pin(entorno):
    """Ambiguo ⇒ ningún pin. Es el mismo criterio que el resto de los
    resolvedores del repo: no se adivina."""
    from apps.checador.models.sede import SedeLC
    from apps.los_proyectos.tareas_ia import _resolver_lugar
    SedeLC.objects.create(nombre="Bodega Norte", lat="19.1", lng="-99.1", activa=True)
    SedeLC.objects.create(nombre="Bodega Sur", lat="19.2", lng="-99.2", activa=True)
    assert _resolver_lugar("en la Bodega", entorno["proyecto"]) == (None, None)


def test_una_sede_apagada_no_pone_pin(entorno):
    from apps.checador.models.sede import SedeLC
    from apps.los_proyectos.tareas_ia import _resolver_lugar
    SedeLC.objects.create(nombre="Bodega Vieja", lat="19.1", lng="-99.1", activa=False)
    assert _resolver_lugar("en la Bodega Vieja", entorno["proyecto"]) == (None, None)


def test_un_nombre_muy_corto_no_pone_pin(entorno):
    """«Sur» aparece por casualidad dentro de cualquier frase."""
    from apps.checador.models.sede import SedeLC
    from apps.los_proyectos.tareas_ia import _resolver_lugar
    SedeLC.objects.create(nombre="Sur", lat="19.1", lng="-99.1", activa=True)
    assert _resolver_lugar("entregar en el sur de la ciudad", entorno["proyecto"]) == (None, None)


def test_media_coordenada_no_se_guarda(entorno):
    """Un pin a medias no sirve: o las dos o ninguna (misma regla que
    `TareaForm.clean`)."""
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.tareas_ia import aplicar_tareas
    aplicar_tareas(proyecto=entorno["proyecto"], usuario=entorno["admin"],
                   tareas=[{"titulo": "Media", "lat": 19.1, "lng": None}])
    t = Tarea.objects.get(titulo="Media")
    assert t.destino_lat is None and t.destino_lng is None


# ── Sin responsable, la tarea sigue quedando del despacho ────────────────────


def test_sin_responsable_la_tarea_no_cae_a_quien_dicta(entorno):
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.tareas_ia import aplicar_tareas
    aplicar_tareas(proyecto=entorno["proyecto"], usuario=entorno["admin"],
                   producto=entorno["linea"], tareas=[{"titulo": "De nadie"}])
    assert Tarea.objects.get(titulo="De nadie").asignada_a_id is None


def test_el_preview_ya_no_dice_que_queda_a_tu_nombre():
    """El aviso del modal afirmaba lo contrario de lo que hace el código desde
    el 7 de agosto."""
    tpl = Path("el-taller/templates/proyectos/_modal_tareas_chalan.html").read_text(encoding="utf-8")
    assert "queda a tu nombre" not in tpl
    assert "queda del despacho" in tpl


# ── Las vistas: el producto viaja de ida y vuelta ────────────────────────────


def test_el_modal_del_chalan_se_abre_con_el_producto_puesto(client, entorno):
    client.force_login(entorno["admin"])
    r = client.get(f"/proyectos/{entorno['proyecto'].pk}/tareas-chalan"
                   f"?producto={entorno['linea'].pk}", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    cuerpo = r.content.decode()
    assert f'name="producto" value="{entorno["linea"].pk}"' in cuerpo
    assert "Gorra trucker" in cuerpo


def test_aplicar_desde_el_modal_liga_el_producto(client, entorno, monkeypatch):
    import json

    from apps.el_pizarron.models import Tarea
    client.force_login(entorno["admin"])
    propuestas = json.dumps([{"titulo": "Comprar hilo", "fecha": "2026-09-01"}])
    r = client.post(f"/proyectos/{entorno['proyecto'].pk}/tareas-chalan/aplicar",
                    {"tareas_json": propuestas, "sel": ["0"],
                     "producto": str(entorno["linea"].pk)})
    assert r.status_code == 204
    assert Tarea.objects.get(titulo="Comprar hilo").producto_id == entorno["linea"].pk


def test_el_alta_manual_desde_la_tarjeta_liga_el_producto(client, entorno):
    from apps.el_pizarron.models import Tarea
    client.force_login(entorno["admin"])
    r = client.post(
        f"/proyectos/{entorno['proyecto'].pk}/agregar-tarea",
        {"titulo": "Revisar muestra", "descripcion": "", "estado": "pendiente",
         "prioridad": "media", "tipo": "tarea", "asignada_a": entorno["admin"].pk,
         "fecha_compromiso": "2026-09-01", "producto": str(entorno["linea"].pk)},
        HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert Tarea.objects.get(titulo="Revisar muestra").producto_id == entorno["linea"].pk


def test_dictar_sin_escribir_nada_abre_el_modal_sin_regañar(client, entorno):
    """El botón de la tarjeta postea aunque su campo esté vacío: ahí toca abrir
    el modal para dictar dentro, no soltar una advertencia."""
    client.force_login(entorno["admin"])
    r = client.post(f"/proyectos/{entorno['proyecto'].pk}/tareas-chalan",
                    {"texto": "", "producto": str(entorno["linea"].pk)},
                    HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert "Describe primero las tareas" not in r.content.decode()


# ── La tarjeta lista sus tareas ──────────────────────────────────────────────


def test_la_tarjeta_lista_las_tareas_del_producto(client, entorno):
    from apps.el_pizarron.models import Tarea
    Tarea.objects.create(proyecto=entorno["proyecto"], producto=entorno["linea"],
                         titulo="Cortar la tela", creado_por=entorno["admin"])
    Tarea.objects.create(proyecto=entorno["proyecto"], titulo="Ajena al producto",
                         creado_por=entorno["admin"])
    client.force_login(entorno["admin"])
    cuerpo = client.get(f"/proyectos/{entorno['proyecto'].pk}/").content.decode()
    assert "Tareas de este producto" in cuerpo
    assert "Cortar la tela" in cuerpo


def test_una_tarea_archivada_no_sale_en_la_tarjeta(client, entorno):
    from apps.el_pizarron.models import Tarea
    Tarea.objects.create(proyecto=entorno["proyecto"], producto=entorno["linea"],
                         titulo="Ya archivada", archivada=True, creado_por=entorno["admin"])
    client.force_login(entorno["admin"])
    assert "Ya archivada" not in client.get(
        f"/proyectos/{entorno['proyecto'].pk}/").content.decode()


def test_las_tareas_de_todas_las_tarjetas_salen_en_UNA_consulta(
        client, entorno, django_assert_num_queries):
    """`_anotar_procesos` ya paga un viaje por línea; el bloque de tareas no
    puede sumar otro. Con más productos, el número de consultas de tareas no
    crece (lección de S-Latencia-Ago24)."""
    from apps.el_catalogo.models import Servicio
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.forms import ProyectoProductoFormSetDetalle
    from apps.los_proyectos.views import _anotar_tareas

    for i in range(6):
        srv = Servicio.objects.create(nombre=f"Extra {i}", categoria=entorno["servicio"].categoria, precio_base=10)
        from apps.los_proyectos.models import ProyectoProducto
        linea = ProyectoProducto.objects.create(
            proyecto=entorno["proyecto"], servicio=srv, cantidad=1)
        Tarea.objects.create(proyecto=entorno["proyecto"], producto=linea,
                             titulo=f"T{i}", creado_por=entorno["admin"])

    fs = ProyectoProductoFormSetDetalle(instance=entorno["proyecto"])
    list(fs.forms)  # materializa el queryset del formset antes de medir
    with django_assert_num_queries(1):
        _anotar_tareas(fs)
    assert sum(len(f.tareas) for f in fs.forms) == 6


# ── Las tres trampas de la tarjeta ───────────────────────────────────────────


def test_el_campo_de_dictado_no_viaja_en_el_autoguardado():
    """El bloque vive DENTRO del formulario del proyecto: un campo con `name`
    se posteaba en cada autoguardado. El texto se lee por id con `hx-vals`."""
    src = TPL_CARD.read_text(encoding="utf-8")
    ini = src.index("Tareas de este producto")
    bloque = src[ini:]
    assert 'id="tareas-dictado-' in bloque
    assert 'name="texto"' not in bloque, (
        "El campo de dictado recuperó un `name`: viajaría en cada autoguardado "
        "del proyecto."
    )
    assert "hx-vals='js:{texto: document.getElementById" in bloque


def test_los_controles_del_bloque_no_disparan_el_autoguardado():
    src = TPL_CARD.read_text(encoding="utf-8")
    ini = src.index("Tareas de este producto")
    bloque = src[ini:]
    # Los dos botones (dictar + alta manual) filtran los parámetros para no
    # arrastrar el formset del proyecto, y ninguno es de tipo submit.
    assert bloque.count("hx-params=") >= 2
    assert bloque.count('type="button"') >= 2


def test_una_tarjeta_sin_guardar_lo_dice_en_vez_de_ofrecer_tareas():
    src = TPL_CARD.read_text(encoding="utf-8")
    assert "Guarda el proyecto primero; luego podrás colgarle tareas" in src


def test_el_bloque_solo_existe_donde_hay_autoguardado(client, entorno):
    """En el alta y en la pestaña de una versión no aplica (no hay pk que ligar
    ni autoguardado que lo salve)."""
    client.force_login(entorno["admin"])
    assert "Tareas de este producto" not in client.get("/proyectos/nuevo/").content.decode()


# ═════════════════════════════════════════════════════════════════════════════
# 2 · La búsqueda del Dashboard encuentra clientes, productos y proveedores
# ═════════════════════════════════════════════════════════════════════════════


def test_encuentra_un_cliente_aunque_no_tenga_proyectos(client, entorno, cliente_factory):
    cliente_factory(creado_por=entorno["admin"], razon_social="Zapatería Rulfo")
    client.force_login(entorno["admin"])
    cuerpo = client.get("/buscar/proyectos?q=Rulfo").content.decode()
    assert "Clientes" in cuerpo
    assert "Zapatería Rulfo" in cuerpo


def test_encuentra_un_producto_por_su_alias_en_un_proyecto(client, entorno):
    entorno["linea"].nombre_proyecto = "Gorra Modelo Janet"
    entorno["linea"].save()
    client.force_login(entorno["admin"])
    cuerpo = client.get("/buscar/proyectos?q=Janet").content.decode()
    assert "Gorra trucker" in cuerpo


def test_encuentra_un_proveedor(client, entorno):
    from apps.el_catalogo.models import Proveedor
    Proveedor.objects.create(razon_social="Telas del Norte", activo=True)
    client.force_login(entorno["admin"])
    cuerpo = client.get("/buscar/proyectos?q=Telas").content.decode()
    assert "Proveedores" in cuerpo
    assert "Telas del Norte" in cuerpo


def test_sin_permiso_de_clientes_esa_seccion_NO_aparece(client, entorno, usuario_factory,
                                                        cliente_factory):
    """No un «no puedes»: la sección simplemente no existe. Las otras sí."""
    from cuentas.models.permiso_usuario import PermisoUsuario
    cliente_factory(creado_por=entorno["admin"], razon_social="Zapatería Rulfo")
    from apps.el_catalogo.models import Proveedor
    Proveedor.objects.create(razon_social="Rulfo Insumos", activo=True)

    disenador = usuario_factory(rol="disenador")
    PermisoUsuario.objects.update_or_create(
        usuario=disenador, modulo="cartera", permiso="ver", defaults={"activo": False})
    PermisoUsuario.objects.update_or_create(
        usuario=disenador, modulo="catalogo", permiso="ver_nombres", defaults={"activo": True})
    client.force_login(disenador)
    cuerpo = client.get("/buscar/proyectos?q=Rulfo").content.decode()
    assert "Zapatería Rulfo" not in cuerpo
    assert "Rulfo Insumos" in cuerpo


def test_las_secciones_nuevas_quedan_fuera_del_filtro_instantaneo():
    """Vienen filtradas por el servidor. El filtro del Kanban se salta lo que
    lleve `kanban-columna-fuera` — si las tocara, les reescribiría el contador."""
    tpl = TPL_RESULTADOS.read_text(encoding="utf-8")
    ini = tpl.index("{% for sec in secciones %}")
    assert "kanban-columna-fuera" in tpl[ini:ini + 400]
    js = Path("el-taller/templates/proyectos/_kanban_script.html").read_text(encoding="utf-8")
    assert ".kanban-columna:not(.kanban-columna-fuera)" in js


def test_el_contador_del_tablero_no_lo_mueven_las_secciones(client, entorno):
    """El bloque de proyectos conserva su propio total."""
    client.force_login(entorno["admin"])
    cuerpo = client.get("/buscar/proyectos?q=Optimist").content.decode()
    assert "Proyectos fuera del tablero" in cuerpo


def test_una_busqueda_de_una_letra_no_dispara_nada(client, entorno):
    client.force_login(entorno["admin"])
    cuerpo = client.get("/buscar/proyectos?q=a").content.decode()
    assert "Clientes" not in cuerpo


def test_el_enlace_de_ver_todos_lleva_el_termino(client, entorno, cliente_factory):
    for i in range(10):
        cliente_factory(creado_por=entorno["admin"], razon_social=f"Rulfo {i} S.A.")
    client.force_login(entorno["admin"])
    cuerpo = client.get("/buscar/proyectos?q=Rulfo").content.decode()
    assert "?q=Rulfo" in cuerpo


# ═════════════════════════════════════════════════════════════════════════════
# 3 · Duplicar proyecto, alcanzable
# ═════════════════════════════════════════════════════════════════════════════


def test_la_lista_trae_el_boton_de_duplicar(client, entorno):
    client.force_login(entorno["admin"])
    cuerpo = client.get("/proyectos/").content.decode()
    assert f"/proyectos/{entorno['proyecto'].pk}/duplicar" in cuerpo


def test_la_fila_de_la_lista_ya_no_usa_onclick(client, entorno):
    """Con `onclick` en el <tr>, el botón de duplicar abriría el proyecto además
    de su modal. `data-href` respeta los botones."""
    src = TPL_FILAS.read_text(encoding="utf-8")
    assert "onclick=" not in src
    assert "data-href=" in src


def test_la_tarjeta_del_kanban_ya_no_es_un_enlace():
    """Un <button> dentro de un <a> es HTML inválido."""
    src = TPL_KANBAN_COL.read_text(encoding="utf-8")
    assert '<a href="{% url \'proyectos-detalle\' p.pk %}"' not in src
    assert 'data-href="{% url \'proyectos-detalle\' p.pk %}"' in src


def test_el_kanban_trae_el_boton_de_duplicar(client, entorno):
    client.force_login(entorno["admin"])
    cuerpo = client.get("/proyectos/kanban/").content.decode()
    assert f"/proyectos/{entorno['proyecto'].pk}/duplicar" in cuerpo


def test_sin_permiso_de_crear_no_hay_boton_de_duplicar(client, entorno, usuario_factory):
    """Y sin él, tampoco su columna: una celda sin cabecera descuadra la tabla."""
    from cuentas.models.permiso_usuario import PermisoUsuario
    lector = usuario_factory(rol="disenador")
    for accion, activo in (("ver", True), ("crear", False), ("editar", False)):
        PermisoUsuario.objects.update_or_create(
            usuario=lector, modulo="proyectos", permiso=accion, defaults={"activo": activo})
    client.force_login(lector)
    cuerpo = client.get("/proyectos/").content.decode()
    assert "/duplicar" not in cuerpo


def test_el_boton_de_duplicar_no_navega_al_proyecto():
    """`data-no-row-click` además del filtro por etiqueta: el manejador de
    `ui.js` ya salta los botones, pero la marca lo deja explícito."""
    for tpl in (TPL_FILAS, TPL_KANBAN_COL):
        src = tpl.read_text(encoding="utf-8")
        ini = src.index("proyectos-duplicar")
        assert "data-no-row-click" in src[max(0, ini - 400):ini]


# ═════════════════════════════════════════════════════════════════════════════
# MCP — El Chalán puede preguntar «¿qué tareas tiene este producto?»
# ═════════════════════════════════════════════════════════════════════════════


def test_el_chalan_lee_las_tareas_de_un_producto(entorno):
    from apps.el_pizarron.models import Tarea

    from capacidades import ejecutar
    Tarea.objects.create(proyecto=entorno["proyecto"], producto=entorno["linea"],
                         titulo="Cortar la tela", creado_por=entorno["admin"])
    salida = ejecutar("tareas_de_producto",
                      {"proyecto_slug": entorno["proyecto"].codigo,
                       "producto": "Gorra trucker"},
                      entorno["admin"])
    assert "Cortar la tela" in str(salida)


def test_el_chalan_no_adivina_entre_dos_productos_iguales(entorno):
    from apps.los_proyectos.models import ProyectoProducto

    from capacidades import ejecutar
    ProyectoProducto.objects.create(proyecto=entorno["proyecto"],
                                    servicio=entorno["servicio"], cantidad=5)
    salida = str(ejecutar("tareas_de_producto",
                          {"proyecto_slug": entorno["proyecto"].codigo,
                           "producto": "Gorra trucker"},
                          entorno["admin"]))
    assert "ambiguo" in salida


def test_la_capacidad_esta_declarada_en_el_catalogo_visible():
    from lib.dictado_catalogo import CONSULTAS_CHAT
    assert any("tareas_de_producto" in c["nombre"] for c in CONSULTAS_CHAT)


# ═════════════════════════════════════════════════════════════════════════════
# El candado de `hx-params="none"` + `hx-vals` — descubierto en este sprint
# ═════════════════════════════════════════════════════════════════════════════
#
# htmx mezcla los valores de `hx-vals` en los parámetros **ANTES** de aplicar el
# filtro de `hx-params` (en htmx 2.0.3: `v = ln(j, qn(En(r)))` y después
# `w = dn(v, r)`; con «none», `dn` devuelve un `FormData` vacío). O sea que
# `hx-params="none"` **también se lleva lo que manda `hx-vals`**, y el control
# acaba posteando un cuerpo vacío.
#
# Se descubrió al escribir el botón de dictado de la tarjeta, y resultó que dos
# controles que YA estaban en producción tenían el mismo error: el selector de
# estado de la tabla de Tareas (daba 403 «Estado inválido» en silencio, porque
# `hx-swap="none"` no pinta la respuesta) y el de ligar un gasto a un proveedor.
#
# La forma correcta es nombrar lo que se conserva (`hx-params="estado"`): el
# formset del proyecto sigue sin viajar y el `hx-vals` sobrevive. Un control sin
# `hx-vals` sí puede quedarse en «none» — su pk va en la URL.

def _controles_con_vals_y_params(ruta: Path):
    """Etiquetas de esa plantilla que usan `hx-vals` y `hx-params` a la vez."""
    import re
    src = ruta.read_text(encoding="utf-8")
    return [m.group(0) for m in re.finditer(r"<[a-zA-Z][^>]*>", src, re.S)
            if "hx-vals" in m.group(0) and "hx-params" in m.group(0)]


@pytest.mark.parametrize("ruta", [
    TPL_CARD,
    Path("el-taller/templates/proyectos/_tareas_panel.html"),
    Path("el-taller/templates/proyectos/_proveedores_panel.html"),
])
def test_ningun_control_mezcla_hx_params_none_con_hx_vals(ruta):
    for tag in _controles_con_vals_y_params(ruta):
        assert 'hx-params="none"' not in tag, (
            f"{ruta}: este control manda `hx-vals` y filtra con "
            f'`hx-params="none"`. htmx mezcla los `hx-vals` ANTES de filtrar, '
            f"así que el cuerpo llega VACÍO y el control no hace nada (sin "
            f"error visible si además lleva `hx-swap=\"none\"`). Nombra los "
            f"parámetros a conservar: hx-params=\"estado\".\n\n{tag[:300]}"
        )


def test_el_selector_de_estado_de_tareas_conserva_su_parametro():
    src = Path("el-taller/templates/proyectos/_tareas_panel.html").read_text(encoding="utf-8")
    assert 'hx-params="estado"' in src


def test_el_selector_de_gasto_sin_proveedor_conserva_su_parametro():
    src = Path("el-taller/templates/proyectos/_proveedores_panel.html").read_text(encoding="utf-8")
    assert 'hx-params="proveedor"' in src


def test_el_boton_de_dictado_conserva_texto_y_producto():
    src = TPL_CARD.read_text(encoding="utf-8")
    assert 'hx-params="texto,producto"' in src
