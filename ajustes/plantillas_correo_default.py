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

# ── Variables comunes ────────────────────────────────────────────────────────
# Toda plantilla —de sistema o creada por el usuario— recibe este contexto.
# `lib.correo_contexto.armar()` es quien lo llena; si un dato no aplica llega
# como cadena vacía, NUNCA falta (una variable ausente renderiza en blanco y
# deja un hueco raro en el correo).
VARIABLES_COMUNES = [
    "cliente",        # nombre del contacto, o la razón social si no hay contacto
    "empresa",        # razón social del cliente
    "fecha",          # hoy, dd/mm/aaaa
    "representante",  # quién manda el correo
]

# Variables que sólo llegan con dato cuando el envío trae un proyecto detrás.
VARIABLES_PROYECTO = ["proyecto", "estado", "monto", "folio"]

# Texto libre: lo escribe quien manda (o El Chalán) en el momento del envío.
VARIABLES_TEXTO_LIBRE = ["asunto", "mensaje"]

# Las que puede usar una plantilla creada por el usuario. Es la unión de todo
# lo anterior: no sabemos desde dónde se va a mandar, así que se le ofrecen
# todas y las que no apliquen llegan vacías.
VARIABLES_LIBRES = VARIABLES_COMUNES + VARIABLES_PROYECTO + VARIABLES_TEXTO_LIBRE


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
    "pago": {
        "nombre": "Confirmación de pago",
        "asunto": "Pago recibido · {{ referencia }} · Learning Center",
        "variables": ["cliente", "monto", "moneda", "referencia", "metodo", "fecha"],
        "cuerpo_html": (
            '<div style="font-family:Arial,sans-serif;color:#1d2939;font-size:14px;line-height:1.5;">'
            "<p>Estimado/a {{ cliente }}:</p>"
            "<p>Confirmamos la recepción de su pago por "
            "<strong>{{ monto }} {{ moneda }}</strong> el {{ fecha }}"
            "{% if referencia %} (referencia {{ referencia }}){% endif %}.</p>"
            "<p>¡Gracias por su confianza!</p>"
            f"{_FOOTER}"
            "</div>"
        ),
    },
    "bienvenida": {
        "nombre": "Bienvenida",
        "asunto": "¡Bienvenido a Learning Center, {{ cliente }}!",
        "variables": ["cliente", "representante", "fecha"],
        "cuerpo_html": (
            '<div style="font-family:Arial,sans-serif;color:#1d2939;font-size:14px;line-height:1.5;">'
            "<p>Estimado/a {{ cliente }}:</p>"
            "<p>Nos da mucho gusto darle la bienvenida. En Learning Center diseñamos "
            "y producimos productos promocionales, arte e imagen corporativa.</p>"
            "<p>A partir de hoy su equipo de contacto le acompañará en cada proyecto. "
            "Cualquier duda, responda directamente a este correo.</p>"
            f"{_FOOTER}"
            "</div>"
        ),
    },
    # ── El Runner ────────────────────────────────────────────────────────────
    # Las dos salen de runner@: es el alias departamental que Learning Center ya
    # tiene dado de alta en Google, así que el equipo y el cliente reconocen de
    # quién viene sin tener que leer la firma.
    "ruta_runner": {
        "nombre": "Ruta del día (al runner)",
        "asunto": "Tu ruta del {{ fecha }} · {{ total_paradas }} parada{{ total_paradas|pluralize }}",
        "remitente_email": "runner@learningcenter.mx",
        "remitente_nombre": "RUNNER | LEARNING CENTER",
        "variables": ["runner", "fecha", "total_paradas", "total_km", "paradas",
                      "salida", "enlace_google", "enlace_waze", "enlace_apple",
                      "empresa"],
        "cuerpo_html": (
            '<div style="font-family:Arial,sans-serif;color:#1d2939;font-size:14px;line-height:1.5;">'
            "<p>Hola {{ runner }}:</p>"
            "<p>Ésta es tu ruta del <strong>{{ fecha }}</strong>: "
            "<strong>{{ total_paradas }}</strong> paradas"
            "{% if total_km %}, unos <strong>{{ total_km }} km</strong>{% endif %}."
            "{% if salida %} Sales de {{ salida }}.{% endif %}</p>"
            '<ol style="padding-left:18px;">'
            "{% for p in paradas %}"
            '<li style="margin-bottom:8px;">'
            "<strong>{{ p.lugar }}</strong>"
            '{% if p.cliente %}<br><span style="color:#475467;">{{ p.cliente }}</span>{% endif %}'
            "{% if p.cita %}<br>Cita a las <strong>{{ p.cita }}</strong>"
            "{% elif p.llegada %}<br>Llegada estimada {{ p.llegada }}{% endif %}"
            '{% if p.titulo %}<br><span style="color:#475467;">{{ p.titulo }}</span>{% endif %}'
            "</li>"
            "{% endfor %}"
            "</ol>"
            "<p>Ábrela en tu app de mapas:</p>"
            "<p>"
            '{% if enlace_google %}<a href="{{ enlace_google }}">Google Maps</a>&nbsp;&nbsp;{% endif %}'
            '{% if enlace_waze %}<a href="{{ enlace_waze }}">Waze</a>&nbsp;&nbsp;{% endif %}'
            '{% if enlace_apple %}<a href="{{ enlace_apple }}">Apple Maps</a>{% endif %}'
            "</p>"
            '<p style="color:#475467;font-size:12px;">Las horas son estimadas: se '
            "calculan en línea recta, sin el tráfico. Las que tienen cita son fijas.</p>"
            f"{_FOOTER}"
            "</div>"
        ),
    },
    "mandado_en_camino": {
        "nombre": "Entrega en camino (al cliente)",
        "asunto": "Tu entrega va en camino · Learning Center",
        "remitente_email": "runner@learningcenter.mx",
        "remitente_nombre": "RUNNER | LEARNING CENTER",
        "variables": ["cliente", "empresa", "proyecto", "mensaje", "fecha",
                      "runner", "posicion", "llegada"],
        "cuerpo_html": (
            '<div style="font-family:Arial,sans-serif;color:#1d2939;font-size:14px;line-height:1.5;">'
            "<p>Estimado/a {{ cliente }}:</p>"
            "<p>Tu entrega{% if proyecto %} de <strong>{{ proyecto }}</strong>{% endif %} "
            "ya salió y va en camino.</p>"
            "{% if llegada %}<p>Llegada estimada: <strong>{{ llegada }}</strong>.</p>{% endif %}"
            "{% if mensaje %}<p>{{ mensaje }}</p>{% endif %}"
            "<p>Cualquier cosa, contéstanos este correo.</p>"
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
SLUGS_PLANTILLA = ["cotizacion", "factura", "cobranza", "pago", "bienvenida",
                   "ruta_runner", "mandado_en_camino", "generico"]


def variables_de(slug: str) -> list[str]:
    """Variables que ofrece el editor para `slug`.

    Las plantillas de sistema declaran las suyas (su contexto es fijo y lo arma
    quien dispara el correo). Una plantilla creada por el usuario no tiene
    contexto predefinido, así que se le ofrecen TODAS las libres.
    """
    plantilla = PLANTILLAS_DEFAULT.get(slug)
    if plantilla is None:
        return list(VARIABLES_LIBRES)
    return plantilla.get("variables", [])


def es_de_sistema(slug: str) -> bool:
    """True si el slug es una de las plantillas que dispara el propio sistema."""
    return slug in PLANTILLAS_DEFAULT
