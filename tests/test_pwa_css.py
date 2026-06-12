"""S-LC-Feedback-V6 Bloque 8: reglas PWA en input.css (dual-copy §18).

Valida que ambas copias contengan las reglas anti-"tells" de iOS. La
verificación visual completa es manual en iPhone real.
"""

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
COPIAS = [
    RAIZ / "el-taller" / "static" / "css" / "input.css",
    RAIZ / "la-gerencia" / "static" / "css" / "input.css",
]

REGLAS_CLAVE = [
    "font-size: 16px",                 # sin zoom de iOS al enfocar inputs
    "-webkit-text-size-adjust: 100%",  # sin reescalado de texto
    "-webkit-tap-highlight-color",     # sin flash gris al tocar
    "overscroll-behavior-y: none",     # sin pull-to-refresh delator
    "min-height: 100dvh",              # viewport dinámico iOS
]


@pytest.mark.parametrize("copia", COPIAS, ids=["taller", "gerencia"])
def test_reglas_pwa_presentes(copia):
    contenido = copia.read_text()
    for regla in REGLAS_CLAVE:
        assert regla in contenido, f"falta la regla PWA «{regla}» en {copia.name}"


def test_copias_sincronizadas_bloque_pwa():
    """El bloque V6 Bloque 8 debe ser idéntico en ambas copias (regla §18)."""
    def bloque(p):
        t = p.read_text()
        i = t.index("V6 Bloque 8")
        return t[i:]
    assert bloque(COPIAS[0]) == bloque(COPIAS[1])


def test_llaves_balanceadas():
    for copia in COPIAS:
        t = copia.read_text()
        assert t.count("{") == t.count("}"), f"llaves desbalanceadas en {copia}"
