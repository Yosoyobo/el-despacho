"""DSL acotado para KPIs custom (S2b.5 · v2 para el constructor de La Gerencia).

EJECUCIÓN SIEMPRE VETADA — el DSL NO permite SQL ni ORM libre. Cada
campo cruza un whitelist (`schema.py`) antes de tocar la base.

Definición v1 (sigue valiendo tal cual, y se normaliza igual):
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

v2 agrega, todo opcional: `duracion` (en vez de `campo`), `campo_fecha`,
filtros `vacio` / fechas relativas ("hoy", "hace_N_dias", "en_N_dias") /
`campo_ref` (comparar contra otro campo), `tipo: "porcentaje"` +
`filtros_numerador`, `agrupar_por` + `top`, `comparar`, `formato`,
`direccion`.

Resultado: `{"valor", "numero", "nota", "link", "formato", "direccion"}` —la
forma de los KPIs del catálogo (`kpis.py`)— más `grupos` y `comparacion`
cuando se piden. `valor` es un número (o «—»), nunca texto formateado.
"""

from __future__ import annotations

from .ejecutor import ejecutar, ejecutar_con_preview, entidad_disponible
from .schema import AGREGACIONES, ENTIDADES, OPS_FILTRO, VENTANAS_TIEMPO
from .ui import describir, esquema_para_ui, resumen_para_prompt
from .validador import ValidacionError, metadatos_de, permisos_de, validar

__all__ = [
    "ejecutar", "ejecutar_con_preview", "validar", "ValidacionError",
    "permisos_de", "metadatos_de", "describir", "esquema_para_ui", "resumen_para_prompt",
    "entidad_disponible",
    "ENTIDADES", "OPS_FILTRO", "AGREGACIONES", "VENTANAS_TIEMPO",
]
