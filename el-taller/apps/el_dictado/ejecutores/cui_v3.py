"""Ejecutores de la Ola 3 CUI (S-Chalan-MCP-V1) — completar verbos que faltaban.

El Chalán ya CREA mucho (Olas 1-2). Esta ola cierra los verbos que le faltaban:
**anular** del ciclo comercial-contable (cotización, movimiento contable) y
**editar** del Catálogo (proveedor, variación). Los homólogos `crear_*` viven en
`avanzados.py`/`catalogo.py`; aquí se agregan sus contrapartes de anulación/edición.

Mismo contrato que `avanzados.py`/`cui_v1.py`/`cui_v2.py`:
`(accion, usuario, contexto)`, lanza `ValueError` si el payload es inválido, la
entidad no existe o el usuario no tiene permiso (defensa en profundidad — el
gating del catálogo ya filtra el prompt, aquí se re-chequea antes de tocar la DB).
Cada ejecutor envuelve un service ya testeado o replica el patrón de
`actualizar_servicio`. Nada se aplica sin la confirmación humana que garantiza
`services.aplicar` (regla §20).
"""

from __future__ import annotations

import contextlib
from decimal import Decimal, InvalidOperation

from . import _gate, registrar
from .avanzados import _cotizacion_por_codigo, _exigir
from .basicos import _limpiar_slug


def _asiento_por_codigo(codigo):
    from apps.contaduria.models import Asiento
    codigo = (codigo or "").strip().upper()
    _exigir(bool(codigo), "Falta `codigo` del movimiento contable.")
    asiento = Asiento.objects.filter(codigo__iexact=codigo).first()
    _exigir(asiento is not None, f"Movimiento contable `{codigo}` no encontrado.")
    return asiento


def _resolver_proveedor(clave):
    """Proveedor activo por razón social (exacta o parcial, sin ambigüedad)."""
    from apps.el_catalogo.models import Proveedor
    clave = _limpiar_slug((clave or "").strip())
    _exigir(bool(clave), "Falta el proveedor (`proveedor`).")
    qs = Proveedor.objects.filter(activo=True)
    prov = qs.filter(razon_social__iexact=clave).first()
    if prov is None:
        coincidencias = list(qs.filter(razon_social__icontains=clave)[:2])
        _exigir(len(coincidencias) >= 1, f"Proveedor `{clave}` no encontrado.")
        _exigir(len(coincidencias) == 1, f"Varios proveedores coinciden con `{clave}`; sé más específico.")
        prov = coincidencias[0]
    return prov


def _decimal(valor, clave):
    try:
        d = Decimal(str(valor)).quantize(Decimal("0.01"))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError(f"`{clave}` inválido: {valor}") from exc
    if d < 0:
        raise ValueError(f"`{clave}` no puede ser negativo.")
    return d


# ── Anulaciones (ciclo comercial-contable) ───────────────────────────────────────

@registrar("anular_cotizacion")
def anular_cotizacion(accion, usuario, contexto=None):
    """Payload: codigo, motivo."""
    _gate(usuario, "puede_anular_cotizaciones", "anular cotizaciones")
    from apps.cotizaciones.services import marcar_anulada

    payload = accion.payload or {}
    cot = _cotizacion_por_codigo(payload.get("codigo"))
    motivo = (payload.get("motivo") or "").strip()
    _exigir(bool(motivo), "`motivo` requerido para anular la cotización.")
    marcar_anulada(cot, usuario, motivo=motivo)
    accion.entidad_tipo = "cotizacion"
    accion.entidad_id = cot.pk


@registrar("anular_asiento")
def anular_asiento(accion, usuario, contexto=None):
    """Payload: codigo (AST-YYYY-NNNN), motivo. Anular NO crea reverso — es para
    corregir capturas; para neutralizar contablemente se captura un ajuste."""
    _gate(usuario, "puede_anular_contaduria", "anular movimientos contables")
    from apps.contaduria.services import anular_asiento as svc

    payload = accion.payload or {}
    asiento = _asiento_por_codigo(payload.get("codigo"))
    motivo = (payload.get("motivo") or "").strip()
    _exigir(bool(motivo), "`motivo` requerido para anular el movimiento contable.")
    svc(asiento, actor=usuario, motivo=motivo)
    accion.entidad_tipo = "asiento"
    accion.entidad_id = asiento.pk


