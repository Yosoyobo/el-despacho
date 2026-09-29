"""La pantalla del historial de actividad — compartida por El Taller y La Gerencia.

Vive en `cuentas/` (app compartida) para que las dos apps enseñen EXACTAMENTE lo
mismo; cada una la monta en su urls.py y pone su plantilla (dual-copy, §18):

- La Gerencia → `/directorio/<pk>/actividad` (desde El Directorio y desde el
  nombre de una petición en El Site).
- El Taller → `/directorio/<pk>/actividad/` (desde la ficha de Equipo) y
  `/perfil/actividad/` (Mi actividad).

**Quién entra** (`lib.permisos.puede_ver_historial_de`): el suyo, cada quien; el
de otro, con `equipo.ver_historial`. Sin permiso es un 403 y no un 404: la
persona existe y su ficha de Equipo la ve todo el despacho, así que esconderla no
protege nada.

`?fecha=AAAA-MM-DD` elige el día (hoy por default). `?csv=dia` baja ese día y
`?csv=30` los 30 días que terminan en él.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from cuentas.models.usuario import Usuario


def _fecha(valor: str | None) -> date:
    hoy = timezone.localdate()
    try:
        elegida = date.fromisoformat((valor or "").strip())
    except ValueError:
        return hoy
    # Mañana no tiene historia, y antes de un año ya se borró.
    return min(elegida, hoy)


def _csv(persona, desde: date, hasta: date, viewer) -> HttpResponse:
    from lib import historial_actividad as ha

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    nombre = f"actividad-{persona.pk}-{desde.isoformat()}"
    if hasta != desde:
        nombre += f"-a-{hasta.isoformat()}"
    resp["Content-Disposition"] = f'attachment; filename="{nombre}.csv"'
    # BOM para que Excel abra los acentos bien a la primera.
    resp.write("﻿")
    escritor = csv.writer(resp)
    escritor.writerow(ha.CSV_COLUMNAS)
    escritor.writerows(ha.filas_csv(persona, desde, hasta, viewer=viewer))
    return resp


def _pagina(request, persona, plantilla: str, es_propia: bool):
    from lib import historial_actividad as ha
    from lib.permisos import puede_ver_historial_de, puede_ver_historial_equipo

    if not puede_ver_historial_de(request.user, persona):
        return HttpResponseForbidden(
            "Para ver la actividad de otra persona hace falta el permiso "
            "«equipo · ver_historial». Se concede en El Directorio."
        )
    fecha = _fecha(request.GET.get("fecha"))
    modo_csv = request.GET.get("csv")
    if modo_csv == "dia":
        return _csv(persona, fecha, fecha, request.user)
    if modo_csv == "30":
        return _csv(persona, fecha - timedelta(days=29), fecha, request.user)

    dia = ha.del_dia(persona, fecha, viewer=request.user)
    dias = ha.dias_con_actividad(persona, timezone.localdate(), n=21)
    anteriores = [d for d in dias if d < fecha]
    siguientes = [d for d in dias if d > fecha]
    hoy = timezone.localdate()
    return render(request, plantilla, {
        "persona": persona,
        "persona_nombre": persona.nombre_completo or persona.email,
        "es_propia": es_propia,
        "dia": dia,
        "fecha": fecha,
        "es_hoy": fecha == hoy,
        "hoy": hoy,
        "minimo": hoy - timedelta(days=ha.RETENCION_DIAS),
        "dia_anterior": anteriores[0] if anteriores else None,
        "dia_siguiente": siguientes[-1] if siguientes else None,
        "dias_recientes": dias[:10],
        "retencion_dias": ha.RETENCION_DIAS,
        # Para enlazar a otras personas desde la propia página (sólo con permiso).
        "puede_ver_otros": puede_ver_historial_equipo(request.user),
    })


def vista_persona(plantilla: str):
    """La vista de `/directorio/<pk>/actividad` con la plantilla de cada app."""
    @login_required
    def actividad(request, pk: int):
        persona = get_object_or_404(Usuario, pk=pk)
        return _pagina(request, persona, plantilla, es_propia=persona.pk == request.user.pk)

    return actividad


def vista_propia(plantilla: str):
    """Mi actividad: la de quien mira, sin permiso."""
    @login_required
    def mi_actividad(request):
        return _pagina(request, request.user, plantilla, es_propia=True)

    return mi_actividad


__all__ = ["vista_persona", "vista_propia"]
