"""Services de La Caja — links de pago y pagos que llegan por webhook.

El contrato con La Recepción es `url_pago(objeto)`: la URL absoluta de la
página pública para una `Factura` (su saldo) o una `Cotizacion` (su anticipo),
creando o reusando el link vigente. `None` si La Caja está apagada (sin llaves)
o si no hay nada que cobrar. Nunca lanza.

**Registro solo, al confirmarse** (decisión de Oscar): el webhook FIRMADO llega
a `recibir_pago`, que es el único punto donde el dinero entra al sistema:

  · Factura  → `facturacion.services.registrar_cobro` (el mismo camino del
    botón «Registrar cobro»: crea el Ingreso, recalcula el saldo y el estado).
  · Anticipo → `cotizaciones.services.crear_factura_anticipo` + emitirla +
    `registrar_cobro`. Así el anticipo sale de las cuentas por cobrar igual que
    si alguien hubiera generado la factura del anticipo a mano.
  · Libre    → un `tesoreria.Ingreso` suelto, ligado al cliente/proyecto.

El método del ingreso es `stripe` o `mercadopago`, y La Contaduría lo asienta
en «Saldo en Stripe» / «Saldo en MercadoPago» hasta que se registra el payout.

Lo que no cuadra (otro monto, factura ya cobrada, link anulado o vencido, un
segundo pago del mismo link) NO se registra solo: queda «por revisar» con el
motivo, y alguien con `caja.revisar_pago` decide.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from lib import pasarelas
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz
from lib.sanear import sanear_contexto

from .models import LinkPago, PagoRecibido

logger = logging.getLogger("despacho.caja")

CERO = Decimal("0.00")
TOLERANCIA = Decimal("0.01")
MONTO_MAXIMO = Decimal("1000000.00")
COBRABLES = {"emitida", "cobrada_parcial"}
PREFIJO_ANTICIPO = "Anticipo de "
# Una sesión de Stripe dura 24 h; se reusa mientras le quede al menos esto.
MARGEN_SESION = timedelta(minutes=10)


def _q(valor) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("0.01"))


def _dinero(valor) -> str:
    from cuentas.templatetags.forms_helpers import dinero
    return dinero(valor)


def _actor(actor):
    return actor if getattr(actor, "is_authenticated", False) else None


def _emitir(tipo: str, actor, payload: dict) -> None:
    try:
        emitir(EventoPortavoz(
            tipo=tipo,
            actor_id=getattr(actor, "id", None),
            actor_email=getattr(actor, "email", None),
            payload=payload,
        ))
    except Exception:  # noqa: BLE001 — el Portavoz nunca tumba un cobro
        logger.exception("caja: no pude emitir %s", tipo)


def configurada() -> bool:
    """¿Hay al menos una pasarela lista? Sin esto La Caja no ofrece nada."""
    return pasarelas.encendida()


# ── ¿Qué se cobra? ───────────────────────────────────────────────────────────


def factura_de_anticipo(cot):
    """La factura del anticipo de una cotización (la última no cancelada)."""
    return (
        cot.facturas.exclude(estado="cancelada")
        .filter(titulo__startswith=PREFIJO_ANTICIPO)
        .order_by("-creado_en", "-pk")
        .first()
    )


def que_cobrar(objeto) -> dict | None:
    """Lo que se le puede cobrar hoy a una factura o cotización, o None.

    `{tipo, monto, concepto, cliente, proyecto, factura, cotizacion}`.
    """
    from apps.cotizaciones.models import Cotizacion
    from apps.facturacion.models import Factura

    if isinstance(objeto, Factura):
        if objeto.estado not in COBRABLES:
            return None
        saldo = objeto.saldo_pendiente
        if saldo <= CERO:
            return None
        nombre = objeto.folio or objeto.codigo
        concepto = (objeto.concepto or objeto.titulo or "").strip()
        return {
            "tipo": "factura", "monto": saldo,
            "concepto": (f"Factura {nombre}" + (f" · {concepto}" if concepto else ""))[:200],
            "cliente": objeto.cliente, "proyecto": objeto.proyecto,
            "factura": objeto, "cotizacion": None,
        }
    if isinstance(objeto, Cotizacion):
        if objeto.anticipo_pendiente:
            return {
                "tipo": "anticipo", "monto": _q(objeto.anticipo_monto),
                "concepto": f"Anticipo de {objeto.codigo} · {objeto.titulo}"[:200],
                "cliente": objeto.cliente, "proyecto": objeto.proyecto,
                "factura": None, "cotizacion": objeto,
            }
        # El anticipo ya se facturó: lo que se cobra es esa factura.
        fac = factura_de_anticipo(objeto) if objeto.anticipo_facturado_en else None
        return que_cobrar(fac) if fac is not None else None
    return None


# ── Crear, reusar y anular links ─────────────────────────────────────────────


def _crear(datos: dict, actor) -> LinkPago:
    link = LinkPago.objects.create(
        tipo=datos["tipo"], factura=datos.get("factura"), cotizacion=datos.get("cotizacion"),
        cliente=datos.get("cliente"), proyecto=datos.get("proyecto"),
        monto=_q(datos["monto"]), concepto=datos["concepto"][:200],
        creado_por=_actor(actor),
    )
    _emitir("caja.link_creado", actor, _payload_link(link))
    return link


def _payload_link(link: LinkPago) -> dict:
    return {
        "link_id": link.pk, "tipo": link.tipo, "monto": float(link.monto),
        "factura_id": link.factura_id, "cotizacion_id": link.cotizacion_id,
        "cliente_id": link.cliente_id, "proyecto_id": link.proyecto_id,
        "estado": link.estado,
    }


def marcar_vencido_si_toca(link: LinkPago) -> LinkPago:
    """Un link vigente que ya pasó su fecha queda `vencido` (se hace al leerlo)."""
    if link.expirado:
        link.estado = "vencido"
        link.save(update_fields=["estado", "actualizado_en"])
    return link


def link_para(objeto, *, actor=None) -> LinkPago | None:
    """El link vigente por lo que hoy se debe de `objeto`, creándolo si hace falta.

    Si ya hay uno por el MISMO monto, se reusa (el cliente puede recibir el
    mismo enlace en la factura, en la cobranza y en La Recepción). Si el saldo
    cambió, el viejo se anula y nace otro: nunca queda vivo un link por una
    cifra que ya no se debe.
    """
    if not configurada():
        return None
    datos = que_cobrar(objeto)
    if datos is None:
        return None
    filtro = {"tipo": datos["tipo"], "estado": "vigente"}
    if datos["tipo"] == "factura":
        filtro["factura"] = datos["factura"]
    else:
        filtro["cotizacion"] = datos["cotizacion"]
    monto = _q(datos["monto"])
    with transaction.atomic():
        for link in LinkPago.objects.select_for_update().filter(**filtro).order_by("-creado_en"):
            if link.expirado:
                marcar_vencido_si_toca(link)
                continue
            if abs(link.monto - monto) < TOLERANCIA:
                return link
            anular(link, actor=None,
                   motivo=f"El saldo cambió a {_dinero(monto)}: se hizo un link nuevo.")
        return _crear(datos, actor)


def url_pago(objeto, *, actor=None) -> str | None:
    """Contrato con La Recepción (y con la cobranza y la factura).

    URL ABSOLUTA de la página pública de pago de una `Factura` (saldo) o una
    `Cotizacion` (anticipo). `None` si La Caja no está configurada o si no hay
    nada que cobrar. Nunca lanza.
    """
    try:
        link = link_para(objeto, actor=actor)
    except Exception:  # noqa: BLE001 — un link roto nunca tumba el correo ni la vista
        logger.exception("caja: url_pago falló para %r", objeto)
        return None
    return link.url_publica() if link is not None else None


def crear_link_libre(*, monto, concepto: str, actor, cliente=None, proyecto=None) -> LinkPago:
    """Monto + concepto que escribe alguien del despacho, ligado a un cliente o
    proyecto. Lanza `ValueError` con un mensaje para el usuario."""
    if not configurada():
        raise ValueError("La Caja está apagada: faltan las llaves de Stripe o MercadoPago en Los Ajustes.")
    try:
        monto = _q(monto)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("El monto no es un número.") from exc
    if monto <= CERO:
        raise ValueError("El monto debe ser mayor a cero.")
    if monto > MONTO_MAXIMO:
        raise ValueError(f"El monto no puede pasar de {_dinero(MONTO_MAXIMO)}.")
    concepto = sanear_contexto(concepto or "", max_len=200)
    if len(concepto) < 3:
        raise ValueError("Escribe qué se está cobrando (el concepto).")
    if proyecto is not None and cliente is None:
        cliente = proyecto.cliente
    if cliente is None:
        raise ValueError("El link libre va ligado a un cliente o a un proyecto.")
    return _crear({
        "tipo": "libre", "monto": monto, "concepto": concepto,
        "cliente": cliente, "proyecto": proyecto,
    }, actor)


def anular(link: LinkPago, *, actor, motivo: str) -> LinkPago:
    """Mata un link vigente. Cierra también el cobro abierto en la pasarela
    (best-effort, fuera de la petición): si el cliente paga igual, el pago llega
    «por revisar» — el dinero nunca se pierde, pero tampoco se registra solo."""
    if link.estado != "vigente":
        raise ValueError("Sólo se anula un link vigente.")
    link.estado = "anulado"
    link.anulado_en = timezone.now()
    link.anulado_por = _actor(actor)
    link.motivo_anulacion = sanear_contexto(motivo or "", max_len=300) or "Anulado."
    link.save(update_fields=["estado", "anulado_en", "anulado_por", "motivo_anulacion", "actualizado_en"])
    sesion, preferencia = link.stripe_sesion_id, link.mp_preferencia_id
    if sesion or preferencia:
        def _cerrar():
            pasarelas.stripe_expirar(sesion)
            pasarelas.mp_expirar(preferencia)

        def _al_confirmar():
            from lib.tareas_fondo import ejecutar_en_fondo
            ejecutar_en_fondo(_cerrar)

        transaction.on_commit(_al_confirmar)
    _emitir("caja.link_anulado", actor, {**_payload_link(link), "motivo": link.motivo_anulacion})
    return link


def sincronizar_links_de_factura(fac) -> int:
    """Anula los links vigentes de una factura que ya no cuadran con lo que se
    debe (alguien registró un cobro a mano, se canceló, se cobró toda). Lo llama
    la señal de `Factura`. Devuelve cuántos anuló."""
    vigentes = list(LinkPago.objects.filter(factura=fac, estado="vigente"))
    if not vigentes:
        return 0
    datos = que_cobrar(fac)
    anulados = 0
    for link in vigentes:
        if datos is not None and abs(link.monto - _q(datos["monto"])) < TOLERANCIA:
            continue
        motivo = ("La factura ya no tiene saldo por cobrar." if datos is None
                  else f"El saldo de la factura cambió a {_dinero(datos['monto'])}.")
        anular(link, actor=None, motivo=motivo)
        anulados += 1
    return anulados


# ── Correo ───────────────────────────────────────────────────────────────────


def anexar_boton(html: str, url: str | None) -> str:
    """Si hay link y el cuerpo no lo trae (una plantilla guardada antes de La
    Caja), le pone el botón «Pagar en línea» al final."""
    if not url or url in (html or ""):
        return html
    from django.utils.html import format_html
    boton = format_html(
        '<p style="margin:20px 0;font-family:Arial,sans-serif;"><a href="{}" '
        'style="display:inline-block;background:#465fff;color:#ffffff;text-decoration:none;'
        'padding:10px 18px;border-radius:8px;font-weight:bold;">Pagar en línea</a></p>',
        url,
    )
    return f"{html}{boton}"


def enviar_por_correo(link: LinkPago, *, actor):
    """Manda el link al correo del cliente por El Cartero (plantilla
    `link_pago`). Devuelve `lib.cartero.ResultadoCorreo`. Nunca lanza."""
    from lib import cartero

    if not link.cobrable:
        return cartero.ResultadoCorreo(ok=False, error="El link ya no está vigente.")
    cliente = link.cliente
    destino = (getattr(cliente, "email_contacto", "") or "").strip()
    if not destino:
        return cartero.ResultadoCorreo(ok=False, error="El cliente no tiene correo registrado.")
    url = link.url_publica()
    contexto = {
        "cliente": getattr(cliente, "nombre_contacto", "") or getattr(cliente, "razon_social", ""),
        "referencia": link.referencia,
        "concepto": link.concepto,
        "monto": _dinero(link.monto),
        "moneda": link.moneda,
        "vence": timezone.localtime(link.vence_en).strftime("%d/%m/%Y"),
        "link_pago": url,
    }
    remitente = ""
    try:
        from ajustes.models import PlantillaCorreo
        plantilla = PlantillaCorreo.obtener("link_pago")
        asunto, html = plantilla.render(contexto)
        remitente = plantilla.remitente_efectivo()
    except Exception:  # noqa: BLE001
        asunto = f"Su enlace de pago · {link.referencia} · Learning Center"
        html = f"<p>Puede pagar en línea {_dinero(link.monto)} {link.moneda}.</p>"
    html = anexar_boton(html, url)
    res = cartero.enviar(destinatario=destino, asunto=asunto, html=html, remitente=remitente)
    if res.ok:
        _emitir("caja.link_enviado", actor, {**_payload_link(link), "destinatario": destino})
    return res


# ── Abrir el cobro en la pasarela ────────────────────────────────────────────


def _correo_valido(valor) -> str:
    """El correo del cliente sólo se le pasa a la pasarela si es válido: uno mal
    capturado haría que Stripe rechace el cobro y el cliente no podría pagar."""
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email
    valor = (valor or "").strip()
    try:
        validate_email(valor)
    except ValidationError:
        return ""
    return valor


def abrir_cobro(link: LinkPago, pasarela: str) -> str:
    """La URL de la pasarela a la que se manda al cliente. Reusa el cobro ya
    abierto (dos pestañas no deben abrir dos cobros). Lanza `ValueError` o
    `pasarelas.ErrorPasarela`."""
    marcar_vencido_si_toca(link)
    if not link.cobrable:
        raise ValueError("Este link ya no está vigente.")
    if pasarela not in pasarelas.estado()["pasarelas"]:
        raise ValueError("Esa forma de pago no está disponible.")
    ahora = timezone.now()
    email = _correo_valido(getattr(link.cliente, "email_contacto", ""))
    if pasarela == "stripe":
        if link.stripe_url and link.stripe_sesion_expira and link.stripe_sesion_expira > ahora + MARGEN_SESION:
            return link.stripe_url
        r = pasarelas.stripe_crear_checkout(
            monto=link.monto, concepto=link.concepto, referencia=link.token, link_id=link.pk,
            url_exito=link.url_publica("gracias"), url_cancelado=link.url_publica("cancelado"),
            email=email,
        )
        expira = ahora + timedelta(hours=23)
        if r.get("expira"):
            try:
                from datetime import UTC, datetime
                expira = datetime.fromtimestamp(int(r["expira"]), tz=UTC)
            except (TypeError, ValueError, OverflowError):
                pass
        link.stripe_sesion_id, link.stripe_url, link.stripe_sesion_expira = r["id"][:120], r["url"][:1000], expira
        link.save(update_fields=["stripe_sesion_id", "stripe_url", "stripe_sesion_expira", "actualizado_en"])
        return link.stripe_url
    if link.mp_url:
        return link.mp_url
    r = pasarelas.mp_crear_preferencia(
        monto=link.monto, concepto=link.concepto, referencia=link.token, link_id=link.pk,
        url_exito=link.url_publica("gracias"), url_cancelado=link.url_publica("cancelado"),
        vence_en=link.vence_en,
    )
    link.mp_preferencia_id, link.mp_url = r["id"][:120], r["url"][:1000]
    link.save(update_fields=["mp_preferencia_id", "mp_url", "actualizado_en"])
    return link.mp_url


# ── Pagos que llegan ─────────────────────────────────────────────────────────

# Lo único que se guarda del aviso. Nada de tarjeta, nombre ni correo del pagador.
_CLAVES_PAYLOAD = (
    "evento_id", "evento_tipo", "sesion_id", "payment_intent", "pago_id",
    "estado", "estado_detalle", "monto", "moneda", "metodo", "tipo_metodo", "referencia",
)


def _sanear_payload(payload: dict | None) -> dict:
    limpio = {}
    for clave in _CLAVES_PAYLOAD:
        valor = (payload or {}).get(clave)
        if valor is None or valor == "":
            continue
        if isinstance(valor, int | float | bool):
            limpio[clave] = valor
        else:
            limpio[clave] = sanear_contexto(str(valor), max_len=200)
    return limpio


def _motivo_del_link(link: LinkPago | None, pago: PagoRecibido) -> str:
    """Por qué el pago NO se puede aplicar al link, o '' si el link está bien."""
    if link is None:
        return "No se encontró el link de pago al que corresponde."
    if (pago.moneda or "").upper() != "MXN":
        return f"Llegó en {pago.moneda}, no en pesos."
    if link.estado == "anulado":
        return f"El link estaba anulado ({link.motivo_anulacion or 'sin motivo'})."
    if link.estado == "pagado":
        return "El link ya estaba pagado: puede ser un pago doble."
    if link.estado == "vencido" or link.expirado:
        return "El link había vencido."
    if abs(_q(pago.monto) - link.monto) >= TOLERANCIA:
        return f"Se pagaron {_dinero(pago.monto)} y el link era por {_dinero(link.monto)}."
    return ""


def _plan(link: LinkPago, monto: Decimal) -> tuple[str, object]:
    """A dónde va el dinero de un link. `(paso, objeto)`:

    - `("cobrar", factura)`        — registrar_cobro a esa factura
    - `("emitir_y_cobrar", fac)`   — la factura del anticipo existe en borrador
    - `("anticipo_nuevo", cot)`    — generar la factura del anticipo y cobrarla
    - `("ingreso", None)`          — ingreso suelto (monto libre)
    - `("revisar", "motivo")`      — no cuadra
    """
    if link.tipo == "libre":
        return "ingreso", None
    if link.tipo == "factura":
        fac = link.factura
        if fac is None:
            return "revisar", "La factura del link ya no existe."
        return _plan_factura(fac, monto)
    cot = link.cotizacion
    if cot is None:
        return "revisar", "La cotización del link ya no existe."
    if cot.anticipo_pendiente:
        if abs(_q(cot.anticipo_monto) - monto) >= TOLERANCIA:
            return "revisar", f"El anticipo de {cot.codigo} ahora es {_dinero(cot.anticipo_monto)}."
        return "anticipo_nuevo", cot
    fac = factura_de_anticipo(cot)
    if fac is None:
        return "revisar", f"La cotización {cot.codigo} ya no tiene anticipo por cobrar."
    if fac.estado == "borrador":
        if fac.calcular_totales()["total"] + TOLERANCIA < monto:
            return "revisar", f"La factura del anticipo ({fac.codigo}) es por menos de lo pagado."
        return "emitir_y_cobrar", fac
    return _plan_factura(fac, monto)


def _plan_factura(fac, monto: Decimal) -> tuple[str, object]:
    nombre = fac.folio or fac.codigo
    if fac.estado not in COBRABLES:
        return "revisar", f"La factura {nombre} está «{fac.estado_etiqueta}»: ya no admite cobros."
    saldo = fac.saldo_pendiente
    if saldo + TOLERANCIA < monto:
        return "revisar", (f"La factura {nombre} sólo debía {_dinero(saldo)}: "
                           "alguien registró otro cobro antes.")
    return "cobrar", fac


def _aplicar(link: LinkPago | None, pago: PagoRecibido, paso: str, objeto, *, actor=None):
    """Mete el dinero al sistema según el plan. Devuelve el `Ingreso`."""
    from apps.facturacion.models import Factura
    from apps.facturacion.services import emitir_factura, registrar_cobro
    from apps.tesoreria.models import Ingreso

    monto = _q(pago.monto)
    fecha = timezone.localdate(pago.fecha_pago) if pago.fecha_pago else timezone.localdate()
    folio = pago.id_externo[:100]
    nota = f"Pago en línea con {pasarelas.NOMBRES.get(pago.pasarela, pago.pasarela)}"

    if paso == "ingreso":
        concepto = link.concepto if link else "sin link"
        return Ingreso.objects.create(
            monto=monto, fecha=fecha, metodo=pago.pasarela,
            descripcion=f"{nota} · {concepto}"[:300], referencia_externa=folio,
            cliente=link.cliente if link else None, proyecto=link.proyecto if link else None,
            creado_por=_actor(actor),
        )
    if paso == "anticipo_nuevo":
        from apps.cotizaciones.services import crear_factura_anticipo
        fac = crear_factura_anticipo(objeto, actor)
        emitir_factura(fac, actor)
    elif paso == "emitir_y_cobrar":
        fac = objeto
        emitir_factura(fac, actor)
    else:
        fac = objeto
    fac = Factura.objects.select_for_update().get(pk=fac.pk)
    registrar_cobro(fac, monto=monto, fecha=fecha, metodo=pago.pasarela, actor=actor,
                    folio=folio, nota=nota)
    if link is not None and link.factura_id != fac.pk:
        link.factura = fac
        link.save(update_fields=["factura", "actualizado_en"])
    return Ingreso.objects.filter(factura=fac, referencia_externa=folio).order_by("-pk").first()


def recibir_pago(*, pasarela: str, id_externo: str, monto, moneda: str = "MXN",
                 estado_pasarela: str = "", aprobado: bool, pendiente: bool = False,
                 referencia: str = "", fecha_pago=None, payload: dict | None = None) -> PagoRecibido:
    """El único punto por donde entra dinero de una pasarela. IDEMPOTENTE: el
    mismo pago avisado dos veces encuentra su fila y no vuelve a registrar.

    Lo llaman los webhooks DESPUÉS de verificar la firma (y, en MercadoPago,
    de consultar el pago a su API).
    """
    id_externo = sanear_contexto(str(id_externo or ""), max_len=120)
    if not id_externo:
        raise ValueError("El aviso no trae el id del pago.")
    monto = _q(monto)
    link = LinkPago.objects.filter(token=referencia).first() if referencia else None
    datos = {
        "link": link, "monto": monto, "moneda": (moneda or "MXN").upper()[:3],
        "estado_pasarela": sanear_contexto(estado_pasarela or "", max_len=40),
        "payload": _sanear_payload(payload), "fecha_pago": fecha_pago or timezone.now(),
    }
    avisos: list = []
    try:
        with transaction.atomic():
            pago, creado = PagoRecibido.objects.select_for_update().get_or_create(
                pasarela=pasarela, id_externo=id_externo,
                defaults={**datos, "estado": "pendiente"},
            )
            if not creado:
                if pago.cerrado:
                    return pago  # idempotencia: ya se decidió
                for campo, valor in datos.items():
                    if campo == "link" and valor is None:
                        continue
                    setattr(pago, campo, valor)
            if not aprobado:
                pago.estado = "pendiente" if pendiente else "rechazado"
                pago.save()
                return pago
            avisos = _confirmar(pago, pago.link)
    except IntegrityError:
        # Dos avisos del mismo pago al mismo tiempo: el otro ganó la carrera.
        return PagoRecibido.objects.get(pasarela=pasarela, id_externo=id_externo)
    for aviso in avisos:
        aviso()
    return pago


def _confirmar(pago: PagoRecibido, link: LinkPago | None) -> list:
    """Dentro de la transacción de `recibir_pago`. Devuelve los avisos a mandar
    ya fuera de ella (evento + push)."""
    if link is not None:
        # Dos pagos distintos del MISMO link (dos pestañas): el segundo espera al
        # primero y lo encuentra ya pagado → por revisar, no dos ingresos.
        link = LinkPago.objects.select_for_update().get(pk=link.pk)
    motivo = _motivo_del_link(link, pago)
    paso, objeto = ("revisar", motivo) if motivo else _plan(link, _q(pago.monto))
    if paso != "revisar":
        try:
            with transaction.atomic():
                link.estado = "pagado"
                link.pagado_en = timezone.now()
                link.pasarela = pago.pasarela
                link.save(update_fields=["estado", "pagado_en", "pasarela", "actualizado_en"])
                ingreso = _aplicar(link, pago, paso, objeto)
        except ValueError as exc:
            paso, objeto = "revisar", f"No se pudo registrar solo: {exc}"[:300]
        else:
            pago.estado = "registrado"
            pago.ingreso = ingreso
            pago.motivo = ""
            pago.save()
            return [lambda: _avisar_registrado(pago)]
    pago.estado = "por_revisar"
    pago.motivo = str(objeto)[:300]
    pago.save()
    return [lambda: _avisar_por_revisar(pago)]


def _payload_pago(pago: PagoRecibido) -> dict:
    link = pago.link
    return {
        "pago_id": pago.pk, "pasarela": pago.pasarela, "id_externo": pago.id_externo,
        "monto": float(pago.monto), "moneda": pago.moneda, "estado": pago.estado,
        "link_id": pago.link_id, "tipo": getattr(link, "tipo", ""),
        "factura_id": getattr(link, "factura_id", None),
        "cotizacion_id": getattr(link, "cotizacion_id", None),
        "cliente_id": getattr(link, "cliente_id", None),
        "ingreso_id": pago.ingreso_id, "motivo": pago.motivo,
    }


def _avisar_registrado(pago: PagoRecibido) -> None:
    _emitir("pago.recibido", None, _payload_pago(pago))
    from .push import notificar_pago
    notificar_pago(pago)


def _avisar_por_revisar(pago: PagoRecibido) -> None:
    _emitir("caja.pago_por_revisar", None, _payload_pago(pago))
    from .push import notificar_pago
    notificar_pago(pago)


# ── Revisión a mano ──────────────────────────────────────────────────────────


def revisar_pago(pago: PagoRecibido, *, accion: str, actor, nota: str = "") -> PagoRecibido:
    """Alguien decide un pago «por revisar».

    - `registrar`: se mete el dinero. Si el link apunta a una factura que aún lo
      admite, como cobro de esa factura; si no, como ingreso suelto del cliente.
    - `descartar`: no se registra (p. ej. ya se devolvió desde la pasarela).
    """
    if pago.estado != "por_revisar":
        raise ValueError("Ese pago ya no está por revisar.")
    nota = sanear_contexto(nota or "", max_len=300)
    if accion == "descartar":
        if not nota:
            raise ValueError("Escribe por qué se descarta.")
        pago.estado = "descartado"
    elif accion == "registrar":
        link = pago.link
        with transaction.atomic():
            paso, objeto = _plan(link, _q(pago.monto)) if link is not None else ("ingreso", None)
            if paso == "revisar":
                paso, objeto = "ingreso", None
            pago.ingreso = _aplicar(link, pago, paso, objeto, actor=actor)
            if link is not None and link.estado == "vigente":
                link.estado = "pagado"
                link.pagado_en = timezone.now()
                link.pasarela = pago.pasarela
                link.save(update_fields=["estado", "pagado_en", "pasarela", "actualizado_en"])
        pago.estado = "registrado"
    else:
        raise ValueError("Acción desconocida.")
    pago.revisado_por = _actor(actor)
    pago.revisado_en = timezone.now()
    pago.nota_revision = nota
    pago.save()
    _emitir("caja.pago_revisado", actor, {**_payload_pago(pago), "accion": accion})
    return pago


# ── Lecturas (pantalla y El Chalán) ──────────────────────────────────────────


def resumen() -> dict:
    """Cifras de la cabecera de La Caja."""
    from django.db.models import Count, Sum

    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    registrados_mes = PagoRecibido.objects.filter(estado="registrado", fecha_pago__date__gte=inicio_mes)
    agg = registrados_mes.aggregate(total=Sum("monto"), n=Count("pk"))
    vigentes = LinkPago.objects.filter(estado="vigente", vence_en__gt=timezone.now())
    return {
        "cobrado_mes": agg["total"] or CERO,
        "pagos_mes": agg["n"] or 0,
        "links_vigentes": vigentes.count(),
        "por_cobrar_links": vigentes.aggregate(s=Sum("monto"))["s"] or CERO,
        "por_revisar": PagoRecibido.objects.filter(estado="por_revisar").count(),
        "pendientes": PagoRecibido.objects.filter(estado="pendiente").count(),
    }
