from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="proyectos-lista"),
    path("nuevo", views.nuevo, name="proyectos-nuevo"),
    path("<int:pk>/", views.detalle, name="proyectos-detalle"),
    path("<int:pk>/editar", views.editar, name="proyectos-editar"),
    path("<int:pk>/cambiar-estado", views.cambiar_estado, name="proyectos-cambiar-estado"),
    path("<int:pk>/asignar", views.asignar, name="proyectos-asignar"),
]
