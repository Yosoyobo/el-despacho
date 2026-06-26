from django.urls import path

from . import views

app_name = "los_chalanes"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("consumo/", views.consumo, name="consumo"),
    path("auditoria/<int:pk>/", views.auditoria_detalle, name="auditoria-detalle"),
    path("cuadro/guardar", views.guardar_cuadro, name="guardar_cuadro"),
    # Prompts — voz editable (Prompt base + voces por estación)
    path("prompts/", views.prompts_voz, name="prompts-voz"),
    path("cadena/reordenar", views.reordenar_cadena, name="reordenar_cadena"),
    path("cadena/toggle", views.toggle_cadena, name="toggle_cadena"),
    # S-Chalanes-Panel: prueba de conexión + borrar llave por proveedor
    path("<slug:nombre>/probar", views.probar_chalan, name="probar_chalan"),
    path("<slug:nombre>/saldo", views.consultar_saldo_chalan, name="consultar_saldo"),
    path("<slug:nombre>/borrar-llave", views.borrar_llave, name="borrar_llave"),
    # Aprendizajes (S2b.2.1)
    path("aprendizajes/", views.aprendizajes_lista, name="aprendizajes-lista"),
    # Barrido manual: El Chalán destila aprendizajes de su historial AHORA
    path("aprendizajes/barrido", views.aprendizajes_barrido, name="aprendizajes-barrido"),
    path("aprendizajes/nuevo", views.aprendizaje_nuevo, name="aprendizaje-nuevo"),
    path("aprendizajes/<int:pk>/editar", views.aprendizaje_editar, name="aprendizaje-editar"),
    path("aprendizajes/<int:pk>/toggle", views.aprendizaje_toggle, name="aprendizaje-toggle"),
    # Conocimiento del negocio (S-Chalan-Negocio-V1)
    path("conocimiento/", views.conocimiento_lista, name="conocimiento-lista"),
    path("conocimiento/<int:pk>/toggle", views.conocimiento_toggle, name="conocimiento-toggle"),
    # KPIs custom pendientes de aprobación (S2b.5)
    path("kpis-pendientes/", views.kpis_pendientes, name="kpis-pendientes"),
    path("kpis-pendientes/<int:pk>/aprobar", views.kpi_aprobar, name="kpi-aprobar"),
    path("kpis-pendientes/<int:pk>/rechazar", views.kpi_rechazar, name="kpi-rechazar"),
]
