from django.urls import path

from . import views

urlpatterns = [
    path("", views.ayuda, name="ayuda"),
    path("raw", views.ayuda_raw, name="ayuda-raw"),
]
