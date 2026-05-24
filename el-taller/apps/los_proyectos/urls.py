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
    # S-LC-Feedback-V5 c4: quick-edits inline desde el detalle.
    path("<int:pk>/editar-fechas", views.editar_fechas, name="proyectos-editar-fechas"),
    path("<int:pk>/editar-economico", views.editar_economico, name="proyectos-editar-economico"),
    path("<int:pk>/agregar-tarea", views.agregar_tarea_modal, name="proyectos-agregar-tarea"),
    path("<int:pk>/agregar-producto", views.agregar_producto_modal, name="proyectos-agregar-producto"),
    path("<int:pk>/quitar-producto/<int:prod_pk>", views.quitar_producto, name="proyectos-quitar-producto"),
]
