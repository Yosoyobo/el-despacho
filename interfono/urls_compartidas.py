"""URLs compartidas: /sw.js + endpoints de suscripción.

Cada app raíz (la_gerencia, el_taller, la_recepcion) incluye este urlconf en
la raíz de su urls.py para tener el SW disponible. El endpoint de suscripción
y prueba quedan disponibles bajo `/perfil/notificaciones/...` en El Taller y
La Gerencia (La Recepción solo expone `/sw.js`).
"""

from django.urls import path

from interfono.sw_js import sw_js
from interfono.views_compartidas import desuscribir, marcar_clickeado, prueba, suscribir

urlpatterns_sw = [
    path("sw.js", sw_js, name="interfono-sw"),
]

urlpatterns_suscripcion = [
    path("perfil/notificaciones/suscribir", suscribir, name="interfono-suscribir"),
    path("perfil/notificaciones/<int:sub_id>/desuscribir", desuscribir, name="interfono-desuscribir"),
    path("perfil/notificaciones/prueba", prueba, name="interfono-prueba"),
    path(
        "perfil/notificaciones/<int:entrega_id>/clickeado",
        marcar_clickeado,
        name="interfono-marcar-clickeado",
    ),
]
