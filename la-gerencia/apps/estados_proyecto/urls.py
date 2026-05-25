from django.urls import path

from . import views

urlpatterns = [
    path("estados-proyecto/", views.lista, name="estados-proyecto-lista"),
    path("estados-proyecto/nuevo/", views.nuevo, name="estados-proyecto-nuevo"),
    path("estados-proyecto/<slug:slug>/editar/", views.editar, name="estados-proyecto-editar"),
    path("estados-proyecto/<slug:slug>/borrar/", views.borrar, name="estados-proyecto-borrar"),
]
