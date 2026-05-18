from django.urls import path

from . import views

app_name = "los_chalanes"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("cuadro/guardar", views.guardar_cuadro, name="guardar_cuadro"),
    path("cadena/reordenar", views.reordenar_cadena, name="reordenar_cadena"),
    path("cadena/toggle", views.toggle_cadena, name="toggle_cadena"),
]
