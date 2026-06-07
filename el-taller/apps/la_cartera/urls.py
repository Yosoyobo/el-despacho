from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="cartera-lista"),
    path("nuevo", views.nuevo, name="cartera-nuevo"),
    path("quick-create/", views.cliente_quick_create, name="cartera-quick-create"),
    path("<int:pk>/", views.detalle, name="cartera-detalle"),
    path("<int:pk>/editar", views.editar, name="cartera-editar"),
    path("<int:pk>/archivar", views.archivar, name="cartera-archivar"),
]
