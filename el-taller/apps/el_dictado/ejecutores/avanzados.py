"""Ejecutores avanzados — escritura financiera y de proceso (Fase B,
sprint S-Chalán-Scope-OCR).

Mismo contrato que `basicos.py`: cada función toma
`(accion: DictadoAccion, usuario: Usuario, contexto: dict)`, aplica el cambio
y lanza `ValueError` si el payload es inválido, la entidad no existe **o el
usuario no tiene permiso**.

Regla de seguridad #2 (defensa en profundidad): además de que el prompt
enumera solo lo permitido por rol (`dictado_catalogo.comandos_para`), cada
ejecutor financiero re-chequea el permiso con `lib.permisos` ANTES de tocar
la DB. El Chalán nunca aplica sin confirmación humana (eso lo garantiza
`services.aplicar`); esto garantiza que un rol sin permiso no escriba aunque
el LLM proponga la acción.
"""

from __future__ import annotations

import contextlib
from datetime import date as _date
from decimal import Decimal, InvalidOperation

from . import registrar
from .basicos import _limpiar_slug, _resolver_cliente, _resolver_proyecto

# ── Helpers comunes ───────────────────────────────────────────────────────────

def _exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise ValueError(mensaje)


def _monto(payload: dict, clave: str = "monto") -> Decimal:
    valor = payload.get(clave)
    try:
        monto = Decimal(str(valor)).quantize(Decimal("0.01"))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError(f"`{clave}` inválido: {valor}") from exc
    if monto <= 0:
        raise ValueError(f"`{clave}` debe ser mayor a cero.")
    return monto


def _fecha(payload: dict, clave: str = "fecha"):
    fecha_str = payload.get(clave)
    fecha = _date.today()
    if fecha_str:
        with contextlib.suppress(ValueError):
            fecha = _date.fromisoformat(str(fecha_str)[:10])
    return fecha


def _factura_por_codigo(codigo: str):
    from apps.facturacion.models import Factura
    codigo = (codigo or "").strip().upper()
    _exigir(bool(codigo), "Falta `codigo` de la factura.")
    fac = Factura.objects.filter(codigo__iexact=codigo).first()
    _exigir(fac is not None, f"Factura `{codigo}` no encontrada.")
    return fac


def _cotizacion_por_codigo(codigo: str):
    from apps.cotizaciones.models import Cotizacion
    codigo = (codigo or "").strip().upper()
    _exigir(bool(codigo), "Falta `codigo` de la cotización.")
    cot = Cotizacion.objects.filter(codigo__iexact=codigo).first()
    _exigir(cot is not None, f"Cotización `{codigo}` no encontrada.")
    return cot


def _egreso_por_codigo(codigo: str):
    from apps.tesoreria.models import Egreso
    codigo = (codigo or "").strip().upper()
    _exigir(bool(codigo), "Falta `codigo` del egreso.")
    eg = Egreso.objects.filter(codigo__iexact=codigo).first()
    _exigir(eg is not None, f"Egreso `{codigo}` no encontrado.")
    return eg


def _ingreso_por_codigo(codigo: str):
    from apps.tesoreria.models import Ingreso
    codigo = (codigo or "").strip().upper()
    _exigir(bool(codigo), "Falta `codigo` del ingreso.")
    ing = Ingreso.objects.filter(codigo__iexact=codigo).first()
    _exigir(ing is not None, f"Ingreso `{codigo}` no encontrado.")
    return ing


def _resolver_cuenta(clave: str):
    """Cuenta contable por código, slot (caja/banco/cxc/stripe_saldo…) o nombre."""
    from apps.contaduria.models import CuentaContable
    clave = _limpiar_slug((clave or "").strip())
    _exigir(bool(clave), "Falta la cuenta contable.")
    cta = (
        CuentaContable.objects.filter(codigo__iexact=clave, activa=True).first()
        or CuentaContable.objects.filter(slot=clave.lower(), activa=True).first()
        or CuentaContable.objects.filter(nombre__icontains=clave, activa=True).first()
    )
    _exigir(cta is not None, f"Cuenta `{clave}` no encontrada.")
    return cta


