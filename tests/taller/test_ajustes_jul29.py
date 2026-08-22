"""LC 2026-07-29 — ronda de ajustes de Oscar (PDF, página del proyecto, móvil,
calendario y Dashboard).

Cubre lo que se puede fijar sin un navegador: la foto que gana en el documento,
la geometría del PDF (envoltorio único, notas atómicas, estimador calibrado), el
mini-Chalán de tareas, el lugar opcional, el widget del Dashboard y las cuatro
secciones del resumen del calendario.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def _drive_falso(monkeypatch):
    """Nada de disco ni de Drive: el documento se arma con el HTML local."""
    monkeypatch.setattr("lib.almacen.proporcion", lambda *_a, **_k: 0.0)


def _servicio(nombre="Playera dry fit", **kw):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(
        nombre="Producción", defaults={"orden": 10})
    return Servicio.objects.create(
        nombre=nombre, categoria=cat, precio_base=Decimal("210.00"), **kw)


def _con_nombre(usuario, nombre):
    """El factory de usuarios no acepta `nombre_completo`; se fija aquí."""
    usuario.nombre_completo = nombre
    usuario.save(update_fields=["nombre_completo"])
    return usuario


def _cot(proyecto, actor):
    from apps.cotizaciones.models import Cotizacion
    return Cotizacion.objects.create(
        cliente=proyecto.cliente, proyecto=proyecto, titulo=proyecto.nombre,
        estado="borrador", version=1, creado_por=actor)


# ── PDF (1): la foto del alias gana sobre la del producto padre ─────────────

class TestFotoDelAlias:
    """Dos líneas del MISMO producto con alias distintos: cada una debe salir con
    SU foto. Antes la llave por producto ganaba y las dos heredaban la primera —
    de ahí «se sigue poniendo la imagen del producto padre»."""

    def test_dos_alias_del_mismo_producto_llevan_cada_uno_su_foto(
            self, proyecto_factory, usuario_factory):
        from apps.cotizaciones.models import CotizacionItem
        from apps.cotizaciones.services import _foto_del_item, _fotos_vivas_del_proyecto
        from apps.los_proyectos.models import ProyectoProducto

        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Playeras LCC")
        srv = _servicio(imagen_file_id="FOTO-CATALOGO")
        ProyectoProducto.objects.create(
            proyecto=proyecto, servicio=srv, cantidad=16, orden=1,
            nombre_proyecto="Playera dry fit — negro", imagen_file_id="FOTO-NEGRO")
        ProyectoProducto.objects.create(
            proyecto=proyecto, servicio=srv, cantidad=16, orden=2,
            nombre_proyecto="Polo dry fit — blanco", imagen_file_id="FOTO-BLANCO")

        cot = _cot(proyecto, admin)
        negro = CotizacionItem.objects.create(
            cotizacion=cot, servicio=srv, concepto="Playera dry fit — negro",
            cantidad=16, precio_unitario=Decimal("210"), imagen_file_id="FOTO-CATALOGO")
        blanco = CotizacionItem.objects.create(
            cotizacion=cot, servicio=srv, concepto="Polo dry fit — blanco",
            cantidad=16, precio_unitario=Decimal("295"), imagen_file_id="FOTO-CATALOGO")

        vivas = _fotos_vivas_del_proyecto(cot)
        assert _foto_del_item(negro, vivas) == "FOTO-NEGRO"
        assert _foto_del_item(blanco, vivas) == "FOTO-BLANCO"

    def test_la_llave_por_producto_no_contagia_a_la_linea_sin_alias(
            self, proyecto_factory, usuario_factory):
        """Si un producto se usa dos veces y sólo una tiene foto propia, la otra
        NO hereda esa foto: se queda con la del catálogo."""
        from apps.cotizaciones.models import CotizacionItem
        from apps.cotizaciones.services import _foto_del_item, _fotos_vivas_del_proyecto
        from apps.los_proyectos.models import ProyectoProducto

        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Playeras LCC")
        srv = _servicio(imagen_file_id="FOTO-CATALOGO")
        ProyectoProducto.objects.create(
            proyecto=proyecto, servicio=srv, cantidad=10, orden=1,
            nombre_proyecto="Con bordado", imagen_file_id="FOTO-BORDADO")
        ProyectoProducto.objects.create(
            proyecto=proyecto, servicio=srv, cantidad=10, orden=2)

        cot = _cot(proyecto, admin)
        sin_alias = CotizacionItem.objects.create(
            cotizacion=cot, servicio=srv, concepto=srv.nombre,
            cantidad=10, precio_unitario=Decimal("210"), imagen_file_id="FOTO-CATALOGO")

        vivas = _fotos_vivas_del_proyecto(cot)
        assert _foto_del_item(sin_alias, vivas) == "FOTO-CATALOGO"

    def test_un_solo_uso_sigue_casando_por_producto(
            self, proyecto_factory, usuario_factory):
        """Sin ambigüedad, la llave por producto sigue sirviendo: cubre el caso en
        que el concepto se renombró a mano en la cotización."""
        from apps.cotizaciones.models import CotizacionItem
        from apps.cotizaciones.services import _foto_del_item, _fotos_vivas_del_proyecto
        from apps.los_proyectos.models import ProyectoProducto

        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Gorras")
        srv = _servicio(nombre="Gorra gabardina")
        ProyectoProducto.objects.create(
            proyecto=proyecto, servicio=srv, cantidad=30, orden=1,
            nombre_proyecto="Gorra Paris Texas", imagen_file_id="FOTO-GORRA")

        cot = _cot(proyecto, admin)
        item = CotizacionItem.objects.create(
            cotizacion=cot, servicio=srv, concepto="Otro nombre a mano",
            cantidad=30, precio_unitario=Decimal("160"))

        vivas = _fotos_vivas_del_proyecto(cot)
        assert _foto_del_item(item, vivas) == "FOTO-GORRA"


# ── PDF (2) y (3): geometría del documento ─────────────────────────────────

class TestGeometriaDelDocumento:

    @pytest.fixture
    def cot_con_dos_bloques(self, proyecto_factory, usuario_factory):
        from apps.cotizaciones.models import CotizacionItem
        admin = usuario_factory(rol="super_admin")
        cot = _cot(proyecto_factory(nombre="Playeras Dry Fit LCC"), admin)
        for nombre, precio in (("Playera dry fit — negro", "210"),
                               ("Polo dry fit — blanco", "295")):
            CotizacionItem.objects.create(
                cotizacion=cot, concepto=nombre, descripcion="16 pz\nColor",
                cantidad=16, precio_unitario=Decimal(precio))
        return cot

    def test_los_bloques_van_en_UNA_sola_tabla_envoltorio(
            self, cot_con_dos_bloques, _drive_falso):
        """Dos tablas seguidas dejan el espacio que Docs mete entre tablas (quirk
        #5) — el hueco «entre los elementos 1 y 2» que reportó Oscar. Con una
        tabla y una fila por bloque, ese espacio no existe."""
        from apps.cotizaciones import services
        html = services.construir_html_pdf(cot_con_dos_bloques)
        # Una sola apertura de envoltorio, dos filas (una por bloque).
        assert html.count('<td style="border:none; padding:0; vertical-align:top;">') >= 2

    def test_ya_no_se_inyecta_aire_calculado_a_mano(
            self, cot_con_dos_bloques, _drive_falso):
        from apps.cotizaciones import services
        html = services.construir_html_pdf(cot_con_dos_bloques)
        assert "aire_arriba" not in html
        assert "<br><br>" not in html

    def test_las_notas_van_dentro_del_envoltorio_atomico(
            self, cot_con_dos_bloques, _drive_falso):
        """Oscar: «se compaginó el bloque de notas». Van en la misma primitiva que
        los bloques (fila de tabla con `preventOverflow`) para que no se partan, y
        el hueco que las empuja al pie va DENTRO de la celda para que viaje con
        ellas."""
        import re

        from apps.cotizaciones import services
        html = services.construir_html_pdf(cot_con_dos_bloques)
        antes = html.split("Notas:")[0]
        # Lo último que se abre antes de las notas es: envoltorio → celda → hueco.
        cola = antes[-400:]
        assert re.search(
            r'<table[^>]*>\s*<tr><td style="border:none; padding:0; vertical-align:top;">\s*'
            r'<div style="margin-top:\d+pt;">\s*<p [^>]*>$',
            cola.rstrip()), cola
        # El hueco es un número real (la plantilla no dejó la variable sin sustituir).
        assert "{{" not in html

    def test_el_estimador_cuenta_el_overhead_del_convertidor(self):
        """Se quedaba ~60pt corto por bloque (medido en dos documentos reales), y
        con 6 bloques ese error acumulado disparaba el hueco de las notas."""
        from apps.cotizaciones.services import _OVERHEAD_BLOQUE_PT, _alto_bloque

        class _It:
            detalle_lineas = []
        fila = {"it": _It(), "imagen": "", "extras": []}
        assert _alto_bloque(fila) >= _OVERHEAD_BLOQUE_PT
        assert _OVERHEAD_BLOQUE_PT > 0

    def test_el_hueco_de_las_notas_tiene_tope(self, cot_con_dos_bloques):
        """Un error de estimación no puede abrir medio hoja de agujero ni empujar
        el documento a una página de más (la página 4 vacía de Dekalogo)."""
        from apps.cotizaciones.services import (
            _TOPE_HUECO_NOTAS_PT,
            _espacio_antes_de_notas,
        )
        # Documento vacío = el máximo hueco posible.
        assert _espacio_antes_de_notas(cot_con_dos_bloques, [], [], ["n"]) <= _TOPE_HUECO_NOTAS_PT


class TestPreventOverflowAnidado:
    """`_peticiones_prevent_overflow` tiene que entrar a las tablas ANIDADAS: los
    bloques del documento viven en celdas del envoltorio."""

    def test_recorre_las_tablas_hijas(self):
        from lib.google_drive import _peticiones_prevent_overflow
        cuerpo = [{
            "startIndex": 10,
            "table": {
                "rows": 1,
                "tableRows": [{
                    "tableCells": [{
                        "content": [{"startIndex": 20, "table": {"rows": 3}}],
                    }],
                }],
            },
        }]
        peticiones = _peticiones_prevent_overflow(cuerpo)
        indices = {p["updateTableRowStyle"]["tableStartLocation"]["index"] for p in peticiones}
        assert indices == {10, 20}
        for p in peticiones:
            assert p["updateTableRowStyle"]["tableRowStyle"] == {"preventOverflow": True}

    def test_tolera_basura(self):
        from lib.google_drive import _peticiones_prevent_overflow
        assert _peticiones_prevent_overflow(None) == []
        assert _peticiones_prevent_overflow([{"paragraph": {}}, "basura", {"table": {}}]) == []


# ── Proyecto: Facturas ligadas con monto y fecha ────────────────────────────

def test_facturas_ligadas_muestran_monto_y_fecha(
        client, proyecto_factory, usuario_factory):
    from apps.facturacion.models import Factura, FacturaItem

    admin = usuario_factory(rol="super_admin")
    proyecto = proyecto_factory(nombre="Playeras LCC")
    fac = Factura.objects.create(
        cliente=proyecto.cliente, proyecto=proyecto, concepto="Producción",
        fecha_emision=date(2026, 7, 20), regimen_fiscal="exento", creado_por=admin)
    FacturaItem.objects.create(
        factura=fac, descripcion="Producción", cantidad=1,
        precio_unitario=Decimal("3360.00"))

    client.force_login(admin)
    html = client.get(f"/proyectos/{proyecto.pk}/").content.decode()
    assert "Facturas ligadas" in html
    assert "20/07/2026" in html
    assert "3,360" in html


# ── Móvil: el orden del detalle sobrevive al autoguardado ──────────────────

def test_el_orden_de_movil_sobrevive_al_swap_por_oob(
        client, proyecto_factory, usuario_factory):
    """El autoguardado reemplaza el `<section>` del panel Económico por OOB. Si esa
    respuesta no trae el `order-*`, el panel salta de lugar en móvil tras cada
    guardado — así que la clase tiene que ir también en `_guardado_oob.html`."""
    admin = usuario_factory(rol="super_admin")
    proyecto = proyecto_factory(nombre="Playeras LCC")
    client.force_login(admin)

    html = client.get(f"/proyectos/{proyecto.pk}/").content.decode()
    assert 'id="economico-panel"' in html and "order-2" in html

    r = client.post(f"/proyectos/{proyecto.pk}/",
                    {"nombre": "Playeras LCC", "cliente": proyecto.cliente_id,
                     "estado": proyecto.estado,
                     "productos-TOTAL_FORMS": "0", "productos-INITIAL_FORMS": "0",
                     "productos-MIN_NUM_FORMS": "0", "productos-MAX_NUM_FORMS": "50"},
                    HTTP_HX_REQUEST="true")
    cuerpo = r.content.decode()
    assert 'hx-swap-oob="true"' in cuerpo
    assert "order-2" in cuerpo, "el panel Económico perdió su posición de móvil"


# ── Proyecto: mini-Chalán de tareas ────────────────────────────────────────

class TestTareasChalan:

    def test_el_boton_aparece_en_el_panel_de_tareas(
            self, client, proyecto_factory, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Playeras LCC")
        client.force_login(admin)
        html = client.get(f"/proyectos/{proyecto.pk}/").content.decode()
        assert "Dictar tareas" in html
        assert f"/proyectos/{proyecto.pk}/tareas-chalan" in html

    def test_el_modal_manual_ya_no_trae_el_widget_de_ia(
            self, client, proyecto_factory, usuario_factory):
        """Oscar: «podemos quitar el chalán de adentro de este modal». El 🤖 de la
        descripción se fue; El Chalán vive en su propio botón al lado."""
        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Playeras LCC")
        client.force_login(admin)
        html = client.get(f"/proyectos/{proyecto.pk}/agregar-tarea",
                          HTTP_HX_REQUEST="true").content.decode()
        assert "Nueva tarea" in html
        assert "data-ia-redactar" not in html
        assert "data-ia-instruccion" not in html

    def test_get_abre_el_textarea(self, client, proyecto_factory, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Playeras LCC")
        client.force_login(admin)
        r = client.get(f"/proyectos/{proyecto.pk}/tareas-chalan", HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert 'name="texto"' in r.content.decode()

    def test_post_propone_pero_no_crea(
            self, client, proyecto_factory, usuario_factory, monkeypatch):
        """Regla §20: El Chalán propone, el humano confirma."""
        from apps.el_pizarron.models import Tarea
        from apps.los_proyectos import tareas_ia

        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Playeras LCC")
        monkeypatch.setattr(tareas_ia, "interpretar_tareas", lambda **_k: {
            "ok": True, "error": "", "tareas": [{
                "titulo": "Mandar el arte al cliente", "asignada_id": None,
                "asignada_nombre": "", "fecha": "2026-08-03",
                "tipo": "tarea", "prioridad": "media", "detalle": "",
            }],
        })
        client.force_login(admin)
        r = client.post(f"/proyectos/{proyecto.pk}/tareas-chalan",
                        {"texto": "el lunes mandar el arte"}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert "Mandar el arte al cliente" in r.content.decode()
        assert not Tarea.objects.filter(proyecto=proyecto).exists()

    def test_aplicar_crea_solo_las_seleccionadas(
            self, client, proyecto_factory, usuario_factory):
        import json

        from apps.el_pizarron.models import Tarea

        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Playeras LCC")
        propuestas = [
            {"titulo": "Sí va", "asignada_id": None, "fecha": "2026-08-03",
             "tipo": "tarea", "prioridad": "media", "detalle": ""},
            {"titulo": "No va", "asignada_id": None, "fecha": "2026-08-04",
             "tipo": "tarea", "prioridad": "media", "detalle": ""},
        ]
        client.force_login(admin)
        r = client.post(
            f"/proyectos/{proyecto.pk}/tareas-chalan/aplicar",
            {"tareas_json": json.dumps(propuestas), "sel": ["0"]},
            HTTP_HX_REQUEST="true")
        assert r.status_code == 204
        assert r["HX-Redirect"].endswith(f"/proyectos/{proyecto.pk}/")
        titulos = set(Tarea.objects.filter(proyecto=proyecto).values_list("titulo", flat=True))
        assert titulos == {"Sí va"}

    def test_sin_responsable_queda_general_del_despacho(
            self, proyecto_factory, usuario_factory):
        """LC 2026-08-07 (Oscar): «no debe de asignar a nadie si no se lo digo».

        Antes caía a quien dictaba, y terminaba con tareas ajenas colgadas de su
        nombre. Ahora se queda sin responsable. Ver test_ajustes_ago07.py.
        """
        from apps.los_proyectos import tareas_ia
        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Playeras LCC")
        res = tareas_ia.aplicar_tareas(
            proyecto=proyecto, usuario=admin,
            tareas=[{"titulo": "Sin dueño", "fecha": "2026-08-03"}])
        assert res["creadas"] == 1
        from apps.el_pizarron.models import Tarea
        assert Tarea.objects.get(titulo="Sin dueño").asignada_a_id is None

    def test_interpretar_sin_texto_no_llama_a_la_ia(self, proyecto_factory):
        from apps.los_proyectos import tareas_ia
        res = tareas_ia.interpretar_tareas(
            proyecto=proyecto_factory(nombre="X"), texto="  ", usuario=None)
        assert res["ok"] is False and res["tareas"] == []

    def test_resolver_persona_no_adivina_si_hay_dos(self, usuario_factory):
        from apps.los_proyectos.tareas_ia import _resolver_persona
        a = _con_nombre(usuario_factory(email="k1@x.mx"), "Karla Pérez")
        b = _con_nombre(usuario_factory(email="k2@x.mx"), "Karla Gómez")
        assert _resolver_persona("Karla", [a, b]) is None
        assert _resolver_persona("Karla Pérez", [a, b]) == a


# ── General (1): el lugar de la tarea es opcional ──────────────────────────

def test_el_lugar_de_una_entrega_ya_no_es_obligatorio(proyecto_factory, usuario_factory):
    """Oscar: «lo más importante es qué, quién y cuándo»."""
    from apps.el_pizarron.forms import TareaGlobalForm

    proyecto = proyecto_factory(nombre="Playeras LCC")
    persona = usuario_factory(email="alguien@x.mx")
    form = TareaGlobalForm(data={
        "proyecto": proyecto.pk, "titulo": "Entregar gorras",
        "asignada_a": persona.pk, "fecha_compromiso": "2026-08-03",
        "tipo": "entrega", "destino_etiqueta": "",
    })
    assert form.is_valid(), form.errors.as_json()


# ── Dashboard: «Tareas pendientes» de todos ────────────────────────────────

def test_el_dashboard_muestra_las_tareas_de_todos(
        client, proyecto_factory, usuario_factory):
    from apps.el_pizarron.models import Tarea

    admin = usuario_factory(rol="super_admin")
    otro = _con_nombre(usuario_factory(email="otro@x.mx"), "Otro Del Equipo")
    proyecto = proyecto_factory(nombre="Playeras LCC")
    Tarea.objects.create(proyecto=proyecto, titulo="Tarea de alguien más",
                         asignada_a=otro, fecha_compromiso=date.today())

    # Una tarea cerrada NO cuenta como pendiente, aunque su estado terminal no se
    # llame literalmente «completada» (los estados son configurables en Gerencia).
    Tarea.objects.create(proyecto=proyecto, titulo="Tarea ya cerrada",
                         asignada_a=otro, estado="completada",
                         fecha_compromiso=date.today())

    client.force_login(admin)
    html = client.get("/").content.decode()
    assert "Tareas pendientes" in html
    assert "Tarea de alguien más" in html
    assert "Otro Del Equipo" in html
    assert "Tarea ya cerrada" not in html


# ── Calendario ─────────────────────────────────────────────────────────────

class TestCalendario:

    def test_los_dias_de_otro_mes_no_se_pintan(self, client, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        client.force_login(admin)
        html = client.get("/calendario/?year=2026&month=8").content.decode()
        # Agosto 2026 arranca en sábado: los 5 primeros huecos van vacíos.
        assert 'aria-hidden="true"' in html
        assert "opacity-40" not in html

    def test_el_finde_va_mas_angosto(self, client, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        client.force_login(admin)
        html = client.get("/calendario/").content.decode()
        assert "minmax(0,0.8fr)" in html

    def test_los_botones_estan_arriba_del_calendario(self, client, usuario_factory):
        """Nuevo evento y Resumir con El Chalán a la IZQUIERDA, arriba de Hoy."""
        admin = usuario_factory(rol="super_admin")
        client.force_login(admin)
        html = client.get("/calendario/").content.decode()
        assert html.index("Nuevo evento") < html.index(">Hoy<")
        assert html.index("Resumir con El Chalán") < html.index(">Hoy<")

    def test_el_resumen_trae_las_cuatro_secciones(
            self, client, proyecto_factory, usuario_factory, monkeypatch):
        from apps.calendario import resumen_ia
        from apps.el_pizarron.models import Tarea

        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Playeras LCC")
        Tarea.objects.create(proyecto=proyecto, titulo="Mandar el arte",
                             asignada_a=admin, fecha_compromiso=date.today())
        # El Chalán sólo aporta la frase de carga; el resumen sale sin él si falla.
        monkeypatch.setattr(resumen_ia, "lectura_de_carga",
                            lambda **_k: {"ok": False, "lectura": "", "error": "sin IA"})
        client.force_login(admin)
        html = client.get("/calendario/resumen/").content.decode()
        assert "Hoy" in html
        assert "Tareas" in html
        assert "Mandar el arte" in html

    def test_el_resumen_no_incluye_tareas_completadas(
            self, proyecto_factory, usuario_factory):
        from apps.calendario.resumen import texto_calendario
        from apps.el_pizarron.models import Tarea

        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Playeras LCC")
        Tarea.objects.create(proyecto=proyecto, titulo="Pendiente viva",
                             asignada_a=admin, fecha_compromiso=date.today())
        Tarea.objects.create(proyecto=proyecto, titulo="Ya cerrada",
                             asignada_a=admin, estado="completada",
                             fecha_compromiso=date.today())
        texto = texto_calendario(admin)
        assert "Pendiente viva" in texto
        assert "Ya cerrada" not in texto

    def test_las_entregas_llevan_fecha_proyecto_y_productos(
            self, proyecto_factory, usuario_factory):
        from apps.calendario.resumen import texto_calendario
        from apps.los_proyectos.models import ProyectoProducto
        from django.utils import timezone

        admin = usuario_factory(rol="super_admin")
        proyecto = proyecto_factory(nombre="Playeras LCC")
        proyecto.fecha_compromiso = timezone.now() + timedelta(days=5)
        proyecto.save(update_fields=["fecha_compromiso"])
        ProyectoProducto.objects.create(
            proyecto=proyecto, servicio=_servicio(), cantidad=16,
            nombre_proyecto="Playera dry fit — negro")

        texto = texto_calendario(admin)
        assert "Siguientes entregas:" in texto
        assert "Playeras LCC" in texto
        assert "Playera dry fit — negro" in texto
