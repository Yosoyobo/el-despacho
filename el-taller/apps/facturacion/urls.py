from django.urls import path

from . import views

app_name = "facturacion"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nueva/", views.nueva, name="nueva"),
    path("desde-cotizacion/<int:cot_pk>/", views.desde_cotizacion, name="desde-cotizacion"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/emitir/", views.emitir, name="emitir"),
    path("<int:pk>/cobrar/", views.registrar_cobro, name="cobrar"),
    path("<int:pk>/cancelar/", views.cancelar, name="cancelar"),
    path("<int:pk>/duplicar/", views.duplicar, name="duplicar"),
    path("api/proyecto/<int:pk>/datos/", views.api_proyecto_datos, name="api-proyecto-datos"),
    path("api/cotizacion/<int:pk>/datos/", views.api_cotizacion_datos, name="api-cotizacion-datos"),
]
