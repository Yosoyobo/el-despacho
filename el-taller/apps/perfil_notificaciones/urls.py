from django.urls import path

from . import views

urlpatterns = [
    path("", views.perfil, name="perfil-notificaciones"),
    path("categorias/", views.guardar_categorias, name="perfil-notificaciones-categorias"),
]