def _gate(usuario, helper, accion_humana: str) -> None:
    from lib import permisos
    if not getattr(permisos, helper)(usuario):
        raise ValueError(f"No tienes permiso para {accion_humana}.")


# ── Tesorería ───────────────────────────────────────────────────────────────

@registrar("registrar_ingreso")
def registrar_ingreso(accion, usuario, contexto=None):
    """Payload: monto, descripcion, cliente_slug?, proyecto_slug?, metodo?, fecha?."""
    _gate(usuario, "puede_ver_finanzas", "registrar ingresos")
    from apps.tesoreria.models import METODOS_INGRESO, Ingreso

    payload = accion.payload or {}
    monto = _monto(payload)
    descripcion = (payload.get("descripcion") or "").strip()
    _exigir(bool(descripcion), "`descripcion` requerida.")

    cliente = None
    if payload.get("cliente_slug"):
        cliente = _resolver_cliente(payload["cliente_slug"].lower(), contexto)
    proyecto = None
    if payload.get("proyecto_slug"):
        proyecto = _resolver_proyecto(payload["proyecto_slug"], contexto)

    metodo = (payload.get("metodo") or "transferencia").lower()
    if metodo not in dict(METODOS_INGRESO):
        metodo = "transferencia"

    ingreso = Ingreso.objects.create(
        monto=monto, descripcion=descripcion[:300], cliente=cliente,
        proyecto=proyecto, metodo=metodo, fecha=_fecha(payload),
        creado_por=usuario,
    )
    accion.entidad_tipo = "ingreso"
    accion.entidad_id = ingreso.pk


@registrar("reembolsar_egreso")
def reembolsar_egreso(accion, usuario, contexto=None):
    """Payload: codigo, banco_o_caja? (banco|caja), metodo?."""
    _gate(usuario, "puede_ver_finanzas", "reembolsar egresos")
    from apps.tesoreria.services import reembolsar_egreso as svc

    payload = accion.payload or {}
    egreso = _egreso_por_codigo(payload.get("codigo"))
    _exigir(egreso.estado_pago == "por_reembolsar",
            f"El egreso {egreso.codigo} no está marcado por reembolsar.")
    banco_o_caja = (payload.get("banco_o_caja") or "banco").lower()
    if banco_o_caja not in {"banco", "caja"}:
        banco_o_caja = "banco"
    metodo = (payload.get("metodo") or "transferencia").lower()
    svc(egreso, metodo=metodo, banco_o_caja=banco_o_caja, actor=usuario)
    accion.entidad_tipo = "egreso"
    accion.entidad_id = egreso.pk


@registrar("anular_egreso")
def anular_egreso(accion, usuario, contexto=None):
    """Payload: codigo, motivo."""
    _gate(usuario, "puede_ver_finanzas", "anular egresos")
    from apps.tesoreria.services import anular_egreso as svc

    payload = accion.payload or {}
    egreso = _egreso_por_codigo(payload.get("codigo"))
    motivo = (payload.get("motivo") or "").strip()
    _exigir(bool(motivo), "`motivo` requerido para anular.")
    svc(egreso, usuario, motivo)
    accion.entidad_tipo = "egreso"
    accion.entidad_id = egreso.pk


@registrar("anular_ingreso")
def anular_ingreso(accion, usuario, contexto=None):
    """Payload: codigo, motivo."""
    _gate(usuario, "puede_ver_finanzas", "anular ingresos")
    from apps.tesoreria.services import anular_ingreso as svc

    payload = accion.payload or {}
    ingreso = _ingreso_por_codigo(payload.get("codigo"))
    motivo = (payload.get("motivo") or "").strip()
    _exigir(bool(motivo), "`motivo` requerido para anular.")
    svc(ingreso, usuario, motivo)
    accion.entidad_tipo = "ingreso"
    accion.entidad_id = ingreso.pk


# ── Facturación ───────────────────────────────────────────────────────────────

