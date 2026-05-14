from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="taller-home"),
    path("ping", views.ping, name="taller-ping"),
]
