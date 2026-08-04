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


def test_costo_unitario_real_suma_impresion_y_procesos_divididos(proyecto_factory):
    """El caso del screenshot: mostraba $44.94 (el producto pelón) y lo correcto
    es $89.11 — producto + impresión por pieza + el proceso fijo dividido."""
    pp = _linea_del_screenshot(proyecto_factory)
    assert pp.costo_total_con_procesos == Decimal("2584.26")
    # 44.94 (producto) + 39.00 (impresión/pz) + 150/29 (fijo dividido) = 89.11
    assert round(pp.costo_unitario_real, 2) == Decimal("89.11")
    # Y NO el costo del producto pelón, que era el bug.
    assert round(pp.costo_unitario_real, 2) != pp.costo_efectivo


def test_el_divisor_son_las_piezas_producidas_no_las_cobradas(proyecto_factory):
    """Oscar: «el costo unitario del producto no debe de sumar la merma diferida —
    o sea cada pz de merma tiene el mismo costo unitario». El costo por pieza sale
    de dividir entre las 29 producidas, no entre las 25 que se cobran."""
    pp = _linea_del_screenshot(proyecto_factory)
    piezas = pp.cantidad + pp.merma
    assert round(pp.costo_unitario_real * piezas, 2) == pp.costo_total_con_procesos
    # Repartirlo entre las cobradas daría 103.37 — eso amortizaría la merma.
    assert round(pp.costo_unitario_real, 2) != Decimal("103.37")


def test_utilidad_unitaria_usa_el_costo_real(proyecto_factory):
    """Mostraba $175.06 (220 − 44.94); lo correcto es $130.89 (220 − 89.11)."""
    pp = _linea_del_screenshot(proyecto_factory)
    assert round(pp.utilidad_unitaria, 2) == Decimal("130.89")


def test_la_merma_sigue_pegandole_a_la_utilidad_total(proyecto_factory):
    """La merma NO se amortiza por pieza, así que su pérdida tiene que seguir
    apareciendo en los totales de la derecha (que ya salían bien). Y por eso
    utilidad/pieza × cantidad NO da la utilidad total: es esperado."""
    pp = _linea_del_screenshot(proyecto_factory)
    assert round(pp.utilidad, 2) == Decimal("2915.74")
    assert pp.margen_porcentaje == Decimal("53.0")
    assert round(pp.utilidad_unitaria * pp.cantidad, 2) > round(pp.utilidad, 2)


def test_costo_unitario_real_sin_piezas_no_divide_por_cero(proyecto_factory):
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=0, merma=0)
    assert pp.costo_unitario_real == Decimal("0")


def test_solo_merma_sin_cantidad_igual_calcula_el_costo_por_pieza(proyecto_factory):
    """Si sólo hay merma (caso raro), cada pieza sigue teniendo su costo."""
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=0, merma=4,
        costo_unitario=Decimal("50.00"))
    assert pp.costo_unitario_real == Decimal("50.00")


def test_la_tarjeta_calcula_el_costo_unitario_con_el_total(proyecto_factory):
    """Espejo en el JS: divide el costo TOTAL entre la cantidad cobrada, no
    muestra el costo del producto. Si alguien lo revierte, este test lo caza."""
    from pathlib import Path
    js = Path("el-taller/templates/proyectos/_form_productos_js.html").read_text(
        encoding="utf-8")
    assert "const cuReal = piezas > 0 ? total / piezas : 0;" in js
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
    pie = next(ln for ln in tpl.splitlines()
               if "Costo prod." in ln and "data-costo-total" in ln)
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


# ── (1) El recuadro «Descripción» del proyecto ahora se llama «Notas» ─────────


def test_el_recuadro_del_proyecto_se_llama_notas(client, usuario_factory,
                                                 proyecto_factory):
    """Oscar: «cambiar el recuadro descripción a notas». El campo del modelo
    sigue siendo `descripcion` — sólo cambia la etiqueta."""
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    p = proyecto_factory(descripcion="Algo escrito")
    cuerpo = client.get(f"/proyectos/{p.pk}/").content.decode()
    assert 'id_descripcion" class="mb-1.5 block' in cuerpo.replace('for="', 'for="')
    assert ">Notas</label>" in cuerpo
    # Y el campo sigue posteándose con su nombre real.
    assert 'name="descripcion"' in cuerpo


# ── (2a) El «+» verde de proceso de venta vive en la fila 1 ───────────────────


