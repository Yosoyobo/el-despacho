"""LC 2026-08-04 (segunda ronda) — ajustes de Oscar sobre el deploy del día.

Cubre los 4 puntos del ticket:

1. En escritorio el botón «Bajar PDF» debe DESCARGAR, no abrir la hoja de
   compartir del sistema (macOS sí implementa `navigator.share`).
2. El documento de la cotización con el interlineado más apretado.
3. Botón chiquito (✓ / ✕) en el recuadro «Cotizaciones» del proyecto para pasar
   a «Esperando respuesta» una vez que ya hay cotización.
4. **URGENTE** — el costo unitario y la ganancia unitaria del pie de la tarjeta
   de producto se calculaban mal (mostraban el costo del producto pelón,
   ignorando la merma y los procesos).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _servicio(nombre="Playera dry fit", precio="220.00", costo="44.94"):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Cat Ago04")
    return Servicio.objects.create(
        nombre=nombre, categoria=cat, precio_base=Decimal(precio),
        costo=Decimal(costo), activo=True,
    )


# ── 4 · URGENTE: costo unitario y ganancia unitaria de la tarjeta ────────────


def _linea_del_screenshot(proyecto_factory):
    """La línea EXACTA que Oscar mandó en el screenshot.

    25 pz + 4 de merma · producto $44.94 · impresión $39 POR PIEZA ·
    «Adaptación y positivos» $150 fijo · precio $220.
    Costo total = 44.94×29 + 39×29 + 150 = 2,584.26 (lo que ya salía bien).
    """
    from apps.los_proyectos.models import ProyectoProducto, ProyectoProductoProceso
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=25, merma=4,
        precio_unitario=Decimal("220.00"), costo_unitario=Decimal("44.94"),
    )
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="impresion", costo=Decimal("39.00"), por_pieza=True)
    ProyectoProductoProceso.objects.create(
        producto=pp, tipo="operativo", descripcion="Adaptación y positivos",
        costo=Decimal("150.00"), por_pieza=False)
    return pp


def test_costo_unitario_real_reparte_todo_el_costo_entre_las_piezas_cobradas(
        proyecto_factory):
    """El caso del screenshot: mostraba $44.94 y lo correcto es $103.37."""
    pp = _linea_del_screenshot(proyecto_factory)
    assert pp.costo_total_con_procesos == Decimal("2584.26")
    # 2,584.26 ÷ 25 piezas cobradas (la merma la absorben las que se venden).
    assert round(pp.costo_unitario_real, 2) == Decimal("103.37")
    # Y NO el costo del producto pelón, que era el bug.
    assert round(pp.costo_unitario_real, 2) != pp.costo_efectivo


def test_utilidad_unitaria_usa_el_costo_real(proyecto_factory):
    """Mostraba $175.06 (220 − 44.94); lo correcto es $116.63."""
    pp = _linea_del_screenshot(proyecto_factory)
    assert round(pp.utilidad_unitaria, 2) == Decimal("116.63")


def test_utilidad_unitaria_cuadra_con_la_utilidad_de_la_linea(proyecto_factory):
    """La prueba de que el reparto es el correcto: utilidad/pieza × cantidad
    tiene que dar la utilidad total que ya salía bien (y su margen del 53%)."""
    pp = _linea_del_screenshot(proyecto_factory)
    assert round(pp.utilidad_unitaria * pp.cantidad, 2) == round(pp.utilidad, 2)
    assert pp.margen_porcentaje == Decimal("53.0")


def test_costo_unitario_real_sin_cantidad_no_divide_por_cero(proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=0, merma=0)
    assert pp.costo_unitario_real == Decimal("0")


def test_la_tarjeta_calcula_el_costo_unitario_con_el_total(proyecto_factory):
    """Espejo en el JS: divide el costo TOTAL entre la cantidad cobrada, no
    muestra el costo del producto. Si alguien lo revierte, este test lo caza."""
    from pathlib import Path
    js = Path("el-taller/templates/proyectos/_form_productos_js.html").read_text(
        encoding="utf-8")
    assert "const cuReal = cant > 0 ? total / cant : 0;" in js
    assert "cpp.textContent = cuReal ? fmt(cuReal) : '—'" in js
    # La utilidad por pieza sale del costo REAL, ya no del producto pelón.
    assert "precioEfectivo(card) - cuReal" in js
    assert "precioEfectivo(card) - cu;" not in js


def test_el_pie_de_la_tarjeta_se_lee_mas_grande():
    """Oscar 2026-08-04: «el texto "Costo prod. … · unit. …/pz · …" debe de ser
    más grande» — pasó de 11px a text-xs/text-sm."""
    from pathlib import Path
    tpl = Path("el-taller/templates/proyectos/_producto_card.html").read_text(
        encoding="utf-8")
    pie = next(ln for ln in tpl.splitlines() if "Costo prod." in ln)
    assert "text-[11px]" not in pie
    assert "text-xs" in pie and "sm:text-sm" in pie


# ── 1 · En escritorio, el botón baja el archivo ───────────────────────────────


def test_compartir_pdf_solo_en_tactil():
    """macOS Chrome/Safari implementan `navigator.share`, así que sin este
    candado el botón dejaba de descargar en la computadora (Oscar: «en desktop
    este botón debería de bajar el archivo»)."""
    from pathlib import Path
    tpl = Path("el-taller/templates/cotizaciones/pdf.html").read_text(encoding="utf-8")
    assert "matchMedia('(pointer: coarse)')" in tpl
    assert "if (!tactil) return;" in tpl
    # La descarga real la sigue dando el `attachment` de la vista.
    assert 'id="lc-bajar"' in tpl and 'download="{{ nombre_archivo }}.pdf"' in tpl


def test_la_descarga_va_como_attachment(client, usuario_factory, monkeypatch,
                                        cliente_factory):
    """El camino de escritorio depende de que la vista mande `attachment`."""
    from apps.cotizaciones.models import Cotizacion
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    cot = Cotizacion.objects.create(
        cliente=cliente_factory(), titulo="Doc", creado_por=u)
    monkeypatch.setattr(
        "apps.cotizaciones.services.generar_pdf",
        lambda *_a, **_k: type("R", (), {"ok": True, "pdf_bytes": b"%PDF-1.4",
                                         "error": ""})(),
    )
    r = client.get(f"/cotizaciones/{cot.pk}/pdf/")
    assert r.status_code == 200
    assert r["Content-Disposition"].startswith("attachment;")


# ── 2 · Interlineado del documento más apretado ───────────────────────────────


def test_documento_con_interlineado_apretado():
    from pathlib import Path
    tpl = Path("el-taller/templates/cotizaciones/pdf.html").read_text(encoding="utf-8")
    assert "line-height: 1.02;" in tpl          # cuerpo (era 1.15)
    assert "line-height: 1.15;" not in tpl
    # Celdas de las tablas de conceptos: 2pt → 1pt (la fila «Total», que va
    # destacada, se queda con 2pt a propósito).
    assert "#cccccc; padding:2pt 5pt" not in tpl
    assert "#cccccc; padding:1pt 5pt" in tpl
    assert "margin-bottom:24pt" not in tpl      # encabezado y totales
    assert "margin-bottom:18pt" not in tpl      # tablas de conceptos


def test_el_estimador_de_paginacion_bajo_con_el_interlineado():
    """Si el documento se aprieta y el estimador no, cree que ocupa más de lo
    que ocupa y las notas se quedan flotando a media hoja."""
    from types import SimpleNamespace

    from apps.cotizaciones import services
    it = SimpleNamespace(detalle_lineas=["a", "b", "c"])
    alto = services._alto_bloque({"it": it, "extras": []})
    # 18 + 3×13 + 4 + 32 + 10 + overhead(60) = 163 (antes 98 + 42 + 60 = 200).
    assert alto == 163


def test_el_hueco_de_las_notas_sigue_topado():
    """El tope es lo que impide que un error de estimación abra medio hoja."""
    from apps.cotizaciones import services
    assert services._TOPE_HUECO_NOTAS_PT == 96


# ── 3 · Botón «pasar a esperando respuesta» ───────────────────────────────────


def _con_cotizacion(proyecto_factory, usuario):
    """Un proyecto en «Por cotizar» que ya tiene su v1."""
    from apps.cotizaciones.models import Cotizacion
    p = proyecto_factory(estado="por_cotizar")
    Cotizacion.objects.create(
        cliente=p.cliente, proyecto=p, titulo="v1", version=1, creado_por=usuario)
    return p


def test_sugerencia_aparece_con_cotizacion_y_estado_por_cotizar(
        client, usuario_factory, proyecto_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = _con_cotizacion(proyecto_factory, u)
    r = client.get(f"/proyectos/{p.pk}/")
    cuerpo = r.content.decode()
    assert "¿Pasar el proyecto a «Esperando respuesta»?" in cuerpo
    assert f'id="cot-sugerencia-{p.pk}"' in cuerpo
    # El ✓ reusa el endpoint que ya mueve el estado y repinta la barra de status.
    assert f'hx-target="#proyecto-status-bar-{p.pk}"' in cuerpo
    assert '{"estado": "esperando_respuesta"}' in cuerpo


def test_sugerencia_no_aparece_sin_cotizacion(client, usuario_factory,
                                              proyecto_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = proyecto_factory(estado="por_cotizar")
    r = client.get(f"/proyectos/{p.pk}/")
    assert "¿Pasar el proyecto a" not in r.content.decode()


def test_sugerencia_no_aparece_en_otro_estado(client, usuario_factory,
                                              proyecto_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = _con_cotizacion(proyecto_factory, u)
    p.estado = "esperando_respuesta"
    p.save(update_fields=["estado"])
    r = client.get(f"/proyectos/{p.pk}/")
    assert "¿Pasar el proyecto a" not in r.content.decode()


def test_sugerencia_aparece_al_generar_la_primera_cotizacion(
        client, usuario_factory, proyecto_factory, monkeypatch):
    """El flujo que pidió Oscar: «después de que se haya generado la primera
    cotización». El recuadro se repinta por HTMX y ahí ya trae la sugerencia."""
    from apps.cotizaciones.models import Cotizacion
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = proyecto_factory(estado="por_cotizar")

    def _generar(proyecto, actor):
        return Cotizacion.objects.create(
            cliente=proyecto.cliente, proyecto=proyecto, titulo="v1",
            version=1, creado_por=actor)

    monkeypatch.setattr(
        "apps.cotizaciones.services.generar_desde_proyecto", _generar)
    r = client.post(f"/proyectos/{p.pk}/cotizacion/generar",
                    HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert "¿Pasar el proyecto a «Esperando respuesta»?" in r.content.decode()


def test_el_check_cambia_el_estado_del_proyecto(client, usuario_factory,
                                                proyecto_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = _con_cotizacion(proyecto_factory, u)
    r = client.post(f"/proyectos/{p.pk}/cambiar-estado",
                    {"estado": "esperando_respuesta"}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200          # devuelve la barra de status repintada
    p.refresh_from_db()
    assert p.estado == "esperando_respuesta"


def test_sugerencia_oculta_para_quien_no_puede_cambiar_el_estado(
        client, usuario_factory, proyecto_factory):
    u = usuario_factory(rol="super_admin")
    p = _con_cotizacion(proyecto_factory, u)
    dis = usuario_factory(rol="disenador")
    from apps.los_proyectos.models import ProyectoAsignacion
    ProyectoAsignacion.objects.create(proyecto=p, usuario=dis, rol_en_proyecto="disenador")
    client.force_login(dis)
    r = client.get(f"/proyectos/{p.pk}/")
    assert "¿Pasar el proyecto a" not in r.content.decode()
