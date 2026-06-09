from django.urls import path

from . import views

urlpatterns = [
    path("", views.ayuda, name="ayuda"),
    path("novedades/", views.novedades, name="ayuda-novedades"),
    path("raw", views.ayuda_raw, name="ayuda-raw"),
]
