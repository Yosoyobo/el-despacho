from django.urls import path

from . import views, views_kpi_custom

urlpatterns = [
    path("", views.home, name="taller-home"),
    path("ping", views.ping, name="taller-ping"),
    path("perfil/dashboard/", views.dashboard_preferencias, name="perfil-dashboard"),
    path("perfil/dashboard/guardar", views.dashboard_guardar, name="perfil-dashboard-guardar"),
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
