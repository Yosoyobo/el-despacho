from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="gerencia-home"),
    path("ping", views.ping, name="gerencia-ping"),
]
