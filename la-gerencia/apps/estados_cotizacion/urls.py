from django.urls import path

from . import views

urlpatterns = [
    path("estados-cotizacion/", views.lista, name="estados-cotizacion-lista"),
    path("estados-cotizacion/nuevo/", views.nuevo, name="estados-cotizacion-nuevo"),
    path("estados-cotizacion/<slug:slug>/editar/", views.editar, name="estados-cotizacion-editar"),
    path("estados-cotizacion/<slug:slug>/toggle/", views.toggle_activo, name="estados-cotizacion-toggle"),
    path("estados-cotizacion/<slug:slug>/borrar/", views.borrar, name="estados-cotizacion-borrar"),
]
