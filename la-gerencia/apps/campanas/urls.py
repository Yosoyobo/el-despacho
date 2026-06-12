from django.urls import path

from . import views

urlpatterns = [
    path("campanas/", views.lista, name="campanas-lista"),
    path("campanas/nueva/", views.nueva, name="campanas-nueva"),
    path("campanas/<int:pk>/", views.detalle, name="campanas-detalle"),
]