def test_el_boton_verde_es_un_mas_en_la_primera_fila():
    """Oscar: «minimizar a solo un + más grande y poner forzoso en la misma línea
    que categoría, producto, cantidad, merma, precio unitario. Absorber espacio de
    categoría»."""
    from pathlib import Path
    tpl = Path("el-taller/templates/proyectos/_producto_card.html").read_text(
        encoding="utf-8")
    # Una sexta columna en la fila 1 y Categoría cede espacio (1fr → 0.7fr).
    assert "md:grid-cols-[0.7fr_1.4fr_72px_72px_120px_36px]" in tpl
    # El botón quedó como un «+» grande, ya no «+ Proceso».
    ini = tpl.index("venta-add")
    boton = tpl[ini:tpl.index("</button>", ini) + len("</button>")]
    assert ">+</button>" in boton
    assert "+ Proceso" not in boton
    assert "text-xl" in boton
    # Y está DENTRO de la fila 1: aparece antes del contenedor de la lista.
    assert tpl.index("venta-add") < tpl.index("<div data-ventas")
    # Sin líneas de venta, el contenedor de la lista no ocupa su hueco.
    assert "[&:not(:has(.venta-fila))]:hidden" in tpl


# ── (2b) «Notas» → «Descripción», multilínea y ligada a la cotización ─────────


def test_la_descripcion_de_la_linea_es_multilinea_y_crece():
    from pathlib import Path

    from apps.los_proyectos.forms import ProyectoProductoForm
    from django import forms as dj_forms
    f = ProyectoProductoForm()
    assert isinstance(f.fields["nota"].widget, dj_forms.Textarea)
    assert f.fields["nota"].widget.attrs.get("data-autogrow") == "1"
    assert f.fields["nota"].label == "Descripción"
    # Ya no es un CharField de 200: acepta un texto largo de varias líneas.
    from apps.los_proyectos.models import ProyectoProducto
    assert ProyectoProducto._meta.get_field("nota").max_length is None
    tpl = Path("el-taller/templates/proyectos/_producto_card.html").read_text(
        encoding="utf-8")
    assert ">Descripción</label>" in tpl
    assert ">Notas</label>" not in tpl
    # El renglón alinea al fondo: al crecer, la etiqueta sube.
    assert "md:grid-cols-[1.4fr_120px_1.6fr] md:items-end" in tpl
    js = Path("el-taller/templates/proyectos/_form_productos_js.html").read_text(
        encoding="utf-8")
    assert "function autogrow(ta)" in js
    assert "textarea[data-autogrow]" in js


def test_la_descripcion_de_la_tarjeta_es_la_especificacion_de_la_cotizacion(
        proyecto_factory):
    """Oscar: «ligar a la especificación del elemento que se pone en la
    cotización». Lo que se escribe en la tarjeta es lo que sale en el documento."""
    from apps.cotizaciones import descripcion
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=105,
        nota="Gorras de gabardina\nColor: Beige / Terracota",
    )
    texto = descripcion.descripcion_para(pp)
    assert texto.splitlines() == [
        "105 pz", "Gorras de gabardina", "Color: Beige / Terracota"]


def test_la_descripcion_de_la_tarjeta_gana_sobre_la_version_anterior(
        proyecto_factory):
    """Si no ganara, «ligar» no significaría nada: la herencia de la versión
    previa se comería lo que se acaba de escribir en la tarjeta."""
    from apps.cotizaciones import descripcion
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=110, nota="Especificación nueva")
    texto = descripcion.descripcion_para(pp, previo="105 pz\nTexto viejo de la v1")
    assert texto == "110 pz\nEspecificación nueva"


def test_sin_descripcion_en_la_tarjeta_se_hereda_como_antes(proyecto_factory):
    """Cero regresión: la línea sin descripción propia sigue heredando el texto
    editado en la versión anterior, con las piezas al día."""
    from apps.cotizaciones import descripcion
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=110, nota="")
    texto = descripcion.descripcion_para(
        pp, previo="105 pz (3 colores, 35 pz c/u)\nFrontal: Mantarraya")
    assert texto == "110 pz (3 colores, 35 pz c/u)\nFrontal: Mantarraya"


