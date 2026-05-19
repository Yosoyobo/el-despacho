from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="taller-home"),
    path("ping", views.ping, name="taller-ping"),
    path("perfil/dashboard/", views.dashboard_preferencias, name="perfil-dashboard"),
    path("perfil/dashboard/guardar", views.dashboard_guardar, name="perfil-dashboard-guardar"),
    path("perfil/dashboard/sugerencia/<int:sugerencia_id>/aceptar", views.sugerencia_aceptar, name="perfil-dashboard-sugerencia-aceptar"),
    path("perfil/dashboard/sugerencia/<int:sugerencia_id>/descartar", views.sugerencia_descartar, name="perfil-dashboard-sugerencia-descartar"),
]
