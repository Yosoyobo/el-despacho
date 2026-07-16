"""Ejecutores de la Ola 2 CUI (S-Chalan-MCP-V1) — Facturación.

Continúa el hilo comercial (cotización → factura → cobro → cierre) cerrando los
huecos de "lo que se hace con clicks pero aún no por conversación" en La
Facturación: facturar una cotización, cancelar, duplicar y ligar una factura a
un proyecto. Los ejecutores de crear/emitir/cobrar factura ya viven en
`avanzados.py` (Fase B / S-Chalan-Barrido).

Mismo contrato que `avanzados.py`/`cui_v1.py`: `(accion, usuario, contexto)`,
lanza `ValueError` si el payload es inválido, la entidad no existe o el usuario
no tiene permiso (defensa en profundidad — el gating del catálogo ya filtra el
prompt, aquí se re-chequea antes de tocar la DB). Cada ejecutor envuelve un
service ya testeado de `apps.facturacion.services`. Nada se aplica sin la
confirmación humana que garantiza `services.aplicar` (regla §20).
"""

from __future__ import annotations

from . import _gate, registrar
from .avanzados import _cotizacion_por_codigo, _exigir, _factura_por_codigo
from .basicos import _resolver_proyecto


@registrar("crear_factura_desde_cotizacion")
def crear_factura_desde_cotizacion(accion, usuario, contexto=None):
    """Payload: codigo (de la cotización). Clona sus líneas/impuestos en una
    factura BORRADOR (no emite, no es CFDI — regla §16)."""
    _gate(usuario, "puede_crear_facturacion", "crear facturas")
    from apps.facturacion.services import crear_desde_cotizacion

    cot = _cotizacion_por_codigo((accion.payload or {}).get("codigo"))
    fac = crear_desde_cotizacion(cot, usuario)
    accion.entidad_tipo = "factura"
    accion.entidad_id = fac.pk


@registrar("cancelar_factura")
def cancelar_factura(accion, usuario, contexto=None):
    """Payload: codigo, motivo. El service bloquea cancelar una factura con
    cobros (primero se anula el ingreso) — alinea con `cancelar_factura_cobrada`
    (prohibido)."""
    _gate(usuario, "puede_cancelar_facturacion", "cancelar facturas")
    from apps.facturacion.services import cancelar

    payload = accion.payload or {}
    fac = _factura_por_codigo(payload.get("codigo"))
    motivo = (payload.get("motivo") or "").strip()
    _exigir(bool(motivo), "`motivo` requerido para cancelar la factura.")
    cancelar(fac, usuario, motivo)
    accion.entidad_tipo = "factura"
    accion.entidad_id = fac.pk


@registrar("duplicar_factura")
def duplicar_factura(accion, usuario, contexto=None):
    """Payload: codigo. Crea una copia en borrador con los mismos ítems e
    impuestos."""
    _gate(usuario, "puede_crear_facturacion", "duplicar facturas")
    from apps.facturacion.services import duplicar

    fac = _factura_por_codigo((accion.payload or {}).get("codigo"))
    nueva = duplicar(fac, usuario)
    accion.entidad_tipo = "factura"
    accion.entidad_id = nueva.pk


@registrar("ligar_factura_proyecto")
def ligar_factura_proyecto(accion, usuario, contexto=None):
    """Payload: codigo (de la factura), proyecto_slug."""
    _gate(usuario, "puede_crear_facturacion", "ligar facturas a proyectos")
    from apps.facturacion.services import ligar_a_proyecto

    payload = accion.payload or {}
    fac = _factura_por_codigo(payload.get("codigo"))
    proyecto = _resolver_proyecto(payload.get("proyecto_slug"), contexto)
    ligar_a_proyecto(fac, proyecto, usuario)
    accion.entidad_tipo = "factura"
    accion.entidad_id = fac.pk
