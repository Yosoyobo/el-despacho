from django.urls import path

from . import views

urlpatterns = [
    path("tipos-buzon/", views.lista, name="tipos-buzon-lista"),
    path("tipos-buzon/nuevo/", views.nuevo, name="tipos-buzon-nuevo"),
    path("tipos-buzon/<slug:slug>/editar/", views.editar, name="tipos-buzon-editar"),
    path("tipos-buzon/<slug:slug>/toggle/", views.toggle_activo, name="tipos-buzon-toggle"),
    path("tipos-buzon/<slug:slug>/borrar/", views.borrar, name="tipos-buzon-borrar"),
]
