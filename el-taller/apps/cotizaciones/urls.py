from django.urls import path

from . import views

app_name = "cotizaciones"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nueva/", views.nuevo, name="nuevo"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/enviar/", views.enviar, name="enviar"),
    path("<int:pk>/aprobar/", views.aprobar, name="aprobar"),
    path("<int:pk>/rechazar/", views.rechazar, name="rechazar"),
    path("<int:pk>/anular/", views.anular, name="anular"),
    path("<int:pk>/duplicar/", views.duplicar, name="duplicar"),
    path("<int:pk>/factura-anticipo/", views.factura_anticipo, name="factura-anticipo"),
]
