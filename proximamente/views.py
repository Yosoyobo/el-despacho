from django.http import Http404
from django.shortcuts import redirect, render

MODULOS = {
    # `recados` ya está vivo (S2b.1) — se removió del placeholder.
    "tesoreria": {
        "nombre": "La Tesorería",
        "icono": "💰",
        "descripcion": (
            "Ingresos, egresos, cuentas por cobrar y por pagar, reembolsos y "
            "reportes de flujo de caja. Incluye OCR de recibos y dictado de "
            "gastos por El Chalán."
        ),
        "sprint": "S2b",
        "documento": "DOC_06",
    },
    "chalanes": {
        "nombre": "Los Chalanes",
        "icono": "🤖",
        "descripcion": (
            "Cuadro de Los Chalanes: gestión del motor de IA (Claudio, GPT, "
            "Chino…), aprendizajes capturados desde El Dictado y métricas de "
            "costo y latencia."
        ),
        "sprint": "pre-S2b",
        "documento": "DOC_02",
    },
    "dictado-historial": {
        "nombre": "Histórico de El Dictado",
        "icono": "🎙️",
        "descripcion": (
            "Tu historial personal de dictados al Chalán: texto crudo, "
            "interpretación, acciones aplicadas y errores."
        ),
        "sprint": "S2b",
        "documento": "DOC_04",
    },
    "referencias": {
        "nombre": "Sistema de Referencias",
        "icono": "🔗",
        "descripcion": (
            "Mecanismo único `@/#/$` para mencionar usuarios, proyectos y "
            "clientes desde cualquier campo de texto del sistema."
        ),
        "sprint": "pre-S2b",
        "documento": "DOC_01",
    },
}


def modulo(request, modulo):
    """Render the coming-soon placeholder for a known future module slug."""
    contexto = MODULOS.get(modulo)
    if contexto is None:
        raise Http404("Módulo desconocido")
    return render(
        request,
        "proximamente/pagina.html",
        {"modulo": contexto, "slug": modulo},
    )


def indice(request):
    """If someone hits /proximamente/ without slug, go home."""
    return redirect("/")
