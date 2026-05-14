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
    "proyecto.creado",
    "proyecto.status_cambiado",
    "tarea.creada",
    "tarea.completada",
    "cotizacion.enviada",
    "factura.emitida",
    "pago.recibido",
    "pago.recordatorio",
    "usuario.creado",
    "usuario.bloqueado",
    "ajuste.credencial_guardada",
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
