"""Services de La Facturación.

Transiciones de estado, integración con Tesorería (cobros) y emisión
de eventos Portavoz. Los asientos contables los genera `signals.py`
desde la app `contaduria` para mantener la dependencia unidireccional.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import Factura, FacturaImpuesto, FacturaItem

CERO = Decimal("0.00")


def _emitir(tipo: str, fac: Factura, actor, payload_extra: dict | None = None):
    payload = {
        "factura_id": fac.id,
        "codigo": fac.codigo,
        "cliente_id": fac.cliente_id,
        "estado": fac.estado,
    }
    if payload_extra:
        payload.update(payload_extra)
    emitir(EventoPortavoz(
        tipo=tipo,
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload=payload,
    ))


def emitir_creada(fac: Factura, actor):
    _emitir("factura.creada", fac, actor, {"titulo": fac.titulo})


def emitir_actualizada(fac: Factura, actor):
    _emitir("factura.actualizada", fac, actor)


def construir_html_pdf(fac: Factura) -> str:
    """Renderiza el HTML imprimible de la factura (template `pdf.html`)."""
    from django.template.loader import render_to_string
    return render_to_string("facturacion/pdf.html", {
        "fac": fac,
        "items": list(fac.items.select_related("servicio", "unidad_fk").all()),
        "totales": fac.calcular_totales(),
    })


def enviar_por_correo(fac: Factura, actor):
    """Manda la factura por El Cartero con el PDF adjunto (best-effort).

    Destinatario: el correo del cliente. Devuelve `lib.cartero.ResultadoCorreo`.
    Genera el PDF si Drive está disponible; nunca lanza."""
    from lib import cartero

    destino = (getattr(fac.cliente, "email_contacto", "") or "").strip()
    if not destino:
        return cartero.ResultadoCorreo(ok=False, error="El cliente no tiene correo.")

    adjuntos = []
    pdf_bytes = pdf_bytes_almacenado(fac)
    if pdf_bytes:
        adjuntos.append(cartero.Adjunto(
            nombre=f"{fac.codigo}.pdf", contenido=pdf_bytes, mime="application/pdf"))

    asunto, html = _render_correo(fac)
    return cartero.enviar(destinatario=destino, asunto=asunto, html=html, adjuntos=adjuntos)


def _render_correo(fac: Factura) -> tuple[str, str]:
    """(asunto, cuerpo_html) desde la PlantillaCorreo editable; fallback al
    template de archivo."""
    from cuentas.templatetags.forms_helpers import dinero
    totales = fac.calcular_totales()
    contexto = {
        "codigo": fac.codigo,
        "titulo": fac.titulo,
        "cliente": fac.cliente.razon_social,
        "total": dinero(totales["total"]),
        "moneda": fac.moneda,
        "fecha_emision": fac.fecha_emision.strftime("%d/%m/%Y") if fac.fecha_emision else "",
        "vencimiento": fac.fecha_vencimiento.strftime("%d/%m/%Y") if fac.fecha_vencimiento else "",
        "notas": fac.notas or "",
    }
    try:
        from ajustes.models import PlantillaCorreo
        return PlantillaCorreo.obtener("factura").render(contexto)
    except Exception:  # noqa: BLE001
        from django.template.loader import render_to_string
        html = render_to_string("facturacion/email.html", {"fac": fac})
        return f"Factura {fac.codigo} · Learning Center", html


# --- CFDI del PAC (LC #162): almacenar PDF + XML, no generar --------------

def _bytes_almacenados(file_id: str) -> bytes | None:
    """Bytes de un archivo de El Almacén por su llave, o None. Nunca lanza."""
    if not file_id:
        return None
    try:
        from lib import almacen
        contenido, _mime, _nombre = almacen.leer(file_id)
        return contenido
    except Exception:  # noqa: BLE001
        return None


def pdf_bytes_almacenado(fac: Factura) -> bytes | None:
    """Bytes del PDF del CFDI almacenado (para adjuntar en correos). Nunca lanza."""
    return _bytes_almacenados(fac.pdf_file_id)


def almacenar_cfdi(fac: Factura, *, pdf_file=None, xml_file=None,
                   cfdi_uuid: str = "", actor=None) -> dict:
    """Almacena el CFDI del PAC (PDF y/o XML) en Drive (subcarpeta «Facturas»)
    y lo liga a la factura. Reemplaza el archivo previo del mismo tipo y guarda
    el folio fiscal (UUID) si se provee. Best-effort por archivo — nunca lanza.
    Devuelve {ok, guardados: [...], errores: [...]}."""
    import contextlib

    from lib.adjuntos import subir

    guardados: list[str] = []
    errores: list[str] = []
    update_fields: list[str] = []

    def _reemplazar(prev_id: str):
        # El CFDI reemplazado sí se borra (es el único caso del repo): una foto de
        # producto NUNCA se borra, porque su llave puede estar congelada en una
        # cotización ya enviada. `espejo=True` se lleva también la copia de Drive.
        if prev_id:
            with contextlib.suppress(Exception):
                from lib import almacen

                almacen.borrar(prev_id, espejo=True)

    if pdf_file is not None:
        res = subir(pdf_file, subcarpeta="Facturas")
        if res.ok and res.data:
            _reemplazar(fac.pdf_file_id)
            fac.pdf_file_id = res.data.get("id", "")
            fac.pdf_url = res.data.get("webViewLink", "")
            update_fields += ["pdf_file_id", "pdf_url"]
            guardados.append("PDF")
        else:
            errores.append(f"PDF: {res.error}")

    if xml_file is not None:
        res = subir(xml_file, subcarpeta="Facturas")
        if res.ok and res.data:
            _reemplazar(fac.xml_file_id)
            fac.xml_file_id = res.data.get("id", "")
            fac.xml_url = res.data.get("webViewLink", "")
            update_fields += ["xml_file_id", "xml_url"]
            guardados.append("XML")
        else:
            errores.append(f"XML: {res.error}")

    cfdi_uuid = (cfdi_uuid or "").strip()
    if cfdi_uuid:
        fac.cfdi_uuid = cfdi_uuid[:40]
        update_fields.append("cfdi_uuid")

    if guardados or cfdi_uuid:
        fac.cfdi_almacenado_en = timezone.now()
        update_fields.append("cfdi_almacenado_en")
        fac.save(update_fields=list(dict.fromkeys(update_fields)))
        _emitir("factura.cfdi_almacenado", fac, actor,
                {"guardados": guardados, "cfdi_uuid": fac.cfdi_uuid})

    return {
        "ok": bool(guardados or cfdi_uuid) and not errores,
        "guardados": guardados,
        "errores": errores,
    }


def crear_desde_cotizacion(cotizacion, actor) -> Factura:
    """Clona items+impuestos+vínculo, hereda datos comerciales. Estado
    borrador. Vencimiento por default 30 días desde hoy."""
    with transaction.atomic():
        fac = Factura.objects.create(
            cliente=cotizacion.cliente,
            proyecto=cotizacion.proyecto,
            cotizacion_origen=cotizacion,
            titulo=cotizacion.titulo[:200],
            estado="borrador",
            fecha_emision=date.today(),
            fecha_vencimiento=date.today() + timedelta(days=30),
            moneda=cotizacion.moneda,
            regimen_fiscal=cotizacion.regimen_fiscal,
            descuento_global_porcentaje=cotizacion.descuento_global_porcentaje,
            notas=cotizacion.notas,
            terminos=cotizacion.terminos,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        for it in cotizacion.items.all():
            FacturaItem.objects.create(
                factura=fac,
                orden=it.orden,
                servicio=it.servicio,
                # LC 2026-07: la factura lleva el NOMBRE del concepto, no el
                # bloque de especificaciones de la cotización (material, color,
                # branding) — eso es material de venta, no de facturación.
                descripcion=it.concepto_visible or it.descripcion,
                cantidad=it.cantidad,
                unidad=it.unidad,
                precio_unitario=it.precio_unitario,
                descuento_porcentaje=it.descuento_porcentaje,
            )
        for ci in cotizacion.impuestos.all():
            FacturaImpuesto.objects.create(factura=fac, tasa=ci.tasa)
    _emitir("factura.creada", fac, actor,
            {"titulo": fac.titulo, "cotizacion_id": cotizacion.id})
    return fac


def _resolver_monto_base(fac: Factura, monto=None) -> Decimal:
    """Monto base (subtotal sin impuestos) de una factura por CONCEPTO. Prioridad:
    `monto` explícito → subtotal de la cotización origen → monto calculado del
    proyecto. NUNCA copia el desglose de la cotización (decisión Oscar 2026-07:
    la factura es por concepto + monto global; para traer las líneas de la
    cotización se usa el botón «Sustituir» del formulario)."""
    if monto is not None:
        base = Decimal(str(monto)).quantize(Decimal("0.01"))
        if base > CERO:
            return base
    cot = fac.cotizacion_origen
    if cot is not None:
        sub = cot.calcular_totales().get("subtotal_items") or CERO
        base = Decimal(str(sub)).quantize(Decimal("0.01"))
        if base > CERO:
            return base
    proy = fac.proyecto
    if proy is not None:
        base = Decimal(str(getattr(proy, "monto_calculado", None) or 0)).quantize(Decimal("0.01"))
        if base > CERO:
            return base
    return CERO


def fijar_linea_concepto(fac: Factura, *, monto=None) -> Decimal:
    """Modo «monto» (LC 2026-07, decisión Oscar «una línea automática»): deja la
    factura con UNA sola línea-concepto (descripción = concepto, precio = monto
    base). REEMPLAZA todas las líneas previas. El monto se resuelve con
    `_resolver_monto_base` (anti-$0). Devuelve el monto base aplicado."""
    base = _resolver_monto_base(fac, monto)
    with transaction.atomic():
        fac.items.all().delete()
        if base > CERO:
            _sintetizar_linea(fac, base)
    return base


def _divisor_total(fac: Factura) -> Decimal:
    """Cuánto vale el total por cada peso de base, con el régimen y las tasas
    que tiene ESTA factura. Total = base × divisor."""
    factor = Decimal("1")
    if fac.regimen_fiscal == "honorarios":
        from lib.fiscal import desglose_honorarios
        d = desglose_honorarios(Decimal("10000.00"))
        factor = d["total"] / Decimal("10000.00")
    elif fac.regimen_fiscal != "exento":
        for fi in fac.impuestos.select_related("tasa").all():
            pct = (fi.tasa.porcentaje or CERO) / Decimal("100")
            factor += -pct if fi.tasa.tipo == "retencion" else pct
    desc = Decimal("1") - (fac.descuento_global_porcentaje or CERO) / Decimal("100")
    parcial = (fac.porcentaje_a_facturar or Decimal("100")) / Decimal("100")
    divisor = factor * desc * parcial
    return divisor if divisor > 0 else Decimal("1")


def fijar_total_con_impuestos(fac: Factura, total_deseado) -> Decimal:
    """Deja la factura con UNA línea-concepto cuyo TOTAL (ya con IVA y
    retenciones) es exactamente `total_deseado`.

    Oscar 2026-07-25: al capturar facturas viejas se dicta el importe final del
    CFDI, no la base. Aquí se invierte el cálculo: base = total ÷ divisor, y se
    corrige el redondeo comparando contra `calcular_totales` (los impuestos se
    redondean al centavo por separado, así que la división sola puede quedar a
    uno o dos centavos). Devuelve la base aplicada.
    """
    objetivo = Decimal(str(total_deseado)).quantize(Decimal("0.01"))
    divisor = _divisor_total(fac)
    base = (objetivo / divisor).quantize(Decimal("0.01"))
    for _ in range(4):
        fijar_linea_concepto(fac, monto=base)
        diferencia = objetivo - fac.calcular_totales()["total"]
        if abs(diferencia) < Decimal("0.005"):
            break
        base = (base + diferencia / divisor).quantize(Decimal("0.01"))
    return base


def asegurar_lineas_desde_origen(fac: Factura, *, monto_fallback=None) -> bool:
    """Anti-$0 para el modo «desglose»: si la factura quedó SIN líneas, sintetiza
    UNA línea-concepto con su monto base (`monto_fallback` explícito → subtotal
    de la cotización → monto del proyecto). NO copia múltiples líneas de la
    cotización (para eso está el botón «Sustituir»). Idempotente: no toca nada si
    ya hay líneas. Devuelve True si agregó la línea."""
    if fac.items.exists():
        return False
    base = _resolver_monto_base(fac, monto_fallback)
    if base > CERO:
        _sintetizar_linea(fac, base)
        return True
    return False


def _sintetizar_linea(fac: Factura, base: Decimal) -> None:
    """Crea UNA línea cantidad=1 con el concepto de la factura como descripción."""
    concepto = (fac.concepto or "").strip()
    if not concepto:
        concepto = (
            f"Producción de elementos para {fac.proyecto.nombre}"
            if fac.proyecto_id else "Facturación"
        )
    FacturaItem.objects.create(
        factura=fac,
        orden=0,
        descripcion=concepto[:500],
        cantidad=Decimal("1.00"),
        unidad="servicio",
        precio_unitario=base,
        descuento_porcentaje=CERO,
    )


def borrar_cfdi_archivo(fac: Factura, tipo: str) -> None:
    """Borra el PDF o XML del CFDI (El Almacén, su espejo en Drive y los campos
    de la factura). Best-effort; nunca lanza. `tipo` ∈ {'pdf', 'xml'}."""
    import contextlib

    from lib import almacen

    campos: list[str] = []
    if tipo == "pdf" and fac.pdf_file_id:
        with contextlib.suppress(Exception):
            almacen.borrar(fac.pdf_file_id, espejo=True)
        fac.pdf_file_id = ""
        fac.pdf_url = ""
        campos = ["pdf_file_id", "pdf_url"]
    elif tipo == "xml" and fac.xml_file_id:
        with contextlib.suppress(Exception):
            almacen.borrar(fac.xml_file_id, espejo=True)
        fac.xml_file_id = ""
        fac.xml_url = ""
        campos = ["xml_file_id", "xml_url"]
    if campos:
        fac.save(update_fields=campos)


def emitir_factura(fac: Factura, actor) -> Factura:
    """borrador → emitida. Dispara el asiento via signal post_save."""
    if fac.estado != "borrador":
        raise ValueError("Solo se puede emitir una factura en borrador.")
    with transaction.atomic():
        fac.estado = "emitida"
        fac.emitida_en = timezone.now()
        fac.emitida_por = actor if getattr(actor, "is_authenticated", False) else None
        fac.save(update_fields=["estado", "emitida_en", "emitida_por", "actualizado_en"])
    _emitir("factura.emitida", fac, actor)
    return fac


def registrar_cobro(
    fac: Factura,
    *,
    monto,
    fecha,
    metodo: str,
    actor,
    banco_o_caja: str = "banco",  # noqa: ARG001 (futuro: forzar slot caja vs banco)
    folio: str = "",
    nota: str = "",
):
    """Crea un `tesoreria.Ingreso` vinculado y recalcula `monto_cobrado`.
    Transiciona a cobrada_parcial / cobrada_total según corresponda.

    `folio` se guarda en `referencia_externa`; `nota` se anexa a la descripción
    (sección "Referencia" del modal de cobro, ticket LC 2026-06-29).
    """
    if fac.estado not in {"emitida", "cobrada_parcial"}:
        raise ValueError("Solo se puede cobrar una factura emitida o parcialmente cobrada.")
    monto = Decimal(str(monto)).quantize(Decimal("0.01"))
    if monto <= 0:
        raise ValueError("El monto del cobro debe ser mayor a cero.")
    saldo = fac.saldo_pendiente
    if monto > saldo + Decimal("0.01"):
        raise ValueError(f"El monto del cobro ({monto}) excede el saldo pendiente ({saldo}).")

    from apps.tesoreria.models import Ingreso

    descripcion = f"Cobro de {fac.codigo}"
    if (nota or "").strip():
        descripcion = f"{descripcion} · {nota.strip()}"[:300]

    with transaction.atomic():
        Ingreso.objects.create(
            factura=fac,
            monto=monto,
            fecha=fecha,
            metodo=metodo,
            descripcion=descripcion,
            referencia_externa=(folio or "").strip()[:100],
            cliente=fac.cliente,
            proyecto=fac.proyecto,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        recalcular_monto_cobrado(fac)
        total = fac.calcular_totales()["total"]
        if fac.monto_cobrado + Decimal("0.01") >= total:
            fac.estado = "cobrada_total"
        elif fac.monto_cobrado > 0:
            fac.estado = "cobrada_parcial"
        fac.save(update_fields=["estado", "monto_cobrado", "actualizado_en"])

    if fac.estado == "cobrada_total":
        _emitir("factura.cobrada_total", fac, actor, {"monto": float(monto)})
    else:
        _emitir("factura.cobrada_parcial", fac, actor, {"monto": float(monto)})
    return fac


def recalcular_monto_cobrado(fac: Factura) -> Decimal:
    """Recalcula monto_cobrado sumando Ingresos vigentes vinculados."""
    from apps.tesoreria.models import Ingreso
    total = Ingreso.vigentes.filter(factura=fac).aggregate(s=Sum("monto"))["s"] or CERO
    fac.monto_cobrado = Decimal(str(total)).quantize(Decimal("0.01"))
    return fac.monto_cobrado


def cancelar(fac: Factura, actor, motivo: str) -> Factura:
    # Auto-sanar el denormalizado: `monto_cobrado` puede quedar > 0 si algún
    # Ingreso se anuló sin recalcular. Recalculamos desde los cobros VIGENTES y
    # persistimos antes de decidir; así una factura sin cobros reales sí se puede
    # cancelar (evita el "dice que hay cobros ligados pero no aparecen").
    if fac.estado == "cancelada":
        raise ValueError("La factura ya estaba cancelada.")
    recalcular_monto_cobrado(fac)
    fac.save(update_fields=["monto_cobrado", "actualizado_en"])
    if (fac.monto_cobrado or CERO) > 0:
        raise ValueError("Anula primero los cobros antes de cancelar la factura.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Debe registrarse el motivo de cancelación.")
    with transaction.atomic():
        fac.estado = "cancelada"
        fac.cancelada_en = timezone.now()
        fac.cancelada_por = actor if getattr(actor, "is_authenticated", False) else None
        fac.motivo_cancelacion = motivo[:300]
        fac.save(update_fields=[
            "estado", "cancelada_en", "cancelada_por", "motivo_cancelacion",
            "actualizado_en",
        ])
    _emitir("factura.cancelada", fac, actor, {"motivo": motivo[:200]})
    return fac


def cancelar_con_cobros(fac: Factura, actor, motivo: str) -> Factura:
    """Cancelación EN CASCADA: anula primero los cobros (Ingresos) vigentes de la
    factura y luego la cancela, en una sola operación atómica. Es el "forzar" del
    modal — evita obligar al usuario a ir a Tesorería a anular uno por uno.

    Anular cada Ingreso (anulado=True) dispara su asiento reverso en La
    Contaduría vía signal, así que la contabilidad no se descuadra."""
    if fac.estado == "cancelada":
        raise ValueError("La factura ya estaba cancelada.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Debe registrarse el motivo de cancelación.")

    from apps.tesoreria.models import Ingreso
    from apps.tesoreria.services import anular_ingreso

    with transaction.atomic():
        for ing in Ingreso.vigentes.filter(factura=fac):
            anular_ingreso(ing, actor, f"Cancelación de factura {fac.codigo}: {motivo}"[:300])
        recalcular_monto_cobrado(fac)  # ya no debe quedar ninguno vigente
        fac.estado = "cancelada"
        fac.cancelada_en = timezone.now()
        fac.cancelada_por = actor if getattr(actor, "is_authenticated", False) else None
        fac.motivo_cancelacion = motivo[:300]
        fac.save(update_fields=[
            "estado", "cancelada_en", "cancelada_por", "motivo_cancelacion",
            "monto_cobrado", "actualizado_en",
        ])
    _emitir("factura.cancelada", fac, actor, {"motivo": motivo[:200], "cobros_anulados": True})
    return fac


def eliminar(fac: Factura, actor) -> str:
    """Elimina PERMANENTEMENTE una factura CANCELADA (limpieza de pruebas o
    errores de captura, ticket LC 2026-07). Solo si estado='cancelada'.

    Los asientos contables (emisión + cancelación) ya se compensan a cero al
    cancelar, así que borrar la factura no descuadra la contabilidad. Los
    Ingresos anulados que aún la referencien (FK PROTECT) se desligan primero.
    Devuelve el código para el mensaje flash. Idempotencia: no aplica (destruye).
    """
    if fac.estado != "cancelada":
        raise ValueError("Solo se puede eliminar una factura cancelada.")
    codigo = fac.codigo
    _emitir("factura.eliminada", fac, actor, {"codigo": codigo})
    with transaction.atomic():
        from apps.tesoreria.models import Ingreso
        Ingreso.objects.filter(factura=fac).update(factura=None)
        fac.delete()
    return codigo


def duplicar(fac: Factura, actor) -> Factura:
    """Crea copia en borrador con los mismos items e impuestos."""
    with transaction.atomic():
        nueva = Factura.objects.create(
            cliente=fac.cliente,
            proyecto=fac.proyecto,
            titulo=f"Copia de {fac.titulo}"[:200],
            estado="borrador",
            moneda=fac.moneda,
            regimen_fiscal=fac.regimen_fiscal,
            descuento_global_porcentaje=fac.descuento_global_porcentaje,
            notas=fac.notas,
            terminos=fac.terminos,
            creado_por=actor if getattr(actor, "is_authenticated", False) else None,
        )
        for it in fac.items.all():
            FacturaItem.objects.create(
                factura=nueva,
                orden=it.orden,
                servicio=it.servicio,
                descripcion=it.descripcion,
                cantidad=it.cantidad,
                unidad=it.unidad,
                precio_unitario=it.precio_unitario,
                descuento_porcentaje=it.descuento_porcentaje,
            )
        for fi in fac.impuestos.all():
            FacturaImpuesto.objects.create(factura=nueva, tasa=fi.tasa)
    _emitir("factura.creada", nueva, actor, {"titulo": nueva.titulo})
    return nueva


# --- KPIs ----------------------------------------------------------------

def kpis_landing() -> dict:
    """Conteos del header de Facturación.

    Cuenta como facturado lo que de verdad salió al cliente: los estados del
    flujo formal MÁS los borradores que ya tienen su CFDI subido. Learning
    Center timbra con el contador, sube el CFDI y casi nunca pica "Emitir", así
    que contando sólo el estado salían 0 emitidas y 0 por cobrar.

    El flujo no se toca: esas facturas siguen siendo borrador para el sistema
    (y por eso siguen sin asiento de cuentas por cobrar). `cfdi_sin_emitir` es
    justamente ese pendiente, para que el Chalán lo pueda señalar.
    """
    from datetime import date as _d

    from apps.facturacion.models import q_facturadas

    hoy = _d.today()
    inicio_mes = hoy.replace(day=1)
    qs = Factura.objects.exclude(estado="cancelada")

    facturadas_qs = qs.filter(q_facturadas())
    # Borradores DE VERDAD: sin ningún archivo del CFDI encima.
    borradores = qs.filter(estado="borrador", pdf_file_id="", xml_file_id="").count()
    cfdi_sin_emitir = qs.filter(estado="borrador").exclude(
        pdf_file_id="", xml_file_id=""
    ).count()

    # Vencidas y saldo se calculan en Python porque el total depende de las
    # líneas y los impuestos. Son decenas de documentos.
    vencidas = 0
    por_cobrar = Decimal("0.00")
    for f in facturadas_qs.filter(fecha_vencimiento__lt=hoy).prefetch_related("items"):
        if f.saldo_pendiente > 0:
            vencidas += 1
    for f in facturadas_qs.exclude(estado="cobrada_total").prefetch_related("items"):
        saldo = f.saldo_pendiente
        if saldo > 0:
            por_cobrar += saldo

    cobradas_mes = qs.filter(
        estado="cobrada_total", emitida_en__date__gte=inicio_mes,
    ).count()

    return {
        "borradores": borradores,
        # "Emitidas" en la UI = facturadas y todavía no cobradas del todo.
        "emitidas": facturadas_qs.exclude(estado="cobrada_total").count(),
        "vencidas": vencidas,
        "cobradas_mes": cobradas_mes,
        # Nuevas — las consume El Análisis.
        "facturadas": facturadas_qs.count(),
        "cfdi_sin_emitir": cfdi_sin_emitir,
        "monto_por_cobrar": float(por_cobrar),
    }
