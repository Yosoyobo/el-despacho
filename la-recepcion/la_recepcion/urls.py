from apps.recepcion_stub import views
from django.urls import path

urlpatterns = [
    path("", views.proximamente, name="recepcion-home"),
    path("ping", views.ping, name="recepcion-ping"),
]
