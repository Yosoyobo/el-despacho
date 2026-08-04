"""Botón «Resumir pendientes» del recuadro de El Chalán en el Dashboard (2026-07).

Abre un modal (patrón Wave 5: GET HTMX → `#modal-slot`) con el reporte de
pendientes del taller que arma `pendientes.py`: texto simple, sin emojis,
títulos de sección en negritas y renglones separados por `<br>`.

**Las secciones son deterministas** (queries, no IA): un reporte operativo tiene
que ser exacto. LC 2026-08-04 (Oscar: «que este botón use IA, como el de la
página del calendario»): encima del reporte va una **lectura de dos frases** de
El Chalán — lo único que requiere criterio. Si no responde, el reporte sale igual.
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


def _lectura_html(request) -> str:
    """La frase de El Chalán sobre la carga, en su recuadro. "" si no aplica.

    Sólo se pide si el usuario tiene el permiso del Chalán: el reporte es de
    todos, la lectura con IA es de quien puede usarlo (y quien paga sus tokens).
    """
    from lib.permisos import puede_usar_chalan

    from .pendientes import texto_pendientes
    from .pendientes_ia import lectura_de_pendientes

    if not puede_usar_chalan(request.user):
        return ""
    lectura = lectura_de_pendientes(usuario=request.user,
                                    contexto_txt=texto_pendientes(request.user))
    if not lectura.get("ok"):
        return ""
    return format_html(
        '<p class="mb-4 rounded-lg border border-brand-200 bg-brand-50/60 p-3 '
        'text-sm text-brand-800 dark:border-brand-500/30 dark:bg-brand-500/10 '
        'dark:text-brand-200">🤖 {}</p>', lectura["lectura"])


@login_required
def resumen_actividad(request):
    """Modal con el resumen de la actividad pendiente del taller."""
    from .pendientes import encabezado_fecha, secciones_pendientes

    secciones = secciones_pendientes(request.user)
    cuerpo = format_html(
        '{}<div id="reporte-pendientes" class="leading-relaxed text-gray-700 dark:text-gray-200">{}</div>',
        mark_safe(_lectura_html(request)),  # noqa: S308 — HTML propio
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
        "titulo": "Resumen de pendientes",
        "cuerpo": cuerpo,
        "footer": footer,
        "tamano": "lg",
    })
