from django.urls import path

from . import views

urlpatterns = [
    path("centros-costo/", views.lista, name="centros-costo-lista"),
    path("centros-costo/nuevo/", views.nuevo, name="centros-costo-nuevo"),
    path("centros-costo/<slug:slug>/editar/", views.editar, name="centros-costo-editar"),
    path("centros-costo/<slug:slug>/toggle/", views.toggle_activo, name="centros-costo-toggle"),
]
