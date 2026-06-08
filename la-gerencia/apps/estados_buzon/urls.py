from django.urls import path

from . import views

urlpatterns = [
    path("estados-buzon/", views.lista, name="estados-buzon-lista"),
    path("estados-buzon/nuevo/", views.nuevo, name="estados-buzon-nuevo"),
    path("estados-buzon/<slug:slug>/editar/", views.editar, name="estados-buzon-editar"),
    path("estados-buzon/<slug:slug>/borrar/", views.borrar, name="estados-buzon-borrar"),
]
