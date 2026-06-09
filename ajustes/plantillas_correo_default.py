"""Plantillas de correo por defecto (seed + fallback de El Cartero).

Cada plantilla tiene: slug, nombre, asunto (con variables `{{ }}`), cuerpo HTML
y la lista de variables disponibles para ese contexto. El editor gráfico de La
Gerencia parte de estos defaults; el render real usa `ajustes.PlantillaCorreo`
(editable) y cae a estos si la fila está vacía.

Variables: se rellenan con un contexto ACOTADO de strings/números (no se expone
el modelo completo), renderizado con el motor de plantillas de Django.
"""

from __future__ import annotations

_FOOTER = (
    '<p style="color:#475467;">Learning Center<br>'
    '<span style="font-size:12px;color:#98a2b3;">Diseño · Maquila · Imagen corporativa</span></p>'
)

PLANTILLAS_DEFAULT: dict[str, dict] = {
    "cotizacion": {
        "nombre": "Cotización",
        "asunto": "Cotización {{ codigo }} · Learning Center",
        "variables": ["codigo", "titulo", "cliente", "total", "moneda",
                      "fecha_validez", "notas"],
        "cuerpo_html": (
            '<div style="font-family:Arial,sans-serif;color:#1d2939;font-size:14px;line-height:1.5;">'
            "<p>Estimado/a {{ cliente }}:</p>"
            "<p>Adjuntamos la cotización <strong>{{ codigo }}</strong> — {{ titulo }}, "
            "con vigencia hasta el <strong>{{ fecha_validez }}</strong>.</p>"
            "<p>Total: <strong>{{ total }} {{ moneda }}</strong>.</p>"
            "<p>Quedamos atentos a cualquier duda.</p>"
            f"{_FOOTER}"
            "</div>"
        ),
    },
    "factura": {
        "nombre": "Factura",
        "asunto": "Factura {{ codigo }} · Learning Center",
        "variables": ["codigo", "titulo", "cliente", "total", "moneda",
                      "fecha_emision", "vencimiento", "notas"],
        "cuerpo_html": (
            '<div style="font-family:Arial,sans-serif;color:#1d2939;font-size:14px;line-height:1.5;">'
            "<p>Estimado/a {{ cliente }}:</p>"
            "<p>Adjuntamos la factura <strong>{{ codigo }}</strong> — {{ titulo }}, "
            "con vencimiento <strong>{{ vencimiento }}</strong>.</p>"
            "<p>Total: <strong>{{ total }} {{ moneda }}</strong>.</p>"
            '<p style="font-size:12px;color:#98a2b3;">Documento comercial — no es un CFDI.</p>'
            f"{_FOOTER}"
            "</div>"
        ),
    },
    "cobranza": {
        "nombre": "Recordatorio de cobranza",
        "asunto": "Recordatorio de pago · Factura {{ codigo }}",
        "variables": ["codigo", "cliente", "saldo", "moneda", "vencimiento", "dias_vencida"],
        "cuerpo_html": (
            '<div style="font-family:Arial,sans-serif;color:#1d2939;font-size:14px;line-height:1.5;">'
            "<p>Estimado/a {{ cliente }}:</p>"
            "<p>Le recordamos que la factura <strong>{{ codigo }}</strong> presenta un "
            "saldo pendiente de <strong>{{ saldo }} {{ moneda }}</strong>, con "
            "vencimiento el {{ vencimiento }}.</p>"
            "<p>Agradecemos su pronto pago. Si ya realizó el pago, ignore este mensaje.</p>"
            f"{_FOOTER}"
            "</div>"
        ),
    },
    "generico": {
        "nombre": "Genérico",
        "asunto": "{{ asunto }}",
        "variables": ["cliente", "asunto", "mensaje"],
        "cuerpo_html": (
            '<div style="font-family:Arial,sans-serif;color:#1d2939;font-size:14px;line-height:1.5;">'
            "<p>Estimado/a {{ cliente }}:</p>"
            "<p>{{ mensaje }}</p>"
            f"{_FOOTER}"
            "</div>"
        ),
    },
}

# Orden de aparición en la lista del editor.
SLUGS_PLANTILLA = ["cotizacion", "factura", "cobranza", "generico"]


def variables_de(slug: str) -> list[str]:
    return PLANTILLAS_DEFAULT.get(slug, {}).get("variables", [])
