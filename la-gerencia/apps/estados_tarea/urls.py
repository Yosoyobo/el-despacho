from django.urls import path

from . import views

urlpatterns = [
    path("estados-tarea/", views.lista, name="estados-tarea-lista"),
    path("estados-tarea/nuevo/", views.nuevo, name="estados-tarea-nuevo"),
    path("estados-tarea/<slug:slug>/editar/", views.editar, name="estados-tarea-editar"),
    path("estados-tarea/<slug:slug>/toggle/", views.toggle_activo, name="estados-tarea-toggle"),
    path("estados-tarea/<slug:slug>/borrar/", views.borrar, name="estados-tarea-borrar"),
]
