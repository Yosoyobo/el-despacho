"""Deuda cerrada en el Deploy 1 del sprint de pendientes (2026-09-28).

Cuatro cosas que se venían arrastrando, cada una con su candado:

1. **Los «Otros responsables» se perdían.** Las vistas que crean una tarea con
   `form.save(commit=False)` nunca llamaban `form.save_m2m()`: el principal sí
   quedaba, los demás desaparecían en silencio.
2. **`_productos_calc()` se recargaba 18 veces por petición** en el detalle del
   proyecto (cinco consultas cada vez). Ahora se memoiza por instancia, con
   invalidación — el autoguardado escribe y vuelve a leer en la misma petición,
   así que un memo ingenuo serviría dinero viejo.
3. **`puede_ver_catalogo` era un helper muerto** (preguntaba por `catalogo.ver`,
   que no existe). De paso salió que `analisis.ver` no se podía delegar.
4. **El `_emitir_noop` del conftest** tenía una lista fija de módulos que se
   quedó vieja.
"""

from __future__ import annotations

import ast
import collections
import inspect
import json
import re
import sys
import types
from decimal import Decimal
from pathlib import Path

import pytest

# Importado a nivel de módulo A PROPÓSITO: así ya está cargado antes de que el
# fixture autouse corra, que es el caso que la lista vieja no cubría.
from apps.cotizaciones import services as cot_services
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests import conftest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


# ── helpers ──────────────────────────────────────────────────────────────────


def _datos_tarea(asignada, otros, **extra):
    datos = {
        "titulo": extra.pop("titulo", "Revisar muestras"),
        "descripcion": "",
        "estado": "pendiente",
        "prioridad": "media",
        "tipo": "tarea",
        "asignada_a": asignada.pk,
        "fecha_compromiso": "2026-10-01",
        "responsables": [u.pk for u in otros],
    }
    datos.update(extra)
    return datos


def _ids_responsables(tarea) -> set[int]:
    tarea.refresh_from_db()
    return set(tarea.responsables.values_list("pk", flat=True))


