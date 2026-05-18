"""Chalán Gemini — skeleton placeholder.

NO REGISTRAR HASTA SPRINT POSTERIOR. Pre-S2b.1 deja el archivo para que el slot
`chalan_gemini_api_key` y el choice 'gemini' en CuadroChalanes tengan referencia
de código. Cuando se active, implementar `_invocar` con la API de Google.
"""

from __future__ import annotations

from ..base import Adapter, FaltaCredencial, Resultado
from ..capacidades import Capability


class GeminiAdapter(Adapter):
    nombre = "gemini"
    apodo = "Chalán Gemini"
    capacidades = frozenset({Capability.TEXTO, Capability.VISION})

    def _llave(self) -> str:
        from ajustes.models.credencial import Credencial
        llave = Credencial.obtener("chalan_gemini_api_key")
        if not llave:
            raise FaltaCredencial("chalan_gemini_api_key no configurada")
        return llave

    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float) -> Resultado:
        raise NotImplementedError("Chalán Gemini aún no está activo — sprint posterior.")
