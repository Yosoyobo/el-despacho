from django.urls import path

from . import views

urlpatterns = [
    path("", views.panel, name="ajustes-panel"),
    path("guardar", views.guardar, name="ajustes-guardar"),
    # Pre-S2b.1: rutas específicas antes que el slug catch-all, si no el slug
    # captura `analistas/probar` con clave='analistas' y nunca se llega a
    # probar_analistas.
    path("analistas/probar", views.probar_analistas, name="ajustes-probar-analistas"),
    path("google_oauth/probar", views.probar_google_oauth, name="ajustes-probar-google-oauth"),
    path("<slug:clave>/probar", views.probar, name="ajustes-probar"),
    path("tasas/", views.tasas_lista, name="ajustes-tasas"),
    path("tasas/nueva", views.tasa_nueva, name="ajustes-tasa-nueva"),
    path("tasas/<int:pk>/editar", views.tasa_editar, name="ajustes-tasa-editar"),
    # S-LC-Feedback-V5 c6: orden y visibilidad del sidebar de El Taller (global).
    path("sidebar/", views.sidebar_panel, name="ajustes-sidebar"),
    path("sidebar/guardar", views.sidebar_guardar, name="ajustes-sidebar-guardar"),
]
