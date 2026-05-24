"""Catálogo tipado de eventos del Portavoz. Cada evento es un dataclass
serializable a JSON. Agrega aquí cualquier evento nuevo antes de emitirlo.

Regla #6: eventos tipados desde el día 1.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

from .fecha import ahora_mx

EventoTipo = Literal[
    "cliente.creado",
    "cliente.actualizado",
    "proyecto.creado",
    "proyecto.status_cambiado",
    "proyecto.codigo_renumerado",
    "tarea.creada",
    "tarea.completada",
    "cotizacion.creada",
    "cotizacion.actualizada",
    "cotizacion.enviada",
    "cotizacion.aprobada",
    "cotizacion.rechazada",
    "cotizacion.anulada",
    "cotizacion.vencida",
    "factura.emitida",
    "pago.recibido",
    "pago.recordatorio",
    "usuario.creado",
    "usuario.bloqueado",
    "ajuste.credencial_guardada",
    "ajuste.tasa_guardada",
    "catalogo.servicio_creado",
    "catalogo.servicio_actualizado",
    "catalogo.servicio_quick_creado",
    "catalogo.unidad_creada",
    "catalogo.unidad_actualizada",
    "proveedor.creado",
    "proveedor.actualizado",
    "proveedor.archivado",
    "proveedor.reactivado",
    "proveedor.quick_creado",
    "sidebar.orden_actualizado",
    "buzon.nuevo_mensaje",
    "buzon.estado_cambiado",
    "buzon.respondido",
    "buzon.eliminado",
    "site.integracion_fallo",
    "deploy.iniciado",
    "deploy.exitoso",
    "deploy.rollback",
    "auth.google_vinculada",
    "auth.google_error",
    "auth.google_cuenta_no_registrada",
    "recado.creado",
    "recado.editado",
    "recado.leido",
    "tesoreria.ingreso_registrado",
    "tesoreria.egreso_registrado",
    "tesoreria.ocr_procesado",
    "tesoreria.reembolso_pendiente",
    "tesoreria.ingreso_anulado",
    "tesoreria.egreso_anulado",
    "tesoreria.cuentas_por_pagar_alta",
    "tesoreria.exportado",
    "tesoreria.export_fallido",
    "centro_costo.creado",
    "centro_costo.actualizado",
    "contaduria.asiento_creado",
    "contaduria.asiento_anulado",
    "contaduria.cuenta_creada",
    "contaduria.cuenta_actualizada",
]


@dataclass
class EventoPortavoz:
    """Forma base de cualquier evento. Usa `tipo` literal para discriminar en n8n."""
    tipo: EventoTipo
    actor_id: int | None
    actor_email: str | None
    payload: dict[str, Any] = field(default_factory=dict)
    emitido_en: datetime = field(default_factory=ahora_mx)
    schema_version: int = 1

    def serializar(self) -> dict[str, Any]:
        d = asdict(self)
        d["emitido_en"] = self.emitido_en.isoformat()
        return d
