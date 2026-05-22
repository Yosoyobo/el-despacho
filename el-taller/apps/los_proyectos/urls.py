from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="proyectos-lista"),
    path("kanban/", views.kanban, name="proyectos-kanban"),
    path("nuevo", views.nuevo, name="proyectos-nuevo"),
    path("cliente-nuevo/", views.cliente_inline, name="proyectos-cliente-inline"),
    path("<int:pk>/", views.detalle, name="proyectos-detalle"),
    path("<int:pk>/editar", views.editar, name="proyectos-editar"),
    path("<int:pk>/cambiar-estado", views.cambiar_estado, name="proyectos-cambiar-estado"),
    path("<int:pk>/asignar", views.asignar, name="proyectos-asignar"),
]