@registrar("emitir_factura")
def emitir_factura(accion, usuario, contexto=None):
    """Payload: codigo."""
    _gate(usuario, "puede_emitir_facturacion", "emitir facturas")
    from apps.facturacion.services import emitir_factura as svc

    fac = _factura_por_codigo((accion.payload or {}).get("codigo"))
    svc(fac, usuario)  # el service valida estado=borrador
    accion.entidad_tipo = "factura"
    accion.entidad_id = fac.pk


@registrar("cobrar_factura")
def cobrar_factura(accion, usuario, contexto=None):
    """Payload: codigo, monto, metodo?, banco_o_caja? (banco|caja), fecha?."""
    _gate(usuario, "puede_cobrar_facturacion", "registrar cobros")
    from apps.facturacion.services import registrar_cobro

    payload = accion.payload or {}
    fac = _factura_por_codigo(payload.get("codigo"))
    monto = _monto(payload)
    metodo = (payload.get("metodo") or "transferencia").lower()
    banco_o_caja = (payload.get("banco_o_caja") or "banco").lower()
    if banco_o_caja not in {"banco", "caja"}:
        banco_o_caja = "banco"
    registrar_cobro(
        fac, monto=monto, fecha=_fecha(payload), metodo=metodo,
        actor=usuario, banco_o_caja=banco_o_caja,
    )
    accion.entidad_tipo = "factura"
    accion.entidad_id = fac.pk


# ── Cotizaciones ──────────────────────────────────────────────────────────────

@registrar("enviar_cotizacion")
def enviar_cotizacion(accion, usuario, contexto=None):
    """Payload: codigo, email?."""
    _gate(usuario, "puede_enviar_cotizaciones", "enviar cotizaciones")
    from apps.cotizaciones.services import marcar_enviada

    payload = accion.payload or {}
    cot = _cotizacion_por_codigo(payload.get("codigo"))
    marcar_enviada(cot, usuario, email_destino=(payload.get("email") or "").strip())
    accion.entidad_tipo = "cotizacion"
    accion.entidad_id = cot.pk


@registrar("aprobar_cotizacion")
def aprobar_cotizacion(accion, usuario, contexto=None):
    """Payload: codigo, nombre, email?, referencia?."""
    _gate(usuario, "puede_aprobar_cotizaciones", "aprobar cotizaciones")
    from apps.cotizaciones.services import marcar_aprobada

    payload = accion.payload or {}
    cot = _cotizacion_por_codigo(payload.get("codigo"))
    nombre = (payload.get("nombre") or "").strip()
    _exigir(bool(nombre), "Falta `nombre` de quien aprobó.")
    marcar_aprobada(
        cot, usuario, nombre=nombre,
        email=(payload.get("email") or "").strip(),
        referencia=(payload.get("referencia") or "").strip(),
    )
    accion.entidad_tipo = "cotizacion"
    accion.entidad_id = cot.pk


@registrar("rechazar_cotizacion")
def rechazar_cotizacion(accion, usuario, contexto=None):
    """Payload: codigo, motivo."""
    _gate(usuario, "puede_rechazar_cotizaciones", "rechazar cotizaciones")
    from apps.cotizaciones.services import marcar_rechazada

    payload = accion.payload or {}
    cot = _cotizacion_por_codigo(payload.get("codigo"))
    motivo = (payload.get("motivo") or "").strip()
    _exigir(bool(motivo), "`motivo` requerido para rechazar.")
    marcar_rechazada(cot, usuario, motivo=motivo)
    accion.entidad_tipo = "cotizacion"
    accion.entidad_id = cot.pk


# ── Contaduría ────────────────────────────────────────────────────────────────

@registrar("capturar_traspaso")
def capturar_traspaso(accion, usuario, contexto=None):
    """Payload: cuenta_origen, cuenta_destino, monto, descripcion?, fecha?."""
    _gate(usuario, "puede_capturar_contaduria", "capturar movimientos contables")
    from apps.contaduria.wizards import registrar_traspaso

    payload = accion.payload or {}
    origen = _resolver_cuenta(payload.get("cuenta_origen"))
    destino = _resolver_cuenta(payload.get("cuenta_destino"))
    asiento = registrar_traspaso(
        cuenta_origen=origen, cuenta_destino=destino, monto=_monto(payload),
        descripcion=(payload.get("descripcion") or "").strip(),
        fecha=_fecha(payload), creado_por=usuario,
    )
    accion.entidad_tipo = "asiento"
    accion.entidad_id = asiento.pk


