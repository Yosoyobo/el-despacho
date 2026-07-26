"""Botón «Resumir actividad» del recuadro de El Chalán en el Dashboard (2026-07).

Abre un modal (patrón Wave 5: GET HTMX → `#modal-slot`) con el reporte de
pendientes del taller que arma `pendientes.py`: texto simple, sin emojis,
títulos de sección en negritas y renglones separados por `<br>`.

**No gasta IA**: es determinista, se arma con queries. Un reporte operativo
tiene que ser exacto (y gratis); el resumen narrativo con El Chalán vive en el
detalle de cada proyecto.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe


def _cuerpo_pendientes(secciones: list[dict], encabezado: str = "") -> str:
    """Secciones → HTML de texto simple: títulos en negritas, `<br>` entre
    renglones y una línea en blanco entre secciones.

    El encabezado (día, fecha y hora en que se generó) va hasta arriba, en
    negritas y separado del resto — decisión Oscar 2026-07-25.
    """
    partes: list[str] = []
    if encabezado:
        partes.append(f"<b>{escape(encabezado)}</b>")
    for sec in secciones:
        if partes:
            partes.append("")  # línea en blanco separadora
        partes.append(f"<b>{escape(sec['titulo'])}</b>")
        partes.extend(escape(linea) for linea in sec["lineas"])
        if not sec["lineas"]:
            partes.append("(ninguno)")
    return "<br>".join(partes)


@login_required
def resumen_actividad(request):
    """Modal con el resumen de la actividad pendiente del taller."""
    from .pendientes import encabezado_fecha, secciones_pendientes

    secciones = secciones_pendientes(request.user)
    cuerpo = format_html(
        '<div id="reporte-pendientes" class="leading-relaxed text-gray-700 dark:text-gray-200">{}</div>',
        # noqa: S308 — HTML propio, ya escapado
        mark_safe(_cuerpo_pendientes(secciones, encabezado_fecha())),
    )
    footer = mark_safe(  # noqa: S308 — HTML estático propio
        '<button type="button" class="btn-secundario" '
        "onclick=\"navigator.clipboard.writeText(document.getElementById("
        "'reporte-pendientes').innerText); this.textContent='Copiado';\">Copiar</button>"
        '<button type="button" data-modal-slot-close class="btn-primario">Cerrar</button>'
    )
    return render(request, "_componentes_tailadmin/_modal_htmx.html", {
        "titulo": "Resumen de actividad",
        "cuerpo": cuerpo,
        "footer": footer,
        "tamano": "lg",
    })
