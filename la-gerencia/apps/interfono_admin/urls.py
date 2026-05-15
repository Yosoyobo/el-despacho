from django.urls import path

from . import views

urlpatterns = [
    path("", views.tablero, name="interfono-tablero"),
    path("enviar", views.enviar, name="interfono-enviar"),
]
