from django.urls import path

from . import views, views_vivo

urlpatterns = [
    path("", views.tablero, name="site-tablero"),
    path("partial/integraciones", views.partial_integraciones, name="site-partial-integraciones"),
    path("probar/<slug:plataforma>", views.probar_plataforma, name="site-probar"),
    path("probar-todas", views.probar_todas, name="site-probar-todas"),

    # ── El Vigía: la pantalla de pared del NUC ───────────────────────────────
    # Sólo se atiende si la petición llega DIRECTO al contenedor (loopback, LAN o
    # tailnet). Por el dominio público devuelve 404 — ver `views_vivo._es_local`.
    path("vivo/", views_vivo.vivo, name="site-vivo"),
    path("vivo/fierro", views_vivo.vivo_fierro, name="site-vivo-fierro"),
    path("vivo/peticiones", views_vivo.vivo_peticiones, name="site-vivo-peticiones"),
    path("vivo/contenedores", views_vivo.vivo_contenedores, name="site-vivo-contenedores"),
    path("vivo/negocio", views_vivo.vivo_negocio, name="site-vivo-negocio"),
    path("vivo/chalanes", views_vivo.vivo_chalanes, name="site-vivo-chalanes"),
    path("vivo/ventana", views_vivo.vivo_ventana, name="site-vivo-ventana"),
    # La Limpieza. GET pinta el estado, POST la corre — un solo endpoint porque es
    # un solo partial, compartido por la pared y por El Site (regla §22).
    path("vivo/limpieza", views_vivo.vivo_limpieza, name="site-vivo-limpieza"),
]
