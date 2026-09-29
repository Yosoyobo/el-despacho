"""Las pestañas de El Taller (S-Pendientes-Sep28, camino B del análisis de agosto).

Cada pestaña es un documento propio dentro de un marco (`<iframe>`) de la misma
página: el sistema no se entera de que hay varias. Se eligió así porque el front
entero supone una sola página viva a la vez —un modal único, 238 identificadores
únicos, autoguardados que buscan «el formulario del proyecto»— y dos pantallas
en el mismo documento se pisarían en silencio. Con marcos, cada una tiene su
propio documento, sus propios identificadores y su propio `#modal-slot`.

Esta vista sólo sirve el contenedor: la barra y los marcos los arma
`static/js/pestanas.js`, que guarda las pestañas en el navegador
(`localStorage`, decisión de Oscar). Sólo escritorio: en el celular el guion no
arranca y el contenedor manda a la pestaña activa.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .context_processors import es_embebido


@login_required
def pestanas(request):
    # Un contenedor dentro de un marco sería una pestaña con pestañas adentro:
    # la navegación dentro de un marco nunca debe llegar aquí, pero si llega
    # (un enlace pegado a mano), se va al Dashboard.
    if es_embebido(request):
        return redirect("taller-home")
    return render(request, "taller_home/pestanas.html")
