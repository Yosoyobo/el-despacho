from django.urls import path

from . import views

urlpatterns = [
    path("", views.perfil, name="perfil-notificaciones"),
    path("categorias/", views.guardar_categorias, name="perfil-notificaciones-categorias"),
    path("formato-hora/", views.guardar_formato_hora, name="perfil-formato-hora"),
    path("historial/pagina/", views.historial_pagina, name="perfil-notificaciones-historial"),
]
