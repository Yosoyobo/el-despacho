"""Los Analistas — abstracción IA multi-provider con cadena de reemplazo.

API pública:
    from lib.analistas import analizar

    resultado = analizar(estacion="cotizaciones", prompt="Redacta...", max_tokens=400)

`analizar()` resuelve la cadena de adapters configurada para la estación,
ejecuta el primero disponible, y si falla con error transitorio cae al
siguiente. Cada intento se persiste en `ajustes_analistas_log`.

En S2a.1 las estaciones aún no están en uso real — el smoke test desde
`/ajustes/` valida que ambos providers respondan a un prompt mínimo.
"""

from .base import PresupuestoIAExcedido, Resultado, ToolCall
from .reemplazo import analizar, chatear

__all__ = ["analizar", "chatear", "Resultado", "ToolCall", "PresupuestoIAExcedido"]
