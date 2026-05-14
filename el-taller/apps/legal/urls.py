from django.urls import path

from . import views

urlpatterns = [
    path("privacidad", views.privacidad, name="legal-privacidad"),
    path("terminos", views.terminos, name="legal-terminos"),
]
