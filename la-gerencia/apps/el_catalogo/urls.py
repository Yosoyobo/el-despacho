from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="catalogo-lista"),
    path("nuevo", views.nuevo, name="catalogo-nuevo"),
    path("<int:pk>/editar", views.editar, name="catalogo-editar"),
    path("<int:pk>/archivar", views.archivar, name="catalogo-archivar"),
    path("categorias/", views.categorias_lista, name="catalogo-categorias"),
    path("categorias/nueva", views.categoria_nueva, name="catalogo-categoria-nueva"),
    path("categorias/<int:pk>/editar", views.categoria_editar, name="catalogo-categoria-editar"),
]
