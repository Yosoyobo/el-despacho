from apps.recepcion_stub import views
from django.urls import path

from auth_google.urls_recepcion import urlpatterns as _urls_google_stub
from interfono.sw_js import sw_js

urlpatterns = [
    path("sw.js", sw_js, name="interfono-sw"),
    *_urls_google_stub,
    path("", views.proximamente, name="recepcion-home"),
    path("buzon/", views.buzon_proximamente, name="recepcion-buzon"),
    path("ping", views.ping, name="recepcion-ping"),
]
