from django.urls import path

from . import views

urlpatterns = [
    path("", views.panel, name="ajustes-panel"),
    path("guardar", views.guardar, name="ajustes-guardar"),
    path("<slug:clave>/probar", views.probar, name="ajustes-probar"),
]
