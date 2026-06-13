from django.urls import path

from . import views, views_avatar, views_impersonar, views_kpi_custom, views_sidebar

urlpatterns = [
    path("", views.home, name="taller-home"),
    path("ping", views.ping, name="taller-ping"),
    # S-LC-Feedback-V8: impersonación de super_admin.
    path("impersonar/<int:pk>", views_impersonar.impersonar, name="impersonar"),
    path("impersonar/salir", views_impersonar.salir_impersonacion, name="impersonar-salir"),
    # S-LC-Feedback-V8: avatar del usuario (subida a Drive + proxy autenticado).
    path("perfil/avatar/", views_avatar.avatar_modal, name="perfil-avatar"),
    path("perfil/avatar-img/<str:file_id>", views_avatar.avatar_img, name="perfil-avatar-img"),
    path("perfil/dashboard/", views.dashboard_preferencias, name="perfil-dashboard"),
    # S-LC-Feedback-V7: cada usuario acomoda su propio sidebar.
    path("perfil/sidebar/", views_sidebar.sidebar_preferencias, name="perfil-sidebar"),
    path("perfil/sidebar/guardar", views_sidebar.sidebar_guardar, name="perfil-sidebar-guardar"),
    path("perfil/sidebar/restablecer", views_sidebar.sidebar_restablecer, name="perfil-sidebar-restablecer"),
    path("perfil/dashboard/guardar", views.dashboard_guardar, name="perfil-dashboard-guardar"),
    path("perfil/dashboard/reordenar", views.dashboard_reordenar, name="perfil-dashboard-reordenar"),
    path("perfil/dashboard/sugerencia/<int:sugerencia_id>/aceptar", views.sugerencia_aceptar, name="perfil-dashboard-sugerencia-aceptar"),
    path("perfil/dashboard/sugerencia/<int:sugerencia_id>/descartar", views.sugerencia_descartar, name="perfil-dashboard-sugerencia-descartar"),
    # KPIs custom (S2b.5)
    path("kpis/custom/", views_kpi_custom.lista, name="kpi-custom-lista"),
    path("kpis/custom/nuevo/", views_kpi_custom.nuevo, name="kpi-custom-nuevo"),
    path("kpis/custom/proponer", views_kpi_custom.proponer, name="kpi-custom-proponer"),
    path("kpis/custom/crear", views_kpi_custom.crear, name="kpi-custom-crear"),
    path("kpis/custom/<int:pk>/archivar", views_kpi_custom.archivar, name="kpi-custom-archivar"),
    path("kpis/custom/<int:pk>/", views_kpi_custom.previsualizar, name="kpi-custom-detalle"),
]
