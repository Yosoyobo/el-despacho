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
    # Asistente guiado de Google Drive (OAuth sin clave). Antes del slug catch-all.
    path("google-drive/", views.google_drive_guia, name="ajustes-google-drive"),
    path("google-drive/conectar", views.google_drive_conectar, name="ajustes-google-drive-conectar"),
    path("google-drive/oauth/callback", views.google_drive_callback, name="ajustes-google-drive-callback"),
    path("google-drive/desconectar", views.google_drive_desconectar, name="ajustes-google-drive-desconectar"),
    path("google-drive/probar", views.google_drive_probar, name="ajustes-google-drive-probar"),
    path("<slug:clave>/probar", views.probar, name="ajustes-probar"),
    path("tasas/", views.tasas_lista, name="ajustes-tasas"),
    path("tasas/nueva", views.tasa_nueva, name="ajustes-tasa-nueva"),
    path("tasas/<int:pk>/editar", views.tasa_editar, name="ajustes-tasa-editar"),
    # S-LC-Feedback-V5 c6: orden y visibilidad del sidebar de El Taller (global).
    path("sidebar/", views.sidebar_panel, name="ajustes-sidebar"),
    path("sidebar/guardar", views.sidebar_guardar, name="ajustes-sidebar-guardar"),
    # S-LC-Feedback-V5 c8: metas KPI.
    path("metas-kpi/", views.metas_kpi_panel, name="ajustes-metas-kpi"),
    path("metas-kpi/guardar", views.metas_kpi_guardar, name="ajustes-metas-kpi-guardar"),
]
