from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="direccion-home"),
    path("ping", views.ping, name="direccion-ping"),
]
