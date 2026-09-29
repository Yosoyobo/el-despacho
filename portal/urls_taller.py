"""Las dos puertas del equipo (El Taller). Se montan en `/recepcion/`."""

from django.urls import path

from . import views_taller

urlpatterns = [
    path("recepcion/cliente/<int:cliente_pk>/invitar/", views_taller.invitar, name="portal-invitar"),
    path("recepcion/acceso/<int:acceso_pk>/revocar/", views_taller.revocar, name="portal-revocar"),
]
