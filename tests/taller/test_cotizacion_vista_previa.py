"""Vista previa de la cotización antes de generar la versión siguiente.

Sprint 3 del reparto del 2026-08-28. Lo que hace delicado a este sprint es que
«Generar vN» es de lo poco que el sistema **congela** para siempre: crea la
versión que ve el cliente, reinicia el semáforo de estatus al primer paso y se
lleva una foto de los productos del proyecto (`ProyectoProductoVersion`) que
después alimenta las pestañas v1/v2/… del recuadro «Productos involucrados».

La vista previa tiene que enseñar **exactamente** ese documento. Una imitación
—armar un HTML parecido con los datos del proyecto— se vería bien y mentiría en
los detalles que importan: el redondeo de los impuestos, qué líneas se agrupan,
qué foto sale, cómo cae la paginación. Así que el preview **genera de verdad y
deshace**: lo que ves es lo que se va a generar, porque es lo que se generó.

Estos tests son la red permanente de esa decisión. Se agrupan en tres:

1. **El invariante del rollback** — que el preview no deje NADA. No basta con
   contar cotizaciones: se cuentan las cuatro tablas que el generado toca, y se
   vigila el efecto que NO es transaccional (el evento del Portavoz, que encola
   en Redis).
2. **La equivalencia** — que el preview y la versión real coincidan en lo que
   importa. Es la única defensa real contra que el preview se vuelva una
   imitación con los meses.
3. **La pantalla** — permisos, botones y que `pdf_ver` no haya cambiado.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture
def entorno(usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(
        nombre="Producción", defaults={"orden": 10})
    srv = Servicio.objects.create(
        nombre="Taza", precio_base="100", costo="30", categoria=cat)
    p = proyecto_factory(nombre="Branding Optimist", creado_por=admin)
    ProyectoProducto.objects.create(
        proyecto=p, servicio=srv, cantidad=3, incluir_en_calculo=True)
    return {"admin": admin, "p": p, "srv": srv}


@pytest.fixture
def tasa_iva_default():
    from ajustes.models.tasa import TasaImpositiva
    return TasaImpositiva.objects.create(
        nombre="IVA 16%", porcentaje=Decimal("16.00"),
        tipo="trasladado", aplicable_default=True, activa=True, orden=10,
    )


@pytest.fixture
def eventos(monkeypatch):
    """Captura los eventos del Portavoz que emite Cotizaciones.

    Se parchea `apps.cotizaciones.services.emitir` y no `lib.portavoz.emitir`
    porque el módulo importa el símbolo directamente: parchear el origen no
    alcanzaría a la referencia que ya tiene resuelta.
    """
    from apps.cotizaciones import services

    capturados = []
    monkeypatch.setattr(services, "emitir", lambda evt: capturados.append(evt))
    return capturados


def _conteos():
    """Las CUATRO tablas que toca generar una versión.

    Contar sólo `Cotizacion` dejaría fuera justo lo que más cuesta si se
    filtrara: la foto de los productos, que es la que alimenta las pestañas por
    versión del recuadro «Productos involucrados».
    """
    from apps.cotizaciones.models import (
        Cotizacion,
        CotizacionImpuesto,
        CotizacionItem,
    )
    from apps.los_proyectos.models import ProyectoProductoVersion

    return {
        "cotizaciones": Cotizacion.objects.count(),
        "items": CotizacionItem.objects.count(),
        "impuestos": CotizacionImpuesto.objects.count(),
        "fotos_version": ProyectoProductoVersion.objects.count(),
    }


# ── 1. El invariante del rollback ────────────────────────────────────────


def test_el_preview_no_deja_ninguna_fila(client, entorno, tasa_iva_default):
    """Ni cotización, ni líneas, ni impuestos, ni fotos de versión.

    Se cuentan las cuatro tablas: una de ellas quedándose escrita convertiría
    el preview en un generador silencioso de basura.
    """
    client.force_login(entorno["admin"])
    antes = _conteos()

    resp = client.get(reverse("proyectos-previsualizar-cotizacion",
                              args=[entorno["p"].pk]))

    assert resp.status_code == 200
    assert _conteos() == antes


def test_el_preview_no_consume_el_numero_de_version(client, entorno):
    """Tras varios previews, la versión que se genera de verdad es la que tocaba.

    El número sale de `ultima_cot.version + 1` DENTRO de la transacción, así que
    el rollback lo revierte. Si algún día se moviera a un contador aparte —una
    secuencia, un campo en el proyecto— este test es el que avisaría: las
    secuencias de Postgres no se reviertan con el rollback.
    """
    from apps.cotizaciones import services

    client.force_login(entorno["admin"])
    url = reverse("proyectos-previsualizar-cotizacion", args=[entorno["p"].pk])
    for _ in range(3):
        assert client.get(url).status_code == 200

    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    assert cot.version == 1


def test_el_preview_no_consume_el_codigo_correlativo(client, entorno):
    """El COT-YYYY-NNNN tampoco se gasta.

    Es el mismo argumento que la versión, pero por otro camino: el correlativo
    lo calcula `_generar_codigo` leyendo el máximo del año bajo
    `select_for_update`. Mientras salga de una lectura y no de una secuencia,
    el rollback lo devuelve.
    """
    from apps.cotizaciones import services

    client.force_login(entorno["admin"])
    url = reverse("proyectos-previsualizar-cotizacion", args=[entorno["p"].pk])
    for _ in range(2):
        client.get(url)

    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    assert cot.codigo.endswith("-0001"), cot.codigo


def test_el_preview_no_anuncia_una_cotizacion_que_no_existe(
        client, entorno, eventos):
    """El evento del Portavoz NO se emite en un preview.

    Éste es el efecto que el rollback no puede deshacer solo: `emitir` encola en
    Redis, que no es transaccional. Anunciar `cotizacion.generada` de una
    cotización revertida le mandaría a n8n el aviso de algo que no existe, y no
    hay forma de retirarlo.
    """
    client.force_login(entorno["admin"])

    client.get(reverse("proyectos-previsualizar-cotizacion",
                       args=[entorno["p"].pk]))

    tipos = [getattr(e, "tipo", "") for e in eventos]
    assert "cotizacion.generada" not in tipos, tipos


def test_generar_de_verdad_si_anuncia(entorno, eventos, django_capture_on_commit_callbacks):
    """La contraparte del test anterior: en el camino real el evento SÍ sale.

    Sin este test, «no se emite» se cumpliría igual de bien borrando el aviso
    por completo. El `django_capture_on_commit_callbacks` es necesario porque el
    evento se registra con `transaction.on_commit`, y el rollback de pytest hace
    que los callbacks no corran solos (Bug E de CLAUDE.md §14).
    """
    from apps.cotizaciones import services

    with django_capture_on_commit_callbacks(execute=True):
        services.generar_desde_proyecto(entorno["p"], entorno["admin"])

    tipos = [getattr(e, "tipo", "") for e in eventos]
    assert "cotizacion.generada" in tipos, tipos


def test_el_preview_no_baja_nada_de_drive(client, entorno, monkeypatch):
    """Candado: durante el preview no se toca la red.

    Hoy es cierto —desde S-Medios-V1 el documento lee las fotos del disco— y por
    eso la transacción es corta. Pero el preview mantiene abierta una
    transacción con el correlativo bloqueado: si algún día el armado del
    documento volviera a pedirle algo a Drive, un servicio ajeno lento dejaría
    esa transacción abierta y bloquearía los «Generar» de los demás. Este test
    es el que avisaría.
    """
    from lib import almacen

    def _prohibido(*a, **kw):  # pragma: no cover - sólo corre si hay regresión
        raise AssertionError(
            "El preview bajó un archivo del almacén: eso implica red dentro de "
            "una transacción abierta con el correlativo bloqueado.")

    monkeypatch.setattr(almacen, "leer", _prohibido)
    client.force_login(entorno["admin"])

    resp = client.get(reverse("proyectos-previsualizar-cotizacion",
                              args=[entorno["p"].pk]))

    assert resp.status_code == 200


# ── 2. La equivalencia preview ↔ versión real ────────────────────────────


def _cuerpo(html: str) -> str:
    """El documento sin el envoltorio de pantalla.

    La barra y el script de compartir son maquillaje de la vista previa; de
    `<div class="lc-hoja">` para abajo empieza el documento de verdad, que es lo
    que tiene que coincidir.
    """
    marca = '<div class="lc-hoja">'
    assert marca in html, "cambió el envoltorio del preview"
    return html.split(marca, 1)[1]


def test_el_preview_es_el_documento_real_no_una_imitacion(
        client, entorno, tasa_iva_default):
    """El cuerpo del preview y el de la versión ya generada son IDÉNTICOS.

    Éste es el candado que importa a largo plazo. Se compara el documento
    completo carácter por carácter —no un puñado de cifras— porque la forma en
    que esto se rompe no es que los totales salgan mal: es que alguien, dentro
    de unos meses, arme el preview por otro camino «que hace lo mismo». Con esta
    comparación eso no puede pasar en silencio.

    El documento va con el desglose prendido a propósito: así la comparación
    cubre también el cálculo fiscal (IVA y retenciones, con su redondeo), que es
    justo lo que una imitación arruinaría sin que se note.
    """
    from apps.cotizaciones import services

    v1 = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    v1.incluir_desglose = True
    v1.save(update_fields=["incluir_desglose"])

    client.force_login(entorno["admin"])
    html_preview = client.get(
        reverse("proyectos-previsualizar-cotizacion", args=[entorno["p"].pk]),
    ).content.decode()

    v2 = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    html_real = services.construir_html_pdf(v2, preview=True)

    assert v2.incluir_desglose, "el interruptor del documento debe heredarse"
    assert "Retención" in html_real, "el documento tiene que traer los impuestos"
    assert _cuerpo(html_preview) == _cuerpo(html_real)


def test_el_preview_ensena_la_version_que_se_va_a_generar(client, entorno):
    """Un proyecto con v1 ya generada previsualiza la v2, no otra vez la v1."""
    from apps.cotizaciones import services

    services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    client.force_login(entorno["admin"])

    html = client.get(
        reverse("proyectos-previsualizar-cotizacion", args=[entorno["p"].pk]),
    ).content.decode()

    assert "v2" in html


# ── 3. La pantalla ───────────────────────────────────────────────────────


def test_sin_permiso_de_crear_no_se_puede_ensayar(
        client, entorno, usuario_factory):
    """La vista previa es la antesala de generar, así que pide el permiso de
    CREAR y no el de ver: quien no puede generar no tiene por qué ensayarlo.

    El usuario del test SÍ puede ver el proyecto —está asignado a él—, así que
    el 403 sólo puede venir del gate de cotizaciones. Sin esa precaución el test
    daría verde con el gate quitado, porque lo pararía el filtro de proyecto: es
    justo el verde falso que la prueba de mutación destapó.
    """
    from apps.los_proyectos.models import ProyectoAsignacion

    from cuentas.models.permiso_usuario import PermisoUsuario
    from lib.permisos import puede_crear_cotizaciones, puede_ver_proyecto

    disenador = usuario_factory(rol="disenador")
    ProyectoAsignacion.objects.create(
        proyecto=entorno["p"], usuario=disenador, rol_en_proyecto="disenador")
    PermisoUsuario.objects.update_or_create(
        usuario=disenador, modulo="cotizaciones", permiso="crear",
        defaults={"activo": False})
    entorno["p"].refresh_from_db()
    assert puede_ver_proyecto(disenador, entorno["p"]), "debe poder ver el proyecto"
    assert not puede_crear_cotizaciones(disenador)
    client.force_login(disenador)

    resp = client.get(reverse("proyectos-previsualizar-cotizacion",
                              args=[entorno["p"].pk]))

    assert resp.status_code == 403


def test_la_barra_del_preview_ofrece_generar_y_generar_y_enviar(
        client, entorno):
    """Los dos botones que pidió Oscar, y ninguno de ellos es «Bajar PDF».

    Bajar el PDF de una versión que todavía no existe daría 404: el documento
    real lo genera Google a partir de una cotización guardada. El template ya
    condiciona ese botón a `url_descargar`, así que basta con no dárselo.
    """
    client.force_login(entorno["admin"])

    html = client.get(
        reverse("proyectos-previsualizar-cotizacion", args=[entorno["p"].pk]),
    ).content.decode()

    assert reverse("proyectos-generar-cotizacion", args=[entorno["p"].pk]) in html
    assert "Generar y enviar" in html
    assert "Bajar PDF" not in html


def test_los_botones_del_preview_son_formularios_no_htmx(client, entorno):
    """El documento es una página completa que NO extiende `base.html`: ahí no
    hay htmx cargado ni `#modal-slot`. Los botones tienen que ser formularios
    clásicos con su token, o no harían nada."""
    client.force_login(entorno["admin"])

    html = client.get(
        reverse("proyectos-previsualizar-cotizacion", args=[entorno["p"].pk]),
    ).content.decode()

    assert "csrfmiddlewaretoken" in html
    assert 'method="post"' in html


def test_generar_y_enviar_genera_y_lleva_al_envio(client, entorno):
    """El orden importa: primero se confirma la versión, después se abre el
    correo. Si el correo fallara, la versión existe y se reintenta desde el
    recuadro — nunca al revés."""
    from apps.cotizaciones.models import Cotizacion

    client.force_login(entorno["admin"])

    resp = client.post(
        reverse("proyectos-generar-cotizacion", args=[entorno["p"].pk]),
        {"y_enviar": "1"},
    )

    cot = Cotizacion.objects.filter(proyecto=entorno["p"], version=1).first()
    assert cot is not None, "la versión tiene que quedar creada"
    assert resp.status_code == 302
    assert f"enviar_cot={cot.pk}" in resp["Location"]


def test_generar_sin_enviar_vuelve_al_proyecto(client, entorno):
    """Sin `y_enviar`, el botón se comporta como siempre."""
    client.force_login(entorno["admin"])

    resp = client.post(
        reverse("proyectos-generar-cotizacion", args=[entorno["p"].pk]))

    assert resp.status_code == 302
    assert "enviar_cot" not in resp["Location"]


def test_al_volver_de_generar_y_enviar_se_abre_el_modal(client, entorno):
    """El `?enviar_cot=` que deja «Generar y enviar» abre el modal al cargar."""
    from apps.cotizaciones import services

    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    client.force_login(entorno["admin"])

    html = client.get(
        reverse("proyectos-detalle", args=[entorno["p"].pk]),
        {"enviar_cot": cot.pk},
    ).content.decode()

    assert reverse("cotizaciones:enviar", args=[cot.pk]) in html


def test_un_enviar_cot_basura_no_tumba_la_pagina(client, entorno):
    """`?enviar_cot=abc` no puede reventar el detalle del proyecto.

    El valor viene de la barra de direcciones, así que cualquiera lo puede
    escribir. Si llegara crudo a `{% templatetag openblock %} url {% templatetag closeblock %}`, un texto que no sea número
    levanta `NoReverseMatch` y se cae la página entera — no el recuadro: la
    página. Por eso se valida en la vista.
    """
    client.force_login(entorno["admin"])

    for valor in ("abc", "", "1'; DROP", "-5", "99999"):
        resp = client.get(reverse("proyectos-detalle", args=[entorno["p"].pk]),
                          {"enviar_cot": valor})
        assert resp.status_code == 200, f"{valor!r} tumbó el detalle"


def test_no_se_abre_el_envio_de_una_cotizacion_de_otro_proyecto(
        client, entorno, proyecto_factory):
    """La pk tiene que ser de ESTE proyecto.

    Sin la comprobación, `?enviar_cot=` de una cotización ajena abriría su
    modal de envío desde un proyecto que no es el suyo.
    """
    from apps.cotizaciones import services

    otro = proyecto_factory(nombre="Otro proyecto", creado_por=entorno["admin"])
    ajena = services.generar_desde_proyecto(otro, entorno["admin"])
    client.force_login(entorno["admin"])

    html = client.get(
        reverse("proyectos-detalle", args=[entorno["p"].pk]),
        {"enviar_cot": ajena.pk},
    ).content.decode()

    assert reverse("cotizaciones:enviar", args=[ajena.pk]) not in html


def test_el_recuadro_del_proyecto_ofrece_la_vista_previa(client, entorno):
    """El botón que la abre vive junto a «Generar vN»."""
    client.force_login(entorno["admin"])

    html = client.get(
        reverse("proyectos-detalle", args=[entorno["p"].pk]),
    ).content.decode()

    assert reverse("proyectos-previsualizar-cotizacion",
                   args=[entorno["p"].pk]) in html


def test_la_vista_de_siempre_no_cambio(client, entorno):
    """`cotizaciones:ver` sigue trayendo «Bajar PDF» y ninguna acción nueva.

    Los parámetros que se le agregaron a `construir_html_pdf` tienen default, y
    este test es el que exige que ese default siga preservando la pantalla que
    ya existía.
    """
    from apps.cotizaciones import services

    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])
    client.force_login(entorno["admin"])

    html = client.get(
        reverse("cotizaciones:ver", args=[cot.pk])).content.decode()

    assert "Bajar PDF" in html
    assert "Generar y enviar" not in html


def test_el_documento_del_pdf_real_no_lleva_la_barra(entorno):
    """Sin `preview`, el HTML que se le manda a Google va limpio: ni envoltorio
    ni botones. Es lo que separa maquillar la pantalla de tocar el documento."""
    from apps.cotizaciones import services

    cot = services.generar_desde_proyecto(entorno["p"], entorno["admin"])

    html = services.construir_html_pdf(cot)

    assert "lc-barra" not in html
    assert "csrfmiddlewaretoken" not in html


def test_hay_un_solo_documento_de_cotizacion(entorno):
    """Candado anti-divergencia: no puede aparecer una segunda copia de la
    plantilla del documento «para el preview».

    Es el mismo criterio con el que el semáforo de la cotización se extrajo a un
    partial compartido (LC 2026-08-23): dos copias no divergen el primer día,
    divergen en tres meses, y para entonces el preview miente.
    """
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    copias = sorted(
        p.relative_to(raiz).as_posix()
        for p in raiz.rglob("templates/cotizaciones/*.html")
        if p.name.startswith("pdf") or "documento_pdf" in p.name
    )

    assert copias == ["el-taller/templates/cotizaciones/pdf.html"], copias
