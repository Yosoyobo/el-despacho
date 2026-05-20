from django.urls import path

from . import views

app_name = "los_chalanes"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("cuadro/guardar", views.guardar_cuadro, name="guardar_cuadro"),
    path("cadena/reordenar", views.reordenar_cadena, name="reordenar_cadena"),
    path("cadena/toggle", views.toggle_cadena, name="toggle_cadena"),
    # Aprendizajes (S2b.2.1)
    path("aprendizajes/", views.aprendizajes_lista, name="aprendizajes-lista"),
    path("aprendizajes/nuevo", views.aprendizaje_nuevo, name="aprendizaje-nuevo"),
    path("aprendizajes/<int:pk>/editar", views.aprendizaje_editar, name="aprendizaje-editar"),
    path("aprendizajes/<int:pk>/toggle", views.aprendizaje_toggle, name="aprendizaje-toggle"),
    # KPIs custom pendientes de aprobación (S2b.5)
    path("kpis-pendientes/", views.kpis_pendientes, name="kpis-pendientes"),
    path("kpis-pendientes/<int:pk>/aprobar", views.kpi_aprobar, name="kpi-aprobar"),
    path("kpis-pendientes/<int:pk>/rechazar", views.kpi_rechazar, name="kpi-rechazar"),
]
