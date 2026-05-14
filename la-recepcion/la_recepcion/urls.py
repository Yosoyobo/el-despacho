from django.urls import path

from apps.recepcion_stub import views

urlpatterns = [
    path("", views.proximamente, name="recepcion-home"),
    path("ping", views.ping, name="recepcion-ping"),
]
