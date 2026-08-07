from django.urls import path

from . import views

urlpatterns = [
    path("motivos-cancelacion/", views.lista, name="motivos-cancelacion-lista"),
    path("motivos-cancelacion/nuevo/", views.nuevo, name="motivos-cancelacion-nuevo"),
    path("motivos-cancelacion/<slug:slug>/editar/", views.editar, name="motivos-cancelacion-editar"),
    path("motivos-cancelacion/<slug:slug>/toggle/", views.toggle_activo, name="motivos-cancelacion-toggle"),
    path("motivos-cancelacion/<slug:slug>/borrar/", views.borrar, name="motivos-cancelacion-borrar"),
]
