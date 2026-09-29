"""URLs de La Nómina (El Taller, `/nomina/`) — S-Checador-V2."""

from __future__ import annotations

from django.urls import path

from . import views_nomina as v

app_name = "nomina"

urlpatterns = [
    path("", v.lista, name="lista"),
    path("abrir", v.abrir, name="abrir"),
    path("quincena/<int:pk>/", v.periodo, name="periodo"),
    path("quincena/<int:pk>/calcular", v.calcular, name="calcular"),
    path("quincena/<int:pk>/cerrar", v.cerrar, name="cerrar"),
    path("quincena/<int:pk>/csv", v.exportar_csv, name="csv"),
    path("recibo/<int:pk>/", v.recibo, name="recibo"),
    path("recibo/<int:pk>/pagar", v.pagar, name="pagar"),
    path("recibo/<int:pk>/pdf", v.recibo_pdf, name="recibo_pdf"),
    path("sueldos/", v.sueldos, name="sueldos"),
    path("sueldos/nuevo", v.sueldo_nuevo, name="sueldo_nuevo"),
    path("sueldos/<int:pk>/", v.sueldo_editar, name="sueldo_editar"),
    path("sueldos/<int:pk>/borrar", v.sueldo_borrar, name="sueldo_borrar"),
    path("prestamos/", v.prestamos, name="prestamos"),
    path("prestamos/nuevo", v.prestamo_nuevo, name="prestamo_nuevo"),
    path("prestamos/<int:pk>/", v.prestamo, name="prestamo"),
]
