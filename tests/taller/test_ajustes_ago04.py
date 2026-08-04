"""LC 2026-08-04 — ronda de ajustes de Oscar.

Cubre: el workflow del chat que fallaba (cliente dictado de corrido + producto al
proyecto que se acaba de crear), el formato visual de las respuestas del Chalán
con su botón de destino, el Dashboard (buscador en el encabezado y lectura de IA
en el reporte de pendientes), el resumen del calendario rehecho, el calendario en
móvil, la regla del desglose con un solo producto, los centavos del documento y
el botón «Nuevo proyecto» en la ficha del cliente.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


# ── Fixtures / helpers ───────────────────────────────────────────────────────

@pytest.fixture
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture
def _drive_falso(monkeypatch):
    monkeypatch.setattr("lib.imagen_publica.precalentar", lambda *_a, **_k: False)
    monkeypatch.setattr("lib.imagen_publica.proporcion", lambda *_a, **_k: 0.0)


def _accion(payload):
    return SimpleNamespace(payload=payload, entidad_tipo=None, entidad_id=None)


def _servicio(nombre="Playera Kari Kari", **kw):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(
        nombre="Producción", defaults={"orden": 10})
    return Servicio.objects.create(
        nombre=nombre, categoria=cat, precio_base=Decimal("210.00"), **kw)


def _dictado(autor, acciones):
    """Un Dictado del chat con sus acciones confirmadas, listo para `aplicar`."""
    from apps.el_dictado.models import Dictado, DictadoAccion
    d = Dictado.objects.create(
        autor=autor, texto_crudo="(chat)", estado="esperando_confirmacion",
        origen="taller_chat", chalan="anthropic")
    for i, (tipo, payload) in enumerate(acciones):
        DictadoAccion.objects.create(
            dictado=d, orden=i, tipo=tipo, descripcion=tipo,
            payload=payload, confirmada=True)
    return d


# ── 1. El workflow del chat que Oscar mandó en la imagen ─────────────────────

class TestClienteDictadoDeCorrido:
    """«$karikari» tiene que caer en «KARI KARI»: pegado no empataba ni exacto,
    ni normalizado, ni por contención."""

    def test_resuelve_cliente_sin_espacios(self, cliente_factory):
        from apps.el_dictado.ejecutores.basicos import _resolver_cliente
        cli = cliente_factory(razon_social="KARI KARI")
        assert _resolver_cliente("karikari").pk == cli.pk

    def test_tambien_con_el_prefijo_de_referencia(self, cliente_factory):
        from apps.el_dictado.ejecutores.basicos import _resolver_cliente
        cli = cliente_factory(razon_social="Grupo Lazanto S.A. de C.V.")
        assert _resolver_cliente("$grupolazanto").pk == cli.pk

    def test_no_adivina_si_hay_dos_candidatos(self, cliente_factory):
        from apps.el_dictado.ejecutores.basicos import _resolver_cliente
        cliente_factory(razon_social="Kari Kari")
        cliente_factory(razon_social="KA RI KARI")
        with pytest.raises(ValueError, match="no encontrado"):
            _resolver_cliente("karikari")


class TestProyectoDelMismoDictado:
    """«crea el proyecto X para $cliente y agrégale 18 playeras»: la segunda
    acción moría con «tiene varios proyectos, ¿en cuál lo registro?»."""

    def test_prefiere_el_proyecto_recien_creado(self, cliente_factory, proyecto_factory):
        from apps.el_dictado.ejecutores.basicos import _resolver_proyecto_para
        cli = cliente_factory(razon_social="KARI KARI")
        proyecto_factory(cliente=cli, nombre="Viejo 1")
        proyecto_factory(cliente=cli, nombre="Viejo 2")
        nuevo = proyecto_factory(cliente=cli, nombre="Playeras Extra Kari Kari")
        contexto = {"entidades_creadas": {0: {"tipo": "proyecto", "id": nuevo.pk}}}

        resuelto = _resolver_proyecto_para({"cliente_slug": "karikari"}, contexto)
        assert resuelto.pk == nuevo.pk

    def test_ignora_el_recien_creado_si_es_de_otro_cliente(
            self, cliente_factory, proyecto_factory):
        from apps.el_dictado.ejecutores.basicos import _resolver_proyecto_para
        cli = cliente_factory(razon_social="KARI KARI")
        unico = proyecto_factory(cliente=cli, nombre="El único de Kari")
        otro = proyecto_factory(nombre="De alguien más")
        contexto = {"entidades_creadas": {0: {"tipo": "proyecto", "id": otro.pk}}}

        # El proyecto del contexto NO es de este cliente: cae al único activo.
        assert _resolver_proyecto_para({"cliente_slug": "karikari"}, contexto).pk == unico.pk

    def test_sin_cliente_tambien_toma_el_del_dictado(self, proyecto_factory):
        from apps.el_dictado.ejecutores.basicos import _resolver_proyecto_para
        p = proyecto_factory(nombre="Recién creado")
        contexto = {"entidades_creadas": {0: {"tipo": "proyecto", "id": p.pk}}}
        assert _resolver_proyecto_para({}, contexto).pk == p.pk

    def test_dictado_completo_crea_proyecto_y_le_cuelga_el_producto(
            self, cliente_factory, proyecto_factory, usuario_factory, _on_commit_inmediato):
        """El caso exacto de la imagen, de punta a punta."""
        from apps.el_dictado.services import aplicar
        from apps.los_proyectos.models import ProyectoProducto

        admin = usuario_factory(rol="super_admin")
        cli = cliente_factory(razon_social="KARI KARI", creado_por=admin)
        # Dos proyectos viejos: es lo que hacía imposible adivinar.
        proyecto_factory(cliente=cli, nombre="Viejo A", creado_por=admin)
        proyecto_factory(cliente=cli, nombre="Viejo B", creado_por=admin)
        _servicio("Playera Kari Kari")

        d = _dictado(admin, [
            ("crear_proyecto", {"nombre": "Playeras Extra Kari Kari",
                                "cliente_slug": "$karikari"}),
            # El LLM omitió el `@accion_0` — justo el bug.
            ("agregar_producto_proyecto", {"cliente_slug": "karikari",
                                           "servicio": "Playera Kari Kari",
                                           "cantidad": 18}),
        ])
        res = aplicar(dictado=d, usuario=admin)

        assert res == {"aplicadas": 2, "fallidas": 0}
        pp = ProyectoProducto.objects.get()
        assert pp.proyecto.nombre == "Playeras Extra Kari Kari"
        assert pp.cantidad == 18


# ── 2. Respuestas del chat: pastilla, campos y botón de destino ──────────────

class TestPresentacionDelChat:
    def test_la_pastilla_usa_el_titulo_del_catalogo(self):
        from apps.el_dictado.presentacion import titulo_accion
        assert titulo_accion("crear_proyecto") == "Crear proyecto"
        assert titulo_accion("tipo_inventado_zz") == "Tipo inventado zz"

    def test_los_campos_salen_legibles_y_en_orden(self):
        from apps.el_dictado.presentacion import campos_accion
        campos = campos_accion("crear_proyecto", {
            "nombre": "Bandanas NIKE RUN",
            "cliente_slug": "$optimist",
            "fecha_compromiso": "2026-08-03",
        })
        etiquetas = [c["etiqueta"] for c in campos]
        assert etiquetas == ["Nombre", "Cliente", "Fecha de entrega"]
        assert campos[1]["valor"] == "optimist"          # sin el `$`
        assert campos[2]["valor"] == "3 de agosto de 2026"

    def test_aplana_los_campos_anidados(self):
        from apps.el_dictado.presentacion import campos_accion
        campos = campos_accion("actualizar_proyecto",
                               {"proyecto_slug": "lc-0044",
                                "campos": {"estado": "entregado"}})
        assert {"etiqueta": "Estado", "valor": "entregado"} in campos

    def test_enlace_al_proyecto_creado(self, proyecto_factory, usuario_factory):
        from apps.el_dictado.models import DictadoAccion
        admin = usuario_factory(rol="super_admin")
        p = proyecto_factory(creado_por=admin)
        d = _dictado(admin, [("crear_proyecto", {})])
        DictadoAccion.objects.filter(dictado=d).update(
            aplicada=True, entidad_tipo="proyecto", entidad_id=p.pk)

        enlaces = d.enlaces_resultado
        assert enlaces == [{"url": f"/proyectos/{p.pk}/", "etiqueta": "Ir al proyecto"}]

    def test_el_producto_de_una_linea_lleva_a_su_proyecto(
            self, proyecto_factory, usuario_factory):
        from apps.el_dictado.models import DictadoAccion
        from apps.los_proyectos.models import ProyectoProducto
        admin = usuario_factory(rol="super_admin")
        p = proyecto_factory(creado_por=admin)
        pp = ProyectoProducto.objects.create(proyecto=p, servicio=_servicio(), cantidad=3)
        d = _dictado(admin, [("agregar_producto_proyecto", {})])
        DictadoAccion.objects.filter(dictado=d).update(
            aplicada=True, entidad_tipo="producto", entidad_id=pp.pk)

        assert d.enlaces_resultado[0]["url"] == f"/proyectos/{p.pk}/"

    def test_una_entidad_sin_pagina_no_deja_boton(self, usuario_factory):
        from apps.el_dictado.models import DictadoAccion
        admin = usuario_factory(rol="super_admin")
        d = _dictado(admin, [("enviar_correo", {})])
        DictadoAccion.objects.filter(dictado=d).update(
            aplicada=True, entidad_tipo="correo", entidad_id=1)
        assert d.enlaces_resultado == []

    def test_el_markdown_del_chalan_se_limpia(self):
        from apps.el_dictado.services_chat import _limpiar_texto_bot
        assert _limpiar_texto_bot("He propuesto **crear** el proyecto") == \
            "He propuesto crear el proyecto"
        assert _limpiar_texto_bot("## Resumen\n\n\n\nlisto") == "Resumen\n\nlisto"

    def test_la_tarjeta_de_accion_muestra_pastilla_y_campos(
            self, client, cliente_factory, usuario_factory):
        from apps.el_dictado.models import ConversacionChat, MensajeChat
        admin = usuario_factory(rol="super_admin")
        cliente_factory(razon_social="Optimist", creado_por=admin)
        conv = ConversacionChat.objects.create(usuario=admin, titulo="prueba")
        d = _dictado(admin, [("crear_proyecto", {"nombre": "Bandanas NIKE RUN",
                                                 "cliente_slug": "optimist"})])
        MensajeChat.objects.create(conversacion=conv, orden=1, rol="bot",
                                   tipo="accion", cuerpo="", dictado=d)
        client.force_login(admin)
        html = client.get(f"/chalan/c/{conv.pk}/").content.decode()

        assert "Crear proyecto" in html          # pastilla
        assert "Bandanas NIKE RUN" in html       # campo
        assert ">Confirmar<" in html

    def test_el_resultado_trae_el_boton_de_destino(
            self, client, cliente_factory, usuario_factory, _on_commit_inmediato):
        from apps.el_dictado.models import ConversacionChat, MensajeChat
        admin = usuario_factory(rol="super_admin")
        cliente_factory(razon_social="Optimist", creado_por=admin)
        conv = ConversacionChat.objects.create(usuario=admin, titulo="prueba")
        d = _dictado(admin, [("crear_proyecto", {"nombre": "Bandanas NIKE RUN",
                                                 "cliente_slug": "optimist"})])
        accion = d.acciones.get()
        MensajeChat.objects.create(conversacion=conv, orden=1, rol="bot",
                                   tipo="accion", cuerpo="", dictado=d)
        client.force_login(admin)
        client.post(f"/chalan/{d.pk}/aplicar", {f"accion_{accion.pk}": "on"})

        html = client.get(f"/chalan/c/{conv.pk}/").content.decode()
        assert "Ir al proyecto →" in html
        assert "✓ Listo" in html


# ── 3. Dashboard ─────────────────────────────────────────────────────────────

class TestDashboard:
    def test_el_buscador_va_en_el_encabezado_del_kanban(self, client, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        client.force_login(admin)
        html = client.get("/").content.decode()
        assert html.index("Proyectos activos") < html.index('id="kanban-buscar"')
        assert html.index('id="kanban-buscar"') < html.index("Ver tablero completo")

    def test_el_reporte_de_pendientes_lleva_la_lectura_del_chalan(
            self, client, proyecto_factory, usuario_factory, monkeypatch):
        from apps.taller_home import pendientes_ia
        monkeypatch.setattr(
            pendientes_ia, "lectura_de_pendientes",
            lambda **_k: {"ok": True, "lectura": "Hoy urge la entrega de Kari Kari.",
                          "error": ""})
        admin = usuario_factory(rol="super_admin")
        proyecto_factory(creado_por=admin)
        client.force_login(admin)
        html = client.get("/resumen/actividad/", HTTP_HX_REQUEST="true").content.decode()
        assert "Hoy urge la entrega de Kari Kari." in html
        assert "<b>URGENTES</b>" in html   # el reporte exacto sigue debajo

    def test_si_el_chalan_no_responde_el_reporte_sale_igual(
            self, client, proyecto_factory, usuario_factory, monkeypatch):
        from apps.taller_home import pendientes_ia
        monkeypatch.setattr(pendientes_ia, "lectura_de_pendientes",
                            lambda **_k: {"ok": False, "lectura": "", "error": "caído"})
        admin = usuario_factory(rol="super_admin")
        proyecto_factory(creado_por=admin)
        client.force_login(admin)
        html = client.get("/resumen/actividad/", HTTP_HX_REQUEST="true").content.decode()
        assert "<b>URGENTES</b>" in html
        assert "caído" not in html


# ── 4. Resumen del calendario ────────────────────────────────────────────────

class TestResumenCalendario:
    def test_las_tareas_atrasadas_van_en_amarillo_con_su_proyecto(
            self, client, proyecto_factory, usuario_factory, monkeypatch):
        from apps.calendario import resumen_ia
        from apps.el_pizarron.models import Tarea
        monkeypatch.setattr(resumen_ia, "lectura_de_carga",
                            lambda **_k: {"ok": False, "lectura": "", "error": ""})
        admin = usuario_factory(rol="super_admin")
        p = proyecto_factory(nombre="Playeras LCC", creado_por=admin)
        Tarea.objects.create(proyecto=p, titulo="Mandar el arte", asignada_a=admin,
                             fecha_compromiso=date.today() - timedelta(days=3))
        client.force_login(admin)
        html = client.get("/calendario/resumen/").content.decode()

        assert "text-warning-700" in html
        assert "- Playeras LCC" in html
        assert "<ol" in html            # numerado

    def test_las_entregas_anidan_sus_productos(
            self, client, proyecto_factory, usuario_factory, monkeypatch):
        from apps.calendario import resumen_ia
        from apps.los_proyectos.models import ProyectoProducto
        from django.utils import timezone
        monkeypatch.setattr(resumen_ia, "lectura_de_carga",
                            lambda **_k: {"ok": False, "lectura": "", "error": ""})
        admin = usuario_factory(rol="super_admin")
        p = proyecto_factory(nombre="Playeras LCC", creado_por=admin,
                             fecha_compromiso=timezone.now() + timedelta(days=4))
        ProyectoProducto.objects.create(
            proyecto=p, servicio=_servicio(), cantidad=16,
            nombre_proyecto="Playera dry fit — negro")
        client.force_login(admin)
        html = client.get("/calendario/resumen/").content.decode()

        assert "Siguientes entregas" in html
        assert "Playera dry fit — negro · 16 pz" in html

    def test_hay_horizontes_por_semana(self, client, proyecto_factory, usuario_factory, monkeypatch):
        from apps.calendario import resumen_ia
        from apps.el_pizarron.models import Tarea
        monkeypatch.setattr(resumen_ia, "lectura_de_carga",
                            lambda **_k: {"ok": False, "lectura": "", "error": ""})
        admin = usuario_factory(rol="super_admin")
        p = proyecto_factory(nombre="Playeras LCC", creado_por=admin)
        Tarea.objects.create(proyecto=p, titulo="Junta de arranque", asignada_a=admin,
                             fecha_compromiso=date.today() + timedelta(days=9))
        client.force_login(admin)
        html = client.get("/calendario/resumen/").content.decode()
        assert "En 2 semanas" in html or "La próxima semana" in html
        assert "Junta de arranque" in html

    def test_lo_lejano_sale_general(self, proyecto_factory, usuario_factory):
        from apps.calendario.resumen import texto_calendario
        from django.utils import timezone
        admin = usuario_factory(rol="super_admin")
        proyecto_factory(nombre="Entrega muy lejana", creado_por=admin,
                         fecha_compromiso=timezone.now() + timedelta(days=70))
        texto = texto_calendario(admin)
        assert "Más adelante:" in texto
        assert "1 entrega(s)" in texto

    def test_el_texto_va_numerado(self, proyecto_factory, usuario_factory):
        from apps.calendario.resumen import texto_calendario
        from apps.el_pizarron.models import Tarea
        admin = usuario_factory(rol="super_admin")
        p = proyecto_factory(nombre="Playeras LCC", creado_por=admin)
        Tarea.objects.create(proyecto=p, titulo="Pendiente viva", asignada_a=admin,
                             fecha_compromiso=date.today())
        texto = texto_calendario(admin)
        assert "1. " in texto
        assert "Pendiente viva" in texto

    def test_el_evento_de_tarea_lleva_el_nombre_del_proyecto(
            self, proyecto_factory, usuario_factory):
        from apps.calendario.services import eventos_por_dia
        from apps.el_pizarron.models import Tarea
        admin = usuario_factory(rol="super_admin")
        p = proyecto_factory(nombre="Playeras LCC", creado_por=admin)
        Tarea.objects.create(proyecto=p, titulo="Mandar el arte", asignada_a=admin,
                             fecha_compromiso=date.today())
        evs = eventos_por_dia(admin, date.today(), date.today())[date.today()]
        assert evs[0]["subtitulo"] == "Playeras LCC"


# ── 5. Calendario en móvil ───────────────────────────────────────────────────

def test_el_mes_puede_encoger(client, usuario_factory):
    """`min-w-0`: sin él el grid item no encoge y la página saca scroll lateral."""
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get("/calendario/").content.decode()
    assert 'class="min-w-0 max-w-full overflow-hidden rounded-2xl' in html


# ── 6. Documento: desglose con un solo producto y centavos ───────────────────

class TestDocumentoCotizacion:
    def _cot_con(self, proyecto, actor, nombres):
        from apps.cotizaciones.models import Cotizacion, CotizacionItem
        cot = Cotizacion.objects.create(
            cliente=proyecto.cliente, proyecto=proyecto, titulo=proyecto.nombre,
            estado="borrador", version=1, creado_por=actor,
            incluir_desglose=True, regimen_fiscal="iva")
        for i, nombre in enumerate(nombres):
            CotizacionItem.objects.create(
                cotizacion=cot, orden=i, concepto=nombre, descripcion=nombre,
                cantidad=Decimal("1"), precio_unitario=Decimal("1000.00"))
        return cot

    def test_un_solo_producto_no_imprime_la_tabla_de_desglose(
            self, proyecto_factory, usuario_factory, _drive_falso):
        from apps.cotizaciones.services import construir_html_pdf
        admin = usuario_factory(rol="super_admin")
        cot = self._cot_con(proyecto_factory(creado_por=admin), admin, ["Playera"])
        html = construir_html_pdf(cot)

        assert "Desglose de Elementos" not in html
        assert "Subtotal" in html          # los montos sí van
        assert ">Total<" in html

    def test_con_dos_productos_si_va_el_desglose(
            self, proyecto_factory, usuario_factory, _drive_falso):
        from apps.cotizaciones.services import construir_html_pdf
        admin = usuario_factory(rol="super_admin")
        cot = self._cot_con(proyecto_factory(creado_por=admin), admin,
                            ["Playera", "Gorra"])
        assert "Desglose de Elementos" in construir_html_pdf(cot)

    def test_los_totales_llevan_siempre_los_centavos(
            self, proyecto_factory, usuario_factory, _drive_falso):
        from apps.cotizaciones.services import construir_html_pdf
        admin = usuario_factory(rol="super_admin")
        cot = self._cot_con(proyecto_factory(creado_por=admin), admin, ["Playera"])
        html = construir_html_pdf(cot)
        assert "1,000.00" in html          # subtotal exacto, no «1,000»

    def test_el_filtro_de_centavos(self):
        from cuentas.templatetags.forms_helpers import (
            dinero_exacto,
            dinero_exacto_sin_signo,
            dinero_sin_signo,
        )
        assert dinero_exacto(1000) == "$1,000.00"
        assert dinero_exacto_sin_signo(Decimal("1234.5")) == "1,234.50"
        assert dinero_exacto_sin_signo(Decimal("-99")) == "-99.00"
        assert dinero_sin_signo(1000) == "1,000"     # el normal sigue truncando
        assert dinero_exacto(None) == "—"


# ── 7. Ficha del cliente: arrancar un proyecto suyo ──────────────────────────

class TestNuevoProyectoDesdeElCliente:
    def test_el_boton_aparece_en_la_ficha(self, client, cliente_factory, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        cli = cliente_factory(creado_por=admin)
        client.force_login(admin)
        html = client.get(f"/cartera/{cli.pk}/").content.decode()
        assert "+ Nuevo proyecto" in html
        assert f"?cliente={cli.pk}" in html

    def test_el_disenador_no_lo_ve(self, client, cliente_factory, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        disenador = usuario_factory(rol="disenador")
        cli = cliente_factory(creado_por=admin)
        client.force_login(disenador)
        r = client.get(f"/cartera/{cli.pk}/")
        if r.status_code == 200:
            assert "+ Nuevo proyecto" not in r.content.decode()

    def test_el_modal_abre_con_el_cliente_puesto(self, client, cliente_factory, usuario_factory):
        admin = usuario_factory(rol="super_admin")
        cli = cliente_factory(razon_social="Kari Kari", creado_por=admin)
        client.force_login(admin)
        html = client.get(f"/proyectos/nuevo?cliente={cli.pk}",
                          HTTP_HX_REQUEST="true").content.decode()
        assert f'value="{cli.pk}" selected' in html


# ── 8. Resumen de actividad del proyecto ─────────────────────────────────────

class TestResumenActividadProyecto:
    def test_el_contexto_incluye_los_productos(self, proyecto_factory, usuario_factory, monkeypatch):
        from apps.los_proyectos import resumen_ia
        from apps.los_proyectos.models import ProyectoProducto

        admin = usuario_factory(rol="super_admin")
        p = proyecto_factory(nombre="Playeras LCC", creado_por=admin)
        ProyectoProducto.objects.create(
            proyecto=p, servicio=_servicio(), cantidad=16,
            nombre_proyecto="Playera dry fit — negro")

        capturado = {}

        def _falso(*, estacion, prompt, **_kw):
            capturado["prompt"] = prompt
            return SimpleNamespace(texto="Estado: en diseño · Kari Kari")

        monkeypatch.setattr("lib.analistas.analizar", _falso)
        res = resumen_ia.resumir_actividad(proyecto=p, usuario=admin)

        assert res["ok"]
        assert "PRODUCTOS INVOLUCRADOS" in capturado["prompt"]
        assert "Playera dry fit — negro · 16 pz" in capturado["prompt"]

    def test_el_modal_titula_con_el_nombre(self, client, proyecto_factory, usuario_factory, monkeypatch):
        from apps.los_proyectos import views as vistas
        monkeypatch.setattr(
            vistas, "puede_usar_chalan", lambda *_a, **_k: True, raising=False)
        monkeypatch.setattr(
            "apps.los_proyectos.resumen_ia.resumir_actividad",
            lambda **_k: {"ok": True, "resumen": "Estado: en diseño", "error": ""})
        admin = usuario_factory(rol="super_admin")
        p = proyecto_factory(nombre="Playeras LCC", creado_por=admin)
        client.force_login(admin)
        html = client.get(f"/proyectos/{p.pk}/resumir-actividad",
                          HTTP_HX_REQUEST="true").content.decode()
        assert "Resumen de actividad · Playeras LCC" in html
