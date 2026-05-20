"""DSL acotado para KPIs custom generados por el Chalán (S2b.5).

EJECUCIÓN SIEMPRE VETADA — el DSL NO permite SQL ni ORM libre. Cada
campo cruza un whitelist antes de tocar la base.

Entrada esperada:
```
{
  "entidad": "proyecto",            # ∈ ENTIDADES
  "agregacion": "count",            # ∈ AGREGACIONES
  "campo": "monto_cotizado",        # requerido si agregacion ≠ count
  "filtros": [
    {"campo": "estado", "op": "in", "valor": ["en_diseno", "en_produccion"]}
  ],
  "ventana_tiempo": "este_mes",     # ∈ VENTANAS · aplica al campo de fecha de la entidad
  "alcance_usuario": "todos"        # "todos" o "mio" (filtra por autor/asignado)
}
```

Resultado: `{"valor": int|float, "nota": str, "link": str}` — la misma
forma que los KPIs del catálogo (`kpis.py`). Esto permite que `kpis.py`
trate KPIs custom de forma intercambiable.
"""

from __future__ import annotations

from .ejecutor import ejecutar, ejecutar_con_preview
from .schema import AGREGACIONES, ENTIDADES, OPS_FILTRO, VENTANAS_TIEMPO
from .validador import ValidacionError, validar

__all__ = [
    "ejecutar", "ejecutar_con_preview", "validar", "ValidacionError",
    "ENTIDADES", "OPS_FILTRO", "AGREGACIONES", "VENTANAS_TIEMPO",
]
