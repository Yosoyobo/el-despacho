from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="buzon-admin-lista"),
    path("<int:pk>/", views.detalle, name="buzon-admin-detalle"),
    path("<int:pk>/exportar.md", views.exportar_a_claude, name="buzon-admin-exportar"),
]
