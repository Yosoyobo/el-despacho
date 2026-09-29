"""Los documentos de La Imprenta en El Taller: verlos y bajarlos en PDF.

Una sola vista para todos los tipos nuevos (recibo de pago, estado de cuenta,
remisión, orden de trabajo, reembolso…): cada `Documento` dice de dónde salen
sus datos y quién lo puede ver. **El permiso es el del módulo del documento**
(finanzas, facturación, el proyecto): La Imprenta no abre nada que la persona no
pueda ver ya en su pantalla.
"""

from __future__ import annotations

from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


def _documento_y_objeto(request, tipo: str, pk: int):
    from .tipos import DOCUMENTOS

    doc = DOCUMENTOS.get(tipo)
    if doc is None:
        raise Http404("Documento desconocido.")
    try:
        obj = doc.obtener(pk)
    except Exception:  # noqa: BLE001 — DoesNotExist de cualquier modelo
        raise Http404("No existe.") from None
    # 404 y no 403: no se revela que el documento existe.
    if not doc.puede(request.user, obj):
        raise Http404("No existe.")
    return doc, obj


@login_required
def ver(request, tipo: str, pk: int):
    """La hoja en pantalla, con su botón de «Bajar PDF»."""
    from .documentos import base

    doc, obj = _documento_y_objeto(request, tipo, pk)
    cfg = base.configuracion(doc, destino="pantalla")
    html = base.dibujar(doc, obj, cfg, preview=True,
                        url_pdf=reverse("imprenta:pdf", args=[tipo, pk]))
    return HttpResponse(html)


@login_required
def pdf(request, tipo: str, pk: int):
    """El PDF, armado por el motor propio. Sin motor, la versión imprimible."""
    from .documentos import base

    doc, obj = _documento_y_objeto(request, tipo, pk)
    contenido = base.pdf(doc, obj)
    if not contenido:
        messages.warning(request, "El motor de PDF no contesta: aquí está la versión imprimible.")
        return redirect("imprenta:ver", tipo=tipo, pk=pk)
    nombre = f"{base.nombre_archivo(doc, obj, base.configuracion(doc))}.pdf"
    ascii_ = nombre.encode("ascii", "ignore").decode() or f"{tipo}-{pk}.pdf"
    resp = HttpResponse(contenido, content_type="application/pdf")
    resp["Content-Disposition"] = f"attachment; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nombre)}"
    return resp
