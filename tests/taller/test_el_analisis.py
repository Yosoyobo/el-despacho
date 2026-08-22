"""El Análisis: que los nueve temas hablen con datos reales y no se caigan.

Sprint S-Chalan-Analisis (2026-08-22). El hallazgo que originó todo: los
conteos buscaban estados literales ('borrador', 'enviada') que Learning Center
había apagado, así que la conversión salía 100% cuando la real rondaba 30%.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


# ── Los nueve temas nunca tumban nada ────────────────────────────────────

def test_todos_los_temas_responden_sin_datos():
    """Con la base vacía cada tema contesta, aunque sea para decir que no hay nada."""
    from apps.taller_home import negocio

    for dominio in negocio.DOMINIOS:
        hechos = negocio.hechos_de(dominio)
        assert set(hechos) == {"titulo", "hechos", "metricas"}, dominio
        assert hechos["titulo"], dominio


def test_el_alias_margenes_apunta_a_rentabilidad():
    """'margenes' era el margen del Catálogo; ahora contesta con proyectos reales."""
    from apps.taller_home import negocio

    assert negocio.hechos_de("margenes")["titulo"] == negocio.ETIQUETA_DOMINIO["rentabilidad"]


# ── Fases de cotización ──────────────────────────────────────────────────

def test_fase_clasifica_por_significado_no_por_nombre(db):
    """Un estado que el despacho llamó como quiso se clasifica por su fase."""
    from apps.cotizaciones.models import (
        FASE_GANADA,
        EstadoCotizacion,
        fase_de,
        invalidar_cache_estados_cot,
        slugs_de_fase,
    )

    EstadoCotizacion.objects.create(
        slug="cerrado_trato", label="Cerramos trato", fase=FASE_GANADA, orden=90,
    )
    invalidar_cache_estados_cot()
    assert fase_de("cerrado_trato") == FASE_GANADA
    assert "cerrado_trato" in slugs_de_fase(FASE_GANADA)


def test_estado_desconocido_no_cuenta_como_ganado_ni_perdido():
    """Lo prudente ante un slug que no existe: tratarlo como armada."""
    from apps.cotizaciones.models import FASE_ARMADA, fase_de

    assert fase_de("un_estado_que_nadie_creo") == FASE_ARMADA


# ── El embudo cuenta oportunidades, no documentos ────────────────────────

@pytest.fixture
def _catalogo_estados(db):
    from apps.cotizaciones.models import EstadoCotizacion, invalidar_cache_estados_cot

    EstadoCotizacion.objects.all().delete()
    for slug, label, fase, orden in (
        ("generada", "Generada", "armada", 10),
        ("enviada", "Enviada", "enviada", 20),
        ("aprobada", "Aprobada", "ganada", 30),
        ("rechazada", "Rechazada", "perdida", 40),
    ):
        EstadoCotizacion.objects.create(
            slug=slug, label=label, fase=fase, orden=orden, activo=True,
        )
    invalidar_cache_estados_cot()
    yield
    invalidar_cache_estados_cot()


def _cotizar(proyecto, usuario, estado, version, **extra):
    from apps.cotizaciones.models import Cotizacion

    return Cotizacion.objects.create(
        cliente=proyecto.cliente, proyecto=proyecto, titulo=f"v{version}",
        estado=estado, version=version, creado_por=usuario, **extra,
    )


def test_tres_versiones_de_un_proyecto_son_una_sola_oportunidad(
    _catalogo_estados, proyecto_factory, usuario_factory
):
    """Cotizar tres veces el mismo proyecto no son tres oportunidades."""
    from apps.cotizaciones.embudo import embudo, oportunidades

    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    _cotizar(p, u, "generada", 1)
    _cotizar(p, u, "generada", 2)
    _cotizar(p, u, "aprobada", 3)

    assert len(oportunidades()) == 1
    emb = embudo()
    assert emb["total"] == 1
    # Vale la última versión: está ganada.
    assert emb["ganadas"] == 1
    assert emb["armadas"] == 0


def test_conversion_no_es_cien_por_ciento_cuando_hay_cotizaciones_paradas(
    _catalogo_estados, proyecto_factory, usuario_factory
):
    """El bug original: sólo se contaban los estados literales y todo daba 100%."""
    from apps.cotizaciones.embudo import embudo

    u = usuario_factory(rol="super_admin")
    for _ in range(3):
        _cotizar(proyecto_factory(), u, "generada", 1)
    _cotizar(proyecto_factory(), u, "aprobada", 1)
    _cotizar(proyecto_factory(), u, "rechazada", 1)

    emb = embudo()
    assert emb["total"] == 5
    assert emb["armadas"] == 3
    assert emb["ganadas"] == 1
    assert emb["perdidas"] == 1
    # De lo resuelto (1 ganada + 1 perdida) se ganó la mitad.
    assert emb["conversion_pct"] == 50.0
    # De todo lo cotizado se cerró 1 de 5.
    assert emb["cierre_pct"] == 20.0


def test_armada_vieja_sale_como_nunca_enviada(
    _catalogo_estados, proyecto_factory, usuario_factory
):
    from apps.cotizaciones.embudo import embudo

    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    _cotizar(p, u, "generada", 1, fecha_emision=date.today() - timedelta(days=30))

    emb = embudo()
    assert len(emb["sin_enviar"]) == 1
    assert emb["sin_enviar"][0]["dias"] >= 30


def test_enviada_sin_respuesta_se_enfria_segun_lo_configurado(
    _catalogo_estados, proyecto_factory, usuario_factory
):
    from apps.cotizaciones.embudo import embudo
    from django.utils import timezone

    from ajustes.models import ConfiguracionAnalisis

    cfg = ConfiguracionAnalisis.obtener()
    cfg.dias_silencio_cotizacion = 45
    cfg.save()

    u = usuario_factory(rol="super_admin")
    _cotizar(proyecto_factory(), u, "enviada", 1,
             enviada_en=timezone.now() - timedelta(days=50))
    _cotizar(proyecto_factory(), u, "enviada", 1,
             enviada_en=timezone.now() - timedelta(days=10))

    emb = embudo()
    assert emb["enviadas"] == 2
    assert len(emb["enfriadas"]) == 1


def test_el_sello_de_envio_manda_sobre_el_estado(
    _catalogo_estados, proyecto_factory, usuario_factory
):
    """Si ya se mandó, cuenta como enviada aunque el estado diga otra cosa."""
    from apps.cotizaciones.embudo import fase_efectiva
    from django.utils import timezone

    u = usuario_factory(rol="super_admin")
    cot = _cotizar(proyecto_factory(), u, "generada", 1, enviada_en=timezone.now())
    assert fase_efectiva(cot) == "enviada"


# ── Facturas con CFDI: el flujo no se toca, el conteo sí ─────────────────

def test_factura_en_borrador_con_cfdi_cuenta_como_facturada(
    proyecto_factory, usuario_factory
):
    from apps.facturacion.models import Factura

    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    f = Factura.objects.create(
        cliente=p.cliente, proyecto=p, concepto="Trabajo", creado_por=u,
        estado="borrador", xml_file_id="abc123",
    )
    assert f.facturada_de_verdad is True
    assert f.cfdi_sin_emitir is True
    # Pero para el flujo sigue siendo un borrador: no se tocó.
    assert f.estado == "borrador"
    assert f.es_editable is True


def test_factura_en_borrador_sin_cfdi_no_cuenta(proyecto_factory, usuario_factory):
    from apps.facturacion.models import Factura

    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    f = Factura.objects.create(
        cliente=p.cliente, proyecto=p, concepto="Trabajo", creado_por=u, estado="borrador",
    )
    assert f.facturada_de_verdad is False
    assert f.cfdi_sin_emitir is False


def test_kpis_facturacion_separan_borrador_de_cfdi_sin_emitir(
    proyecto_factory, usuario_factory
):
    from apps.facturacion import services
    from apps.facturacion.models import Factura

    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    Factura.objects.create(cliente=p.cliente, proyecto=p, concepto="A",
                           creado_por=u, estado="borrador")
    Factura.objects.create(cliente=p.cliente, proyecto=p, concepto="B",
                           creado_por=u, estado="borrador", pdf_file_id="x1")

    kpis = services.kpis_landing()
    assert kpis["borradores"] == 1
    assert kpis["cfdi_sin_emitir"] == 1
    assert kpis["facturadas"] == 1


# ── Rentabilidad real ────────────────────────────────────────────────────

def test_margen_del_proyecto_usa_lo_capturado(proyecto_factory, usuario_factory):
    from apps.los_proyectos import rentabilidad as rent

    p = proyecto_factory()
    fila = rent.rentabilidad_de(p)
    assert fila["codigo"] == p.codigo
    assert fila["costo_mano_obra"] == 0.0
    # Sin mano de obra costeada, la segunda columna se declara indisponible.
    assert fila["margen_total_pct"] is None


def test_semaforo_respeta_el_umbral_configurado(db):
    from apps.los_proyectos.rentabilidad import semaforo_margen

    from ajustes.models import ConfiguracionAnalisis

    cfg = ConfiguracionAnalisis.obtener()
    cfg.margen_sano_pct = Decimal("50.00")
    cfg.margen_critico_pct = Decimal("0.00")
    cfg.save()

    assert semaforo_margen(70) == "verde"
    assert semaforo_margen(30) == "amarillo"
    assert semaforo_margen(-5) == "rojo"
    assert semaforo_margen(None) == "sin_datos"


# ── Configuración: los umbrales viven en el GUI ──────────────────────────

def test_la_configuracion_trae_los_defaults_acordados(db):
    from ajustes.models import ConfiguracionAnalisis

    cfg = ConfiguracionAnalisis.obtener()
    assert cfg.dias_silencio_cotizacion == 45
    assert cfg.margen_sano_pct == Decimal("50.00")
    assert cfg.prorratear_jornada is True
    assert cfg.auto_activar_aprendizajes is True


# ── Mano de obra: medido vs estimado ─────────────────────────────────────

def test_las_horas_del_cronometro_son_exactas(proyecto_factory, usuario_factory):
    from datetime import timedelta

    from apps.checador.models import SesionProyecto
    from apps.los_proyectos.mano_obra import horas_por_proyecto
    from django.utils import timezone

    from ajustes.models import ConfiguracionAnalisis, TarifaRol
    from cuentas.models.rol import Rol

    cfg = ConfiguracionAnalisis.obtener()
    cfg.prorratear_jornada = False       # sólo lo medido
    cfg.tarifa_hora_default = Decimal("100.00")
    cfg.save()

    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    inicio = timezone.now() - timedelta(hours=3)
    SesionProyecto.objects.create(
        usuario=u, proyecto=p, inicio=inicio, fin=timezone.now(),
        duracion_min=180, estado="cerrada",
    )

    hoy = date.today()
    mapa = horas_por_proyecto(hoy - timedelta(days=7), hoy)
    assert mapa[p.pk]["horas_medidas"] == 3.0
    assert mapa[p.pk]["estimado"] is False
    assert mapa[p.pk]["costo"] == 300.0
    assert Rol is not None and TarifaRol is not None  # importables


def test_la_jornada_se_reparte_pareja_entre_los_proyectos_del_dia(
    proyecto_factory, usuario_factory
):
    """Decisión de Oscar: parejo, no ponderado por monto."""
    from datetime import timedelta

    from apps.checador.models import Jornada
    from apps.los_proyectos.mano_obra import horas_por_proyecto
    from apps.los_proyectos.models import ActividadProyecto
    from django.utils import timezone

    from ajustes.models import ConfiguracionAnalisis

    cfg = ConfiguracionAnalisis.obtener()
    cfg.prorratear_jornada = True
    cfg.tarifa_hora_default = Decimal("100.00")
    cfg.save()

    u = usuario_factory(rol="super_admin")
    p1, p2 = proyecto_factory(), proyecto_factory()
    hoy = date.today()

    ahora = timezone.now()
    Jornada.objects.create(
        usuario=u, fecha=hoy, entrada_en=ahora - timedelta(hours=6),
        salida_en=ahora, estado="cerrada",
    )
    for p in (p1, p2):
        ActividadProyecto.objects.create(
            proyecto=p, tipo="comentario", descripcion="movió algo", actor=u,
        )

    mapa = horas_por_proyecto(hoy - timedelta(days=1), hoy)
    # Seis horas entre dos proyectos = tres y tres.
    assert round(mapa[p1.pk]["horas_estimadas"], 1) == 3.0
    assert round(mapa[p2.pk]["horas_estimadas"], 1) == 3.0
    assert mapa[p1.pk]["estimado"] is True


def test_sin_tarifas_no_se_finge_un_costo(db):
    from apps.los_proyectos.mano_obra import hay_tarifas_configuradas

    from ajustes.models import ConfiguracionAnalisis

    cfg = ConfiguracionAnalisis.obtener()
    cfg.tarifa_hora_default = Decimal("0.00")
    cfg.save()
    assert hay_tarifas_configuradas() is False


# ── Alertas: deterministas, sin IA ───────────────────────────────────────

def test_alerta_cuando_hay_facturas_con_cfdi_sin_emitir(
    proyecto_factory, usuario_factory
):
    from apps.facturacion.models import Factura
    from apps.taller_home.analisis import alertas

    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    Factura.objects.create(cliente=p.cliente, proyecto=p, concepto="A",
                           creado_por=u, estado="borrador", xml_file_id="x")

    claves = {a["clave"] for a in alertas(u)}
    assert "cfdi_sin_emitir" in claves


def test_alerta_de_cancelados_sin_motivo(proyecto_factory, usuario_factory):
    from apps.taller_home.analisis import alertas

    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    p.estado = "cancelado"
    p.save(update_fields=["estado"])

    avisos = {a["clave"]: a for a in alertas(u)}
    assert "cancelados_sin_motivo" in avisos
    assert avisos["cancelados_sin_motivo"]["nivel"] == "amarillo"


def test_las_alertas_respetan_lo_que_cada_quien_puede_ver(
    proyecto_factory, usuario_factory
):
    """Un diseñador no ve alertas de dinero."""
    from apps.facturacion.models import Factura
    from apps.taller_home.analisis import alertas

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    Factura.objects.create(cliente=p.cliente, proyecto=p, concepto="A",
                           creado_por=admin, estado="borrador", xml_file_id="x")

    disenador = usuario_factory(rol="disenador")
    claves = {a["clave"] for a in alertas(disenador)}
    assert "cfdi_sin_emitir" not in claves


# ── La lectura del Chalán ────────────────────────────────────────────────

def test_la_lectura_se_guarda_por_tema(monkeypatch, proyecto_factory, usuario_factory):
    from apps.taller_home import analisis
    from apps.taller_home.models import LecturaAnalisis

    usuario_factory(rol="super_admin")
    proyecto_factory()

    class _Respuesta:
        texto = '{"lecturas": {"ventas": "Hay trabajo parado sin mandar."}}'
        modelo = "claude-test"

    monkeypatch.setattr("lib.analistas.analizar", lambda **kw: _Respuesta())
    res = analisis.generar_lectura()
    assert res["ok"] is True
    assert res["creadas"] == 1
    assert LecturaAnalisis.ultima("ventas").texto.startswith("Hay trabajo parado")


def test_si_la_ia_no_responde_la_pantalla_sigue_saliendo(
    monkeypatch, proyecto_factory, usuario_factory
):
    from apps.taller_home import analisis

    u = usuario_factory(rol="super_admin")
    proyecto_factory()

    def _explota(**kw):
        raise RuntimeError("sin Chalanes disponibles")

    monkeypatch.setattr("lib.analistas.analizar", _explota)
    res = analisis.generar_lectura()
    assert res["ok"] is False
    # Y el panorama se arma igual, con cifras y sin opinión.
    datos = analisis.panorama(u)
    assert datos["temas"]
    assert all(t["lectura"] == "" for t in datos["temas"])


def test_una_respuesta_que_no_se_puede_leer_no_guarda_nada(
    monkeypatch, proyecto_factory, usuario_factory
):
    from apps.taller_home import analisis
    from apps.taller_home.models import LecturaAnalisis

    usuario_factory(rol="super_admin")
    proyecto_factory()

    class _Basura:
        texto = "no soy json"
        modelo = ""

    monkeypatch.setattr("lib.analistas.analizar", lambda **kw: _Basura())
    assert analisis.generar_lectura()["ok"] is False
    assert LecturaAnalisis.objects.count() == 0


# ── La pantalla ──────────────────────────────────────────────────────────

def test_la_pantalla_pide_permiso(client, usuario_factory):
    disenador = usuario_factory(rol="disenador")
    client.force_login(disenador)
    assert client.get("/analisis/").status_code == 403


def test_el_super_admin_entra_y_ve_sus_temas(client, usuario_factory, proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    proyecto_factory()
    client.force_login(admin)
    resp = client.get("/analisis/")
    assert resp.status_code == 200
    assert b"El An" in resp.content  # "El Análisis" (acentos escapados)
    assert resp.context["temas"]


def test_analizar_ahora_solo_por_post(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    assert client.get("/analisis/analizar-ahora").status_code == 405


# ── Aprendizaje: cuatro fuentes y auto-activación ────────────────────────

def test_ahora_aprende_tambien_de_los_dictados_que_fallaron(db, usuario_factory):
    """Antes sólo miraba correcciones explícitas — 8 casos contra 85 fallos."""
    from apps.el_dictado.models import Dictado

    from chalanes.destilar import recolectar_evidencia

    u = usuario_factory(rol="super_admin")
    Dictado.objects.create(autor=u, texto_crudo="mándale lo de siempre a la heladería",
                           estado="fallo_ia")
    evidencia = recolectar_evidencia()
    assert len(evidencia) == 1
    assert evidencia[0]["estado"] == "fallo_ia"


def test_aprende_de_las_conversaciones_del_chat(db, usuario_factory):
    from apps.el_dictado.models import ConversacionChat, MensajeChat

    from chalanes.destilar import recolectar_conversaciones

    u = usuario_factory(rol="super_admin")
    conv = ConversacionChat.objects.create(usuario=u, titulo="Prueba")
    MensajeChat.objects.create(conversacion=conv, orden=1, rol="usuario",
                               cuerpo="¿cómo va lo de la heladería?")
    MensajeChat.objects.create(conversacion=conv, orden=2, rol="asistente",
                               cuerpo="Te refieres al proyecto LC-0007.")

    pares = recolectar_conversaciones()
    assert len(pares) == 1
    assert "heladería" in pares[0]["pregunta"]


def test_lo_muy_seguro_se_activa_solo_y_lo_dudoso_espera(db, usuario_factory):
    from ajustes.models import ConfiguracionAnalisis
    from chalanes.destilar import _persistir

    cfg = ConfiguracionAnalisis.obtener()
    cfg.auto_activar_aprendizajes = True
    cfg.confianza_minima_auto = Decimal("0.85")
    cfg.save()

    autor = usuario_factory(rol="super_admin")
    creados, activados = _persistir([
        {"frase_o_patron": "la heladería", "interpretacion_correcta": "$michoacana",
         "peso": 1.0, "confianza": 0.95, "razon": "se repite"},
        {"frase_o_patron": "lo de siempre", "interpretacion_correcta": "?",
         "peso": 1.0, "confianza": 0.4, "razon": "un solo caso"},
    ], creado_por=autor)

    from chalanes.models import Aprendizaje
    assert creados == 2
    assert activados == 1
    assert Aprendizaje.objects.get(frase_o_patron="la heladería").activo is True
    assert Aprendizaje.objects.get(frase_o_patron="lo de siempre").activo is False


def test_si_se_apaga_la_auto_activacion_todo_espera_revision(db, usuario_factory):
    from ajustes.models import ConfiguracionAnalisis
    from chalanes.destilar import _persistir
    from chalanes.models import Aprendizaje

    cfg = ConfiguracionAnalisis.obtener()
    cfg.auto_activar_aprendizajes = False
    cfg.save()

    creados, activados = _persistir([
        {"frase_o_patron": "seguro", "interpretacion_correcta": "x",
         "peso": 1.0, "confianza": 1.0, "razon": ""},
    ], creado_por=usuario_factory(rol="super_admin"))
    assert (creados, activados) == (1, 0)
    assert Aprendizaje.objects.get(frase_o_patron="seguro").activo is False


# ── MCP: toda herramienta nueva va con su módulo (regla de Oscar) ────────

def test_los_temas_nuevos_estan_en_el_registro_de_capacidades():
    from capacidades import CAPACIDADES

    for nombre in ("resumen_rentabilidad", "resumen_perdidos", "resumen_clientes",
                   "resumen_proveedores", "resumen_equipo", "resumen_ia",
                   "rentabilidad_proyecto"):
        assert nombre in CAPACIDADES, nombre


def test_el_servidor_mcp_expone_el_analisis():
    from mcp_despacho import herramientas

    assert hasattr(herramientas, "resumen_negocio")
    assert hasattr(herramientas, "rentabilidad_proyectos")


def test_el_chalan_solo_ofrece_los_temas_que_el_usuario_puede_ver(usuario_factory):
    from capacidades import listar

    disenador = usuario_factory(rol="disenador")
    nombres = {c.nombre for c in listar(disenador)}
    assert "resumen_rentabilidad" not in nombres   # es dinero
    assert "resumen_equipo" in nombres             # abierto, filtra por dentro


# ── El caso real de Learning Center, como red permanente ─────────────────

def test_el_caso_real_de_lc_ya_no_reporta_cien_por_ciento(
    _catalogo_estados, proyecto_factory, usuario_factory
):
    """Reproduce la forma de la base de producción al 2026-08-22.

    25 oportunidades: 16 armadas ("Generada"), 3 con anticipo, 2 pagadas,
    3 aprobadas y 1 rechazada. Antes de este sprint el sistema reportaba
    100% de conversión porque contaba estados que ya nadie usa.
    """
    from apps.cotizaciones.embudo import embudo
    from apps.cotizaciones.models import EstadoCotizacion, invalidar_cache_estados_cot

    # LC tiene además estos dos, que el catálogo base no trae.
    EstadoCotizacion.objects.create(slug="anticipo", label="Anticipo",
                                    fase="ganada", orden=35)
    EstadoCotizacion.objects.create(slug="pagada", label="Pagada",
                                    fase="ganada", orden=50, terminal=True)
    invalidar_cache_estados_cot()

    u = usuario_factory(rol="super_admin")
    reparto = [("generada", 16), ("anticipo", 3), ("pagada", 2),
               ("aprobada", 3), ("rechazada", 1)]
    for estado, cuantos in reparto:
        for _ in range(cuantos):
            _cotizar(proyecto_factory(), u, estado, 1)

    emb = embudo()
    assert emb["total"] == 25
    assert emb["ganadas"] == 8       # anticipo + pagada + aprobada
    assert emb["perdidas"] == 1
    assert emb["armadas"] == 16
    # De lo resuelto se ganó casi todo…
    assert emb["conversion_pct"] == 88.9
    # …pero del pipeline completo apenas se ha cerrado un tercio.
    assert emb["cierre_pct"] == 32.0


def test_varias_versiones_no_inflan_el_conteo_como_antes(
    _catalogo_estados, proyecto_factory, usuario_factory
):
    """47 documentos son 25 oportunidades: contar documentos deforma todo."""
    from apps.cotizaciones.embudo import embudo, oportunidades

    u = usuario_factory(rol="super_admin")
    # 12 proyectos de una versión + 13 con varias = 25 oportunidades, 47 docs.
    for _ in range(12):
        _cotizar(proyecto_factory(), u, "generada", 1)
    for extra in (1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 4):
        p = proyecto_factory()
        for v in range(1, extra + 2):
            _cotizar(p, u, "generada", v)

    from apps.cotizaciones.models import Cotizacion
    assert Cotizacion.objects.count() == 47
    assert len(oportunidades()) == 25
    assert embudo()["total"] == 25


# ── La data migration, corrida CON datos ─────────────────────────────────

def test_la_migracion_del_permiso_siembra_con_super_admins_de_verdad(db, usuario_factory):
    """El hueco que dejó La Gerencia sin arrancar el 2026-08-22.

    La migración usaba `accion=` y el campo del modelo se llama `permiso`. NO
    falló en los tests aunque las migraciones sí se apliquen: se aplican sobre
    una base SIN usuarios, así que el bucle `for usuario in …super_admin` no
    itera nunca y el `update_or_create` malo jamás se evalúa. En producción, con
    super admins de verdad, revienta al arrancar y el contenedor no levanta.

    Por eso este test invoca la función de la migración a mano, con datos —
    que es la única forma de cubrir una data migration condicionada por filas.
    """
    import importlib

    from django.apps import apps as registro

    from cuentas.models.permiso_usuario import PermisoUsuario

    admin = usuario_factory(rol="super_admin")
    PermisoUsuario.objects.filter(usuario=admin, modulo="analisis").delete()

    migracion = importlib.import_module("cuentas.migrations.0041_seed_permiso_analisis")
    migracion.sembrar(registro, None)

    assert PermisoUsuario.objects.filter(
        usuario=admin, modulo="analisis", permiso="ver", activo=True,
    ).exists(), "el super admin se quedó sin la llave de El Análisis"
