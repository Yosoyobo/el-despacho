from django.urls import path

from . import views

urlpatterns = [
    path("proyectos/<int:proyecto_id>/tareas/nueva", views.nueva_tarea, name="pizarron-nueva-tarea"),
    path("proyectos/<int:proyecto_id>/comentar", views.comentar_proyecto, name="pizarron-comentar-proyecto"),
    path("tareas/<int:pk>/", views.detalle_tarea, name="pizarron-detalle-tarea"),
    path("tareas/<int:pk>/editar", views.editar_tarea, name="pizarron-editar-tarea"),
    path("tareas/<int:pk>/comentar", views.comentar_tarea, name="pizarron-comentar-tarea"),
    path("tareas/<int:pk>/completar", views.completar_tarea, name="pizarron-completar-tarea"),
]
