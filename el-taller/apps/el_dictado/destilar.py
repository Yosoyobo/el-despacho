"""El Chalán que aprende de su historial — wrapper de Taller (S-Chalan-Aprende-V1).

La lógica del destilador se mudó a la app compartida `chalanes/destilar.py`
(S-Chalan-Aprende-Boton) para que tanto el cron de El Taller como el botón de
"barrido" de La Gerencia disparen LA MISMA implementación, sin copias que se
desincronicen ni instalar `apps.el_dictado` en Gerencia.

Este módulo reexporta la API pública para no romper el comando cron
(`chalan_destilar_aprendizajes`) ni los imports/tests existentes que apuntan a
`apps.el_dictado.destilar`.

Trigger CLI: `python manage.py chalan_destilar_aprendizajes [--dias N] [--dry-run]`
(cron semanal, ver crontab §10). Botón equivalente en La Gerencia →
Chalanes → "Aprender de mi historial ahora".
"""

from __future__ import annotations

from chalanes.destilar import (
    ESTACION,
    MAX_CANDIDATOS,
    destilar_aprendizajes,
    recolectar_evidencia,
)

__all__ = [
    "ESTACION",
    "MAX_CANDIDATOS",
    "destilar_aprendizajes",
    "recolectar_evidencia",
]
