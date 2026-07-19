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

def _bytes_de_drive(file_id: str) -> bytes | None:
    """Descarga los bytes de un archivo de Drive por id, o None. Nunca lanza."""
    if not file_id:
        return None
    try:
        from lib.google_drive import drive
        contenido, _mime, _nombre = drive.descargar(file_id)
        return contenido
    except Exception:  # noqa: BLE001
        return None


def pdf_bytes_almacenado(fac: Factura) -> bytes | None:
    """Bytes del PDF del CFDI almacenado (para adjuntar en correos). Nunca lanza."""
    return _bytes_de_drive(fac.pdf_file_id)


def almacenar_cfdi(fac: Factura, *, pdf_file=None, xml_file=None,
                   cfdi_uuid: str = "", actor=None) -> dict:
    """Almacena el CFDI del PAC (PDF y/o XML) en Drive (subcarpeta «Facturas»)
    y lo liga a la factura. Reemplaza el archivo previo del mismo tipo y guarda
    el folio fiscal (UUID) si se provee. Best-effort por archivo — nunca lanza.
    Devuelve {ok, guardados: [...], errores: [...]}."""
    import contextlib

    from lib.adjuntos import subir
    from lib.google_drive import drive

    guardados: list[str] = []
    errores: list[str] = []
    update_fields: list[str] = []

    def _reemplazar(prev_id: str):
        if prev_id:
            with contextlib.suppress(Exception):
                drive.borrar(prev_id)

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
                descripcion=it.descripcion,
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
    """Borra el PDF o XML del CFDI (Drive + campos de la factura). Best-effort;
    nunca lanza. `tipo` ∈ {'pdf', 'xml'}."""
    import contextlib

    from lib.google_drive import drive

    campos: list[str] = []
    if tipo == "pdf" and fac.pdf_file_id:
        with contextlib.suppress(Exception):
            drive.borrar(fac.pdf_file_id)
        fac.pdf_file_id = ""
        fac.pdf_url = ""
        campos = ["pdf_file_id", "pdf_url"]
    elif tipo == "xml" and fac.xml_file_id:
        with contextlib.suppress(Exception):
            drive.borrar(fac.xml_file_id)
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
    if fac.estado == "cancelada":
        raise ValueError("La factura ya estaba cancelada.")
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
    qs = Factura.objects.exclude(estado="cancelada")
    from datetime import date as _d
    hoy = _d.today()
    inicio_mes = hoy.replace(day=1)
    borradores = qs.filter(estado="borrador").count()
    emitidas = qs.filter(estado__in=["emitida", "cobrada_parcial"]).count()
    # 'vencidas' lo computamos en Python por simplicidad (saldo > 0 + fecha
    # vencimiento < hoy). Para listas grandes habría que mover a queryset.
    vencidas = 0
    for f in qs.filter(estado__in=["emitida", "cobrada_parcial"], fecha_vencimiento__lt=hoy):
        if f.saldo_pendiente > 0:
            vencidas += 1
    cobradas_mes = qs.filter(
        estado="cobrada_total", emitida_en__gte=inicio_mes,
    ).count()
    return {
        "borradores": borradores,
        "emitidas": emitidas,
        "vencidas": vencidas,
        "cobradas_mes": cobradas_mes,
    }