def test_el_esqueleto_no_duplica_las_piezas_si_ya_vienen_en_el_texto(
        proyecto_factory):
    """La especificación que baja de una cotización ya arranca con «N pz (…)».
    Se le refresca el conteo, **conservando el paréntesis**, en vez de anteponer
    otro renglón de piezas."""
    from apps.cotizaciones import descripcion
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=110,
        nota="105 pz (3 colores, 35 pz c/u)\nFrontal: Mantarraya",
    )
    assert descripcion.esqueleto(pp) == (
        "110 pz (3 colores, 35 pz c/u)\nFrontal: Mantarraya")


# ── Migración: la especificación ya escrita baja a la tarjeta ─────────────────


def _correr_migracion_0029():
    """Corre la data migration sobre los modelos actuales (misma forma)."""
    import importlib

    from django.apps import apps as registro
    mod = importlib.import_module(
        "apps.los_proyectos.migrations.0029_descripcion_desde_cotizaciones")
    mod.poblar(registro, None)


def test_migracion_baja_la_especificacion_de_la_ultima_version(
        proyecto_factory, usuario_factory):
    """Oscar: «sustituir lo que ya se escribió en especificaciones de varias
    cotizaciones y eso es el nuevo campo de notas»."""
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    from apps.los_proyectos.models import ProyectoProducto
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    srv = _servicio()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=srv, cantidad=25, nota="nota interna vieja")
    for v, texto in ((1, "25 pz\nTexto de la v1"), (2, "25 pz\nTexto de la v2")):
        cot = Cotizacion.objects.create(
            cliente=p.cliente, proyecto=p, titulo=f"v{v}", version=v, creado_por=u)
        CotizacionItem.objects.create(
            cotizacion=cot, servicio=srv, descripcion=texto,
            cantidad=25, precio_unitario=Decimal("220.00"))
    _correr_migracion_0029()
    pp.refresh_from_db()
    # Gana la versión MÁS RECIENTE con texto, y la nota interna se fue.
    assert pp.nota == "25 pz\nTexto de la v2"


def test_migracion_borra_la_nota_vieja_sin_cotizacion(proyecto_factory):
    """«Las notas anteriores por producto se pueden eliminar» — sin especificación
    de dónde bajar, la línea queda limpia."""
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=_servicio(), cantidad=5, nota="NOTA INTERNA SECRETA")
    _correr_migracion_0029()
    pp.refresh_from_db()
    assert pp.nota == ""


def test_migracion_empareja_por_nombre_si_cambio_el_producto(
        proyecto_factory, usuario_factory):
    """Respaldo de `indice_previo`: si a la línea le cambiaron el producto, el
    texto se encuentra por el nombre del concepto."""
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    from apps.los_proyectos.models import ProyectoProducto
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    srv_viejo = _servicio("Playera vieja")
    srv_nuevo = _servicio("Playera nueva")
    cot = Cotizacion.objects.create(
        cliente=p.cliente, proyecto=p, titulo="v1", version=1, creado_por=u)
    CotizacionItem.objects.create(
        cotizacion=cot, servicio=srv_viejo, concepto="Gorras MAU",
        descripcion="105 pz\nGorras de gabardina", cantidad=105,
        precio_unitario=Decimal("100.00"))
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=srv_nuevo, cantidad=105,
        nombre_proyecto="Gorras MAU")
    _correr_migracion_0029()
    pp.refresh_from_db()
    assert pp.nota == "105 pz\nGorras de gabardina"


def test_migracion_es_idempotente(proyecto_factory, usuario_factory):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    from apps.los_proyectos.models import ProyectoProducto
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory()
    srv = _servicio()
    pp = ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=10)
    cot = Cotizacion.objects.create(
        cliente=p.cliente, proyecto=p, titulo="v1", version=1, creado_por=u)
    CotizacionItem.objects.create(
        cotizacion=cot, servicio=srv, descripcion="10 pz\nEspecificación",
        cantidad=10, precio_unitario=Decimal("50.00"))
    _correr_migracion_0029()
    _correr_migracion_0029()
    pp.refresh_from_db()
    assert pp.nota == "10 pz\nEspecificación"


def test_sin_descripcion_ni_previo_cae_al_catalogo(proyecto_factory):
    from apps.cotizaciones import descripcion
    from apps.los_proyectos.models import ProyectoProducto
    srv = _servicio()
    srv.descripcion_default = "Playera 100% algodón"
    srv.save(update_fields=["descripcion_default"])
    p = proyecto_factory()
    pp = ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=20)
    assert descripcion.descripcion_para(pp) == "20 pz\nPlayera 100% algodón"
