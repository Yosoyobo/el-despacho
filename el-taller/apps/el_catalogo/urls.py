from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="catalogo-lista"),
    path("nuevo", views.nuevo, name="catalogo-nuevo"),
    path("<int:pk>/editar", views.editar, name="catalogo-editar"),
    path("<int:pk>/archivar", views.archivar, name="catalogo-archivar"),
    path("<int:pk>/variaciones/", views.variaciones_lista, name="catalogo-variaciones"),
    path("<int:pk>/variaciones/nueva", views.variacion_nueva, name="catalogo-variacion-nueva"),
    path("<int:pk>/variaciones/<int:vpk>/editar", views.variacion_editar, name="catalogo-variacion-editar"),
    path("<int:pk>/variaciones/<int:vpk>/archivar", views.variacion_archivar, name="catalogo-variacion-archivar"),
    path("categorias/", views.categorias_lista, name="catalogo-categorias"),
    path("categorias/nueva", views.categoria_nueva, name="catalogo-categoria-nueva"),
    path("categorias/<int:pk>/editar", views.categoria_editar, name="catalogo-categoria-editar"),
    # S-LC-Feedback-V2: catálogo de unidades de medida
    path("unidades/", views.unidades_lista, name="catalogo-unidades"),
    path("unidades/nueva", views.unidad_nueva, name="catalogo-unidad-nueva"),
    path("unidades/<int:pk>/editar", views.unidad_editar, name="catalogo-unidad-editar"),
    path("unidades/<int:pk>/archivar", views.unidad_archivar, name="catalogo-unidad-archivar"),
    # S-LC-Feedback-V2: quick-create de Servicio desde el form de Proyecto
    path("quick-create/", views.servicio_quick_create, name="catalogo-quick-create"),
]