# ── Edición de Catálogo (contrapartes de crear_proveedor / crear_variacion) ───────

@registrar("actualizar_proveedor")
def actualizar_proveedor(accion, usuario, contexto=None):
    """Payload: proveedor (razón social o parte), y los campos a cambiar:
    razon_social?, nombre_contacto?, email_contacto?, telefono?, rfc?,
    direccion?, notas?."""
    _gate(usuario, "puede_editar_catalogo", "editar proveedores del Catálogo")
    payload = accion.payload or {}
    prov = _resolver_proveedor(payload.get("proveedor") or payload.get("razon_social_actual"))
    cambios = []
    campos_texto = {
        "razon_social": 200, "nombre_contacto": 120, "email_contacto": 254,
        "telefono": 40, "rfc": 20,
    }
    for campo, largo in campos_texto.items():
        if payload.get(campo) not in (None, ""):
            setattr(prov, campo, str(payload[campo])[:largo])
            cambios.append(campo)
    if "direccion" in payload:
        prov.direccion = str(payload.get("direccion") or "")
        cambios.append("direccion")
    if "notas" in payload:
        prov.notas = str(payload.get("notas") or "")
        cambios.append("notas")
    _exigir(bool(cambios), "No indicaste qué cambiar del proveedor (teléfono, correo…).")
    prov.save(update_fields=[*cambios, "actualizado_en"])
    accion.entidad_tipo = "proveedor"
    accion.entidad_id = prov.pk


@registrar("actualizar_variacion")
def actualizar_variacion(accion, usuario, contexto=None):
    """Payload: variacion_id | (servicio + variacion), y los campos a cambiar:
    nombre_nuevo?, costo?, impresion_activa?, impresion_costo?,
    impresion_descripcion?, descripcion?, disponible?."""
    _gate(usuario, "puede_editar_catalogo", "editar variaciones del Catálogo")
    from apps.el_catalogo.models import Variacion

    from .catalogo import _resolver_servicio
    payload = accion.payload or {}

    var = None
    vid = payload.get("variacion_id")
    if vid:
        with contextlib.suppress(TypeError, ValueError):
            var = Variacion.objects.filter(pk=int(vid)).first()
    if var is None:
        servicio = _resolver_servicio(payload.get("servicio"), contexto)
        nombre = _limpiar_slug((payload.get("variacion") or payload.get("nombre") or "").strip())
        _exigir(bool(nombre), "Indica `variacion_id` o (`servicio` + `variacion`).")
        coincidencias = list(Variacion.objects.filter(servicio=servicio, nombre__icontains=nombre)[:2])
        _exigir(len(coincidencias) >= 1, f"No encontré la variación `{nombre}` en ese producto.")
        _exigir(len(coincidencias) == 1, "Varias variaciones coinciden; usa `variacion_id`.")
        var = coincidencias[0]

    cambios = []
    if payload.get("nombre_nuevo"):
        var.nombre = str(payload["nombre_nuevo"])[:150]
        cambios.append("nombre")
    if payload.get("costo") not in (None, ""):
        var.costo = _decimal(payload.get("costo"), "costo")
        cambios.append("costo")
    if "impresion_activa" in payload:
        var.impresion_activa = bool(payload["impresion_activa"])
        cambios.append("impresion_activa")
    if payload.get("impresion_costo") not in (None, ""):
        var.impresion_costo = _decimal(payload.get("impresion_costo"), "impresion_costo")
        cambios.append("impresion_costo")
    if "impresion_descripcion" in payload:
        var.impresion_descripcion = str(payload.get("impresion_descripcion") or "")[:250]
        cambios.append("impresion_descripcion")
    if "descripcion" in payload:
        var.descripcion = str(payload.get("descripcion") or "")[:500]
        cambios.append("descripcion")
    if "disponible" in payload:
        var.disponible = bool(payload["disponible"])
        cambios.append("disponible")
    _exigir(bool(cambios), "No indicaste qué cambiar de la variación (costo, nombre…).")
    var.save(update_fields=[*cambios, "actualizado_en"])
    accion.entidad_tipo = "variacion"
    accion.entidad_id = var.pk
