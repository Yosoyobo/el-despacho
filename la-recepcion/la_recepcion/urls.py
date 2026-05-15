from apps.recepcion_stub import views
from django.urls import path

from interfono.sw_js import sw_js

urlpatterns = [
    path("sw.js", sw_js, name="interfono-sw"),
    path("", views.proximamente, name="recepcion-home"),
    path("buzon/", views.buzon_proximamente, name="recepcion-buzon"),
    path("ping", views.ping, name="recepcion-ping"),
]