@pytest.fixture
def equipo(usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin", email="jefa@sep28.mx")
    ana = usuario_factory(rol="super_admin", email="ana@sep28.mx")
    beto = usuario_factory(rol="super_admin", email="beto@sep28.mx")
    proyecto = proyecto_factory(creado_por=admin, nombre="Gorras Otoño")
    return {"admin": admin, "ana": ana, "beto": beto, "proyecto": proyecto}


# ═════════════════════════════════════════════════════════════════════════════
# 1. Los «Otros responsables» ya no se pierden
# ═════════════════════════════════════════════════════════════════════════════


class TestOtrosResponsablesSeGuardan:
    """Una prueba por vía de alta/edición de tarea. Todas mandan a Ana como
    principal y a Beto y la jefa como «otros»: los tres tienen que quedar."""

    def test_nueva_tarea_del_proyecto(self, client, equipo):
        from apps.el_pizarron.models import Tarea

        client.force_login(equipo["admin"])
        r = client.post(
            f"/proyectos/{equipo['proyecto'].pk}/tareas/nueva",
            _datos_tarea(equipo["ana"], [equipo["beto"], equipo["admin"]]),
        )
        assert r.status_code == 302, r.content[:500]
        t = Tarea.objects.get(titulo="Revisar muestras")
        assert _ids_responsables(t) == {
            equipo["ana"].pk, equipo["beto"].pk, equipo["admin"].pk,
        }

    def test_modal_agregar_tarea_del_proyecto(self, client, equipo):
        from apps.el_pizarron.models import Tarea

        client.force_login(equipo["admin"])
        r = client.post(
            f"/proyectos/{equipo['proyecto'].pk}/agregar-tarea",
            _datos_tarea(equipo["ana"], [equipo["beto"]], titulo="Cortar vinil"),
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 204, r.content[:500]
        t = Tarea.objects.get(titulo="Cortar vinil")
        assert _ids_responsables(t) == {equipo["ana"].pk, equipo["beto"].pk}

    @pytest.mark.parametrize("htmx", [True, False])
    def test_nueva_tarea_global(self, client, equipo, htmx):
        from apps.el_pizarron.models import Tarea

        client.force_login(equipo["admin"])
        datos = _datos_tarea(
            equipo["ana"], [equipo["beto"]], titulo=f"Global {htmx}",
            proyecto=equipo["proyecto"].pk,
        )
        extra = {"HTTP_HX_REQUEST": "true"} if htmx else {}
        r = client.post("/tareas/nueva/", datos, **extra)
        assert r.status_code in (204, 302), r.content[:500]
        t = Tarea.objects.get(titulo=f"Global {htmx}")
        assert _ids_responsables(t) == {equipo["ana"].pk, equipo["beto"].pk}

    def test_el_principal_entra_aunque_no_se_marquen_otros(self, client, equipo):
        """El modal global no pinta «Otros responsables»: aun así el principal
        tiene que quedar en la M2M (la regla del modelo), y sólo `save_m2m`
        lo sincroniza en el camino con `commit=False`."""
        from apps.el_pizarron.models import Tarea

        client.force_login(equipo["admin"])
        datos = _datos_tarea(equipo["ana"], [], titulo="Solo Ana",
                             proyecto=equipo["proyecto"].pk)
        client.post("/tareas/nueva/", datos, HTTP_HX_REQUEST="true")
        assert _ids_responsables(Tarea.objects.get(titulo="Solo Ana")) == {equipo["ana"].pk}

    def test_editar_tarea_conserva_y_quita_otros(self, client, equipo):
        from apps.el_pizarron.models import Tarea

        t = Tarea.objects.create(proyecto=equipo["proyecto"], titulo="Editar",
                                 asignada_a=equipo["ana"])
        client.force_login(equipo["admin"])
        client.post(f"/tareas/{t.pk}/editar",
                    _datos_tarea(equipo["ana"], [equipo["beto"]], titulo="Editar"))
        assert _ids_responsables(t) == {equipo["ana"].pk, equipo["beto"].pk}

        # Desmarcar a Beto lo quita; el principal se queda.
        client.post(f"/tareas/{t.pk}/editar",
                    _datos_tarea(equipo["ana"], [], titulo="Editar"))
        assert _ids_responsables(t) == {equipo["ana"].pk}

    def test_editar_rapido_suma_al_nuevo_principal(self, client, equipo):
        from apps.el_pizarron.models import Tarea

        t = Tarea.objects.create(proyecto=equipo["proyecto"], titulo="Rápida",
                                 asignada_a=equipo["ana"])
        client.force_login(equipo["admin"])
        r = client.post(
            f"/tareas/{t.pk}/editar-rapido",
            {"titulo": "Rápida", "estado": "pendiente", "prioridad": "media",
             "asignada_a": equipo["beto"].pk},
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 204
        assert equipo["beto"].pk in _ids_responsables(t)

    def test_form_commit_false_guarda_todo_al_llamar_save_m2m(self, equipo):
        """El contrato que usan las tres vistas, probado solo."""
        from apps.el_pizarron.forms import TareaForm

        form = TareaForm(_datos_tarea(equipo["ana"], [equipo["beto"]]))
        assert form.is_valid(), form.errors
        tarea = form.save(commit=False)
        tarea.proyecto = equipo["proyecto"]
        tarea.save()
        assert _ids_responsables(tarea) == set()   # aún no: falta save_m2m
        form.save_m2m()
        assert _ids_responsables(tarea) == {equipo["ana"].pk, equipo["beto"].pk}

    def test_las_vistas_que_guardan_con_commit_false_llaman_save_m2m(self):
        """Candado de forma: la siguiente vista que copie el patrón sin la línea
        vuelve a perder responsables sin que nada truene."""
        from apps.el_pizarron import views as pizarron
        from apps.los_proyectos import views as proyectos

        for vista in (pizarron.nueva_tarea_global, pizarron.nueva_tarea,
                      proyectos.agregar_tarea_modal):
            fuente = inspect.getsource(vista)
            assert "save(commit=False)" in fuente
            assert "form.save_m2m()" in fuente, vista.__name__


# ═════════════════════════════════════════════════════════════════════════════
# 2. El dinero del proyecto se lee UNA vez por petición
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def ocho_lineas(usuario_factory, proyecto_factory):
    """Proyecto con 8 líneas, cada una con impresión, proceso de venta y una
    escala: lo que ejercita las cinco tablas que carga `_productos_calc`."""
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    from apps.los_proyectos.models import (
        ProyectoProducto,
        ProyectoProductoEscala,
        ProyectoProductoProceso,
        ProyectoProductoVenta,
    )

    admin = usuario_factory(rol="super_admin", email="dinero@sep28.mx")
    proyecto = proyecto_factory(creado_por=admin, nombre="Playeras Feria")
    cat = CategoriaServicio.objects.create(nombre="Textiles")
    prov = Proveedor.objects.create(razon_social="Maquila Norte", creado_por=admin)
    lineas = []
    for i in range(8):
        srv = Servicio.objects.create(nombre=f"Playera {i}", categoria=cat,
                                      precio_base="100.00", costo="40.00")
        pp = ProyectoProducto.objects.create(proyecto=proyecto, servicio=srv,
                                             cantidad=10, incluir_en_calculo=True,
                                             proveedor=prov)
        ProyectoProductoProceso.objects.create(producto=pp, tipo="impresion",
                                               costo="5.00", proveedor=prov)
        ProyectoProductoVenta.objects.create(producto=pp, descripcion="Ponchado",
                                             cantidad=1, precio_unitario="50.00")
        ProyectoProductoEscala.objects.create(producto=pp, cantidad=20, activa=False)
        lineas.append(pp)
    return {"admin": admin, "proyecto": proyecto, "lineas": lineas, "servicio_cat": cat}


def _sql_crudo_cantidad(proyecto, cantidad: int) -> None:
    """Una escritura que no avisa a nadie: ni signals ni QuerySet."""
    with connection.cursor() as cur:
        cur.execute("UPDATE proyectos_producto SET cantidad = %s WHERE proyecto_id = %s",
                    [cantidad, proyecto.pk])


def _tabla_principal(sql: str) -> str:
    m = re.search(r'FROM "([a-z_0-9]+)"', sql)
    return m.group(1) if m else ""


def _cargas_de_lineas(capturadas) -> int:
    """Las consultas que son la carga de `_productos_calc`: las líneas con su
    producto del catálogo pegado (el `select_related`)."""
    return sum(
        1 for q in capturadas.captured_queries
        if _tabla_principal(q["sql"]) == "proyectos_producto"
        and '"catalogo_servicio"' in q["sql"]
    )


class TestElDineroSeLeeUnaVez:
    def test_el_detalle_carga_las_lineas_una_sola_vez(self, client, ocho_lineas):
        """Antes: 18 cargas de líneas (y 231 consultas en total en este mismo
        escenario). Ahora: una."""
        client.force_login(ocho_lineas["admin"])
        url = f"/proyectos/{ocho_lineas['proyecto'].pk}/"
        client.get(url)  # calienta cachés que no dependen del memo
        with CaptureQueriesContext(connection) as capturadas:
            r = client.get(url)
        assert r.status_code == 200
        assert _cargas_de_lineas(capturadas) == 1, (
            f"{_cargas_de_lineas(capturadas)} cargas de líneas en un solo GET: "
            "el memo de `_productos_calc` dejó de funcionar"
        )
        por_tabla = collections.Counter(
            _tabla_principal(q["sql"]) for q in capturadas.captured_queries)
        # La carga del memo + el queryset del formset. Antes eran 18.
        assert por_tabla["proyectos_producto"] <= 2, por_tabla

    def test_leer_todo_el_dinero_cuesta_una_carga(self, ocho_lineas):
        from apps.los_proyectos.models import Proyecto

        p = Proyecto.objects.get(pk=ocho_lineas["proyecto"].pk)
        with CaptureQueriesContext(connection) as capturadas:
            for _ in range(3):
                _ = (p.monto_calculado, p.costo_produccion, p.desglose_fiscal,
                     p.margen_porcentaje, p.utilidad_productos, p.merma_total,
                     p.deuda_por_proveedor(), p.gastos_operativos_total)
        assert _cargas_de_lineas(capturadas) == 1

    def test_la_lista_que_devuelve_es_una_copia(self, ocho_lineas):
        """Quien recorte o reordene la lista no descompone el memo de los demás."""
        p = ocho_lineas["proyecto"]
        primera = p._productos_calc()
        primera.clear()
        assert len(p._productos_calc()) == 8


class TestElMemoNoSirveDineroViejo:
    def test_guardar_una_linea_desde_otra_instancia_se_nota(self, ocho_lineas):
        from apps.los_proyectos.models import Proyecto, ProyectoProducto

        p = Proyecto.objects.get(pk=ocho_lineas["proyecto"].pk)
        antes = p.monto_calculado  # llena el memo
        linea = ProyectoProducto.objects.get(pk=ocho_lineas["lineas"][0].pk)
        linea.cantidad = 20        # +10 piezas × $100
        linea.save()
        assert p.monto_calculado == antes + Decimal("1000.00")

    def test_una_linea_nueva_se_nota(self, ocho_lineas):
        from apps.los_proyectos.models import Proyecto, ProyectoProducto

        p = Proyecto.objects.get(pk=ocho_lineas["proyecto"].pk)
        antes = p.monto_calculado
        ProyectoProducto.objects.create(
            proyecto=p, servicio=ocho_lineas["lineas"][0].servicio,
            cantidad=1, incluir_en_calculo=True,
        )
        assert p.monto_calculado == antes + Decimal("100.00")

    def test_un_proceso_de_venta_nuevo_se_nota(self, ocho_lineas):
        from apps.los_proyectos.models import Proyecto, ProyectoProductoVenta

        p = Proyecto.objects.get(pk=ocho_lineas["proyecto"].pk)
        antes = p.monto_calculado
        ProyectoProductoVenta.objects.create(
            producto=ocho_lineas["lineas"][1], descripcion="Arte",
            cantidad=1, precio_unitario="300.00",
        )
        assert p.monto_calculado == antes + Decimal("300.00")

    def test_recalcular_no_escribe_desde_el_memo(self, ocho_lineas):
        """El tercer seguro, solo: con una escritura que no avisa a nadie (SQL
        crudo), `recalcular_monto_estimado` tiene que leer la base y no el memo
        — si no, guardaría en la base el monto de antes."""
        from apps.los_proyectos.models import Proyecto

        p = Proyecto.objects.get(pk=ocho_lineas["proyecto"].pk)
        _ = p.monto_calculado
        _sql_crudo_cantidad(p, 20)
        p.recalcular_monto_estimado()
        # 8 líneas × 20 × $100 + 8 procesos de venta × $50.
        assert Proyecto.objects.get(pk=p.pk).monto_estimado == Decimal("16400.00")

    def test_refresh_from_db_olvida_el_memo(self, ocho_lineas):
        from apps.los_proyectos.models import Proyecto

        p = Proyecto.objects.get(pk=ocho_lineas["proyecto"].pk)
        _ = p.monto_calculado
        _sql_crudo_cantidad(p, 20)
        p.refresh_from_db()
        assert p.monto_calculado == Decimal("16400.00")

    def test_activar_una_escala_se_nota(self, ocho_lineas):
        from apps.los_proyectos.models import Proyecto
        from apps.los_proyectos.services_procesos import sincronizar_escalas

        p = Proyecto.objects.get(pk=ocho_lineas["proyecto"].pk)
        antes = p.monto_calculado
        linea = ocho_lineas["lineas"][0]
        sincronizar_escalas(linea, json.dumps([{"cantidad": 20, "activa": True}]))
        # La Opción B manda: 20 piezas en vez de 10, al mismo precio.
        assert p.monto_calculado == antes + Decimal("1000.00")

    @pytest.mark.parametrize("como", [
        "update", "update_relacionado", "bulk_update", "escala_relacionada",
    ])
    def test_escribir_sin_signals_tambien_invalida(self, ocho_lineas, como):
        """`update()` y `bulk_update()` se saltan los signals; las tablas de las
        líneas usan un QuerySet que invalida igual — también desde un related
        manager, que es como se mueven las escalas (`pp.escalas.update(...)`)."""
        from apps.los_proyectos.models import Proyecto, ProyectoProducto

        p = Proyecto.objects.get(pk=ocho_lineas["proyecto"].pk)
        antes = p.monto_calculado            # llena el memo
        linea = ocho_lineas["lineas"][0]
        if como == "update":
            ProyectoProducto.objects.filter(pk=linea.pk).update(cantidad=20)
        elif como == "update_relacionado":
            p.productos.filter(pk=linea.pk).update(cantidad=20)
        elif como == "bulk_update":
            linea.cantidad = 20
            ProyectoProducto.objects.bulk_update([linea], ["cantidad"])
        else:  # la Opción B pasa a mandar: 20 piezas en vez de 10
            linea.escalas.update(activa=True)
        assert p.monto_calculado == antes + Decimal("1000.00")

    def test_el_autoguardado_devuelve_los_montos_nuevos(
        self, client, ocho_lineas, monkeypatch,
    ):
        """El caso que un memo ingenuo rompería: la vista lee el dinero, el
        autoguardado escribe, y el panel que devuelve tiene que salir con el
        monto NUEVO. Se fuerza el peor caso: el memo ya estaba lleno antes de
        guardar."""
        from apps.los_proyectos import views
        from apps.los_proyectos.models import Proyecto

        from cuentas.templatetags.forms_helpers import dinero

        real = views.get_object_or_404

        def _con_memo_lleno(*args, **kwargs):
            obj = real(*args, **kwargs)
            if isinstance(obj, Proyecto):
                _ = obj.monto_calculado
            return obj

        monkeypatch.setattr(views, "get_object_or_404", _con_memo_lleno)

        p = ocho_lineas["proyecto"]
        lineas = ocho_lineas["lineas"]
        datos = {
            "nombre": p.nombre, "cliente": p.cliente_id, "estado": p.estado,
            "descripcion": "",
            "productos-TOTAL_FORMS": str(len(lineas)),
            "productos-INITIAL_FORMS": str(len(lineas)),
            "productos-MIN_NUM_FORMS": "0", "productos-MAX_NUM_FORMS": "1000",
        }
        for i, pp in enumerate(lineas):
            datos.update({
                f"productos-{i}-id": pp.pk,
                f"productos-{i}-servicio": pp.servicio_id,
                f"productos-{i}-proveedor": pp.proveedor_id,
                f"productos-{i}-cantidad": "20" if i == 0 else "10",
                f"productos-{i}-merma": "0",
                f"productos-{i}-precio_unitario": "",
                f"productos-{i}-costo_unitario": "",
                f"productos-{i}-nota": "",
                f"productos-{i}-incluir_en_calculo": "on",
                f"productos-{i}-visible_pdf": "on",
                # La página siempre manda los procesos de venta; sin ellos el
                # autoguardado los borraría (vacío = «ya no hay ninguno»).
                f"productos-{i}-ventas_json": json.dumps(
                    [{"descripcion": "Ponchado", "cantidad": 1, "precio": "50.00"}]),
            })
        client.force_login(ocho_lineas["admin"])
        r = client.post(f"/proyectos/{p.pk}/", datos, HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        html = r.content.decode()
        assert 'id="autosave-error-detalle"' in html
        # Siete líneas de 10 × $100 + la primera con 20 = 9,000, más 8 procesos
        # de venta × $50 = 9,400. Antes de guardar eran 8,400.
        nuevo = dinero(Decimal("9400.00"))
        viejo = dinero(Decimal("8400.00"))
        assert nuevo in html, "el panel no trae el monto nuevo"
        assert viejo not in html, "el panel trae el monto de ANTES de guardar"
        assert Proyecto.objects.get(pk=p.pk).monto_estimado == Decimal("9400.00")


# ═════════════════════════════════════════════════════════════════════════════
# 3. `puede_ver_catalogo` y el catálogo de permisos
# ═════════════════════════════════════════════════════════════════════════════


class TestPermisosDelCatalogo:
    def test_puede_ver_catalogo_pregunta_por_ver_nombres(self, usuario_factory):
        from cuentas.models.permiso_usuario import PermisoUsuario
        from lib.permisos import invalidar_cache_permisos, puede_ver_catalogo

        jefa = usuario_factory(rol="super_admin", email="cat1@sep28.mx")
        assert puede_ver_catalogo(jefa) is True

        nadie = usuario_factory(rol="miembro", email="cat2@sep28.mx")
        assert puede_ver_catalogo(nadie) is False
        PermisoUsuario.objects.create(usuario=nadie, modulo="catalogo",
                                      permiso="ver_nombres", activo=True)
        invalidar_cache_permisos()
        nadie = type(nadie).objects.get(pk=nadie.pk)
        assert puede_ver_catalogo(nadie) is True

    def test_cada_puede_literal_de_permisos_existe_en_el_catalogo(self):
        """El candado que habría cazado el helper muerto: un
        `puede(u, "modulo", "accion")` con una acción que no existe devuelve
        False para todos, super_admin incluido, y no truena."""
        from lib.permisos_defaults import CATALOGO_PERMISOS

        fuente = Path("lib/permisos.py").read_text(encoding="utf-8")
        muertos = []
        for nodo in ast.walk(ast.parse(fuente)):
            if not (isinstance(nodo, ast.Call)
                    and getattr(nodo.func, "id", None) == "puede"
                    and len(nodo.args) >= 3):
                continue
            modulo, accion = nodo.args[1], nodo.args[2]
            if (isinstance(modulo, ast.Constant) and isinstance(accion, ast.Constant)
                    and accion.value not in CATALOGO_PERMISOS.get(modulo.value, [])):
                muertos.append(f"{modulo.value}.{accion.value} (línea {nodo.lineno})")
        assert not muertos, f"permisos que no existen en el catálogo: {muertos}"

    def test_todo_lo_que_se_siembra_por_rol_se_puede_delegar(self):
        """`DEFAULTS_POR_ROL` sin su renglón en `CATALOGO_PERMISOS` es un permiso
        que no sale en El Directorio: nadie más que el rol sembrado lo tiene. Le
        pasó a `analisis.ver`."""
        from lib.permisos_defaults import CATALOGO_PERMISOS, DEFAULTS_POR_ROL

        faltan = sorted(
            f"{rol}: {modulo}.{accion}"
            for rol, modulos in DEFAULTS_POR_ROL.items()
            for modulo, acciones in modulos.items()
            for accion in acciones
            if accion not in CATALOGO_PERMISOS.get(modulo, [])
        )
        assert not faltan, faltan


# ═════════════════════════════════════════════════════════════════════════════
# 4. El `emitir` de mentiras del conftest
# ═════════════════════════════════════════════════════════════════════════════


_SINTETICO = "despacho_modulo_sintetico_sep28"


class TestEmitirDeMentiras:
    @pytest.mark.skipif(conftest.REDIS_OK, reason="con Redis el fixture no parcha nada")
    def test_un_modulo_fuera_de_la_lista_vieja_ya_llega_neutralizado(self):
        from lib.portavoz_eventos import EventoPortavoz

        assert cot_services.emitir is conftest._emitir_de_mentiras
        # Con la lista vieja, esto reventaba con PortavozError sin Redis.
        cot_services.emitir(EventoPortavoz(
            tipo="cotizacion.creada", actor_id=None, actor_email=None, payload={},
        ))

    def test_neutraliza_en_el_origen_y_en_los_modulos_cargados(self, monkeypatch):
        from lib import portavoz

        monkeypatch.undo()          # el mundo real, sin el fixture autouse
        real = portavoz.emitir
        mp = pytest.MonkeyPatch()
        devolver = conftest._neutralizar_emitir(mp)
        try:
            assert portavoz.emitir is conftest._emitir_de_mentiras
            assert cot_services.emitir is conftest._emitir_de_mentiras
        finally:
            devolver()
            mp.undo()
        assert portavoz.emitir is real
        assert cot_services.emitir is real

    def test_no_toca_los_modulos_de_pruebas(self, monkeypatch):
        """Un módulo de pruebas que importa el `emitir` real para probarlo tiene
        que recibir el real."""
        from lib import portavoz

        monkeypatch.undo()
        real = portavoz.emitir
        modulo = types.ModuleType("tests.falso_sep28")
        modulo.emitir = real
        sys.modules[modulo.__name__] = modulo
        mp = pytest.MonkeyPatch()
        try:
            devolver = conftest._neutralizar_emitir(mp)
            assert modulo.emitir is real
            devolver()
        finally:
            mp.undo()
            sys.modules.pop(modulo.__name__, None)

    def test_lo_importado_a_media_prueba_recupera_el_real(self, monkeypatch):
        """Sin la devolución, un módulo importado mientras el origen estaba
        parchado se quedaba con el de mentiras PARA SIEMPRE."""
        from lib import portavoz

        monkeypatch.undo()
        real = portavoz.emitir
        mp = pytest.MonkeyPatch()
        try:
            devolver = conftest._neutralizar_emitir(mp)
            modulo = types.ModuleType(_SINTETICO)
            exec("from lib.portavoz import emitir", modulo.__dict__)  # noqa: S102
            sys.modules[_SINTETICO] = modulo
            assert modulo.emitir is conftest._emitir_de_mentiras
            devolver()
            mp.undo()
            assert modulo.emitir is real
        finally:
            mp.undo()
            sys.modules.pop(_SINTETICO, None)
