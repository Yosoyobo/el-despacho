from django.urls import path

from . import views

urlpatterns = [
    path("dictado/interpretar", views.interpretar_view, name="dictado-interpretar"),
    path("dictado/historial/", views.historial, name="dictado-historial"),
    path("dictado/<int:pk>/preview", views.preview, name="dictado-preview"),
    path("dictado/<int:pk>/aplicar", views.aplicar_view, name="dictado-aplicar"),
    path("dictado/<int:pk>/cancelar", views.cancelar, name="dictado-cancelar"),
    path("dictado/<int:pk>/", views.detalle, name="dictado-detalle"),
]
