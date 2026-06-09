"""Catálogo de estaciones del Cuadro de Chalanes.

Una estación es un caso de uso de IA: un punto del producto donde se invoca
`analizar(estacion, prompt, ...)`. Esta lista alimenta el seed inicial del
`CuadroChalanes` y la UI de `/chalanes/`.
"""

from __future__ import annotations

# (clave, etiqueta_humana, descripcion, requiere_vision, proveedor_default, modelo_default)
ESTACIONES: list[tuple[str, str, str, bool, str, str]] = [
    ("cotizaciones",       "Redactar cotización",         "Genera el cuerpo formal de una cotización para el cliente.", False, "anthropic", "claude-haiku-4-5"),
    ("gastos",             "Categorizar gasto",           "Asigna categoría contable a un gasto descrito en texto libre.", False, "deepseek", "deepseek-chat"),
    ("comunicacion",       "Resumir hilo cliente",        "Resume un hilo de mensajería con un cliente.", False, "anthropic", "claude-haiku-4-5"),
    ("precio",             "Sugerir precio",              "Estima rango de precio con base en histórico de proyectos similares.", False, "anthropic", "claude-haiku-4-5"),
    ("cliente",            "Chat con cliente",            "Asistente conversacional para la Recepción (S5).", False, "anthropic", "claude-haiku-4-5"),
    ("dictado",            "Interpretar dictado",         "Convierte texto dictado en acciones estructuradas (proyectos, tareas).", False, "anthropic", "claude-haiku-4-5"),
    ("taller_chat",        "Chat del Taller",             "Chat conversacional: consulta estatus (proyectos, finanzas, gasto IA, servidor) y propone acciones con confirmación.", False, "anthropic", "claude-haiku-4-5"),
    ("ocr_recibo",         "OCR de recibo",                "Extrae monto, fecha y concepto de la foto de un recibo.", True,  "openai",    "gpt-4o-mini"),
    ("correo_redaccion",   "Redactar correo (El Cartero)", "Redacta/mejora el HTML de las plantillas de correo respetando las variables.", False, "anthropic", "claude-haiku-4-5"),
    ("redaccion_asistida", "Redactar texto (widget 🤖)",   "El botón 🤖 redacta comentarios, notas y respuestas; resuelve @#$ a datos reales.", False, "anthropic", "claude-haiku-4-5"),
    ("smoke",              "Smoke test",                   "Prueba mínima desde Los Ajustes — un saludo.", False, "anthropic", "claude-haiku-4-5"),
]

ESTACIONES_DICT = {e[0]: {
    "etiqueta": e[1], "descripcion": e[2],
    "requiere_vision": e[3], "proveedor_default": e[4], "modelo_default": e[5],
} for e in ESTACIONES}