@registrar("capturar_ajuste")
def capturar_ajuste(accion, usuario, contexto=None):
    """Payload: cuenta, direccion (sube|baja), monto, motivo, fecha?."""
    _gate(usuario, "puede_capturar_contaduria", "capturar movimientos contables")
    from apps.contaduria.wizards import registrar_ajuste

    payload = accion.payload or {}
    cuenta = _resolver_cuenta(payload.get("cuenta"))
    direccion = (payload.get("direccion") or "").lower()
    _exigir(direccion in {"sube", "baja"}, "`direccion` debe ser 'sube' o 'baja'.")
    motivo = (payload.get("motivo") or "").strip()
    _exigir(bool(motivo), "`motivo` requerido para el ajuste.")
    asiento = registrar_ajuste(
        cuenta_objetivo=cuenta, direccion=direccion, monto=_monto(payload),
        motivo=motivo, fecha=_fecha(payload), creado_por=usuario,
    )
    accion.entidad_tipo = "asiento"
    accion.entidad_id = asiento.pk


# ── Comunicaciones (V6 Bloque 7B) ────────────────────────────────────────────

@registrar("enviar_correo")
def enviar_correo(accion, usuario, contexto=None):
    """Payload: cliente_slug, tipo_plantilla (generico|bienvenida|cobranza),
    asunto?, mensaje? (requerido si generico).

    Manda SOLO al email de contacto registrado del cliente — el Chalán nunca
    escribe a direcciones arbitrarias. Preview/confirm humano garantizado por
    services.aplicar; aquí re-chequeamos permiso + saneamos el texto libre.
    """
    _gate(usuario, "puede_enviar_correo", "enviar correos a clientes")
    from ajustes.models.plantilla_correo import PlantillaCorreo

    from lib import cartero
    from lib.sanear import sanear_contexto

    payload = accion.payload or {}
    cliente = _resolver_cliente((payload.get("cliente_slug") or "").lower(), contexto)
    email = (cliente.email_contacto or "").strip()
    _exigir(bool(email), f"El cliente «{cliente.razon_social}» no tiene email de contacto registrado.")

    tipo = (payload.get("tipo_plantilla") or "generico").strip().lower()
    _exigir(tipo in {"generico", "bienvenida", "cobranza"},
            "`tipo_plantilla` debe ser generico, bienvenida o cobranza.")

    contexto_correo: dict = {"cliente": cliente.nombre_contacto or cliente.razon_social}
    if tipo == "generico":
        mensaje = sanear_contexto((payload.get("mensaje") or "").strip())
        _exigir(bool(mensaje), "`mensaje` requerido para un correo genérico.")
        contexto_correo["mensaje"] = mensaje
        contexto_correo["asunto"] = sanear_contexto(
            (payload.get("asunto") or "").strip()
        ) or f"Mensaje de Learning Center para {cliente.razon_social}"
    elif tipo == "bienvenida":
        from django.utils import timezone
        contexto_correo["fecha"] = timezone.localdate().strftime("%d/%m/%Y")
        contexto_correo["representante"] = usuario.get_short_name() or ""

    plantilla = PlantillaCorreo.obtener(tipo)
    asunto_r, html = plantilla.render(contexto_correo)
    resultado = cartero.enviar(destinatario=email, asunto=asunto_r, html=html)
    _exigir(bool(getattr(resultado, "ok", False)),
            f"El Cartero no pudo entregar el correo: {getattr(resultado, 'error', 'error desconocido')}")

    accion.entidad_tipo = "correo"
    accion.entidad_id = cliente.pk
    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="correo.enviado_chalan",
            actor_id=usuario.pk, actor_email=usuario.email,
            payload={"cliente_id": cliente.pk, "tipo_plantilla": tipo},
        ))
