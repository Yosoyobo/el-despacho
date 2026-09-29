from django.urls import path

from . import views

app_name = "compras"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nueva/", views.nueva, name="nueva"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/estado/", views.estado, name="estado"),
]
