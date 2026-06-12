"""Anti cross-wiring proveedor↔modelo en el Cuadro de Chalanes.

Sin credenciales, `listar_modelos()` cae a la lista curada de cada adapter,
así que estas aserciones son deterministas en CI.
"""

from lib.analistas.registry import modelo_default_de, modelo_valido, modelos_por_proveedor


def test_modelos_curados_por_proveedor():
    mapa = modelos_por_proveedor(forzar=True)
    assert "deepseek-chat" in mapa["deepseek"]
    assert "claude-haiku-4-5" in mapa["anthropic"]
    assert mapa["gemini"]  # no vacío


def test_modelo_valido_corrige_cross_wire():
    # Deepseek con un modelo de Anthropic → cae al default de deepseek.
    assert modelo_valido("deepseek", "claude-haiku-4-5") == "deepseek-chat"


def test_modelo_valido_respeta_modelo_correcto():
    assert modelo_valido("anthropic", "claude-haiku-4-5") == "claude-haiku-4-5"


def test_modelo_valido_vacio_usa_default():
    assert modelo_valido("openai", "") == modelo_default_de("openai") == "gpt-4o-mini"
