from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="directorio-lista"),
    path("nuevo", views.crear, name="directorio-crear"),
    path("<int:pk>/editar", views.editar, name="directorio-editar"),
    path("<int:pk>/bloquear", views.bloquear, name="directorio-bloquear"),
]
