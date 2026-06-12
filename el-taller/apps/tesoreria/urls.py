from django.urls import path

from . import views

app_name = "tesoreria"

urlpatterns = [
    path("", views.landing, name="landing"),
    # Ingresos
    path("ingresos/", views.ingresos_lista, name="ingresos-lista"),
    path("ingresos/nuevo/", views.ingreso_nuevo, name="ingreso-nuevo"),
    path("ingresos/<int:pk>/", views.ingreso_detalle, name="ingreso-detalle"),
    path("ingresos/<int:pk>/editar/", views.ingreso_editar, name="ingreso-editar"),
    path("ingresos/<int:pk>/anular/", views.ingreso_anular, name="ingreso-anular"),
    # Egresos
    path("egresos/", views.egresos_lista, name="egresos-lista"),
    path("egresos/nuevo/", views.egreso_nuevo, name="egreso-nuevo"),
    path("egresos/escanear/", views.egreso_escanear, name="egreso-escanear"),
    path("egresos/<int:pk>/", views.egreso_detalle, name="egreso-detalle"),
    path("egresos/<int:pk>/editar/", views.egreso_editar, name="egreso-editar"),
    path("egresos/<int:pk>/anular/", views.egreso_anular, name="egreso-anular"),
    path("egresos/<int:pk>/reembolsar/", views.egreso_reembolsar, name="egreso-reembolsar"),
    path("egresos/<int:pk>/comprobante/", views.egreso_comprobante, name="egreso-comprobante"),
    path("egresos/sugerir-categoria/", views.egreso_sugerir_categoria, name="egreso-sugerir-categoria"),
    # CxC / CxP / reportes
    path("por-cobrar/", views.por_cobrar, name="por-cobrar"),
    path("por-pagar/", views.por_pagar, name="por-pagar"),
    path("gastos-no-registrados/", views.gastos_no_registrados, name="gastos-no-registrados"),
    path("reportes/", views.reportes, name="reportes"),
    # Exports
    path("exportar/<str:vista>.csv", views.exportar, name="exportar-csv"),
    path("exportar/<str:vista>/hoja", views.exportar_sheets, name="exportar-sheets"),
    # API JSON para autocompletar
    path("api/proyecto/<int:pk>/datos/", views.api_proyecto_datos, name="api-proyecto-datos"),
]
