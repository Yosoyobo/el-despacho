from django.urls import path

from . import views

app_name = "contaduria"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("cuentas/", views.cuentas, name="cuentas"),
    path("asientos/", views.asientos, name="asientos"),
    path("asientos/nuevo/", views.asiento_nuevo, name="asiento-nuevo"),
    path("asientos/<int:pk>/", views.asiento_detalle, name="asiento-detalle"),
    path("asientos/<int:pk>/anular/", views.asiento_anular, name="asiento-anular"),
    path("libro-mayor/<int:cuenta_pk>/", views.libro_mayor, name="libro-mayor"),
    path("balance/", views.balance, name="balance"),
    path("estado-resultados/", views.estado_resultados, name="estado-resultados"),
    path("balance-general/", views.balance_general, name="balance-general"),
    path("export/", views.export, name="export"),
    # Cierre de periodo (S3 resto)
    path("cierre/", views.cierre_lista, name="cierre-lista"),
    path("cierre/nuevo/", views.cierre_nuevo, name="cierre-nuevo"),
    path("cierre/<int:pk>/reabrir/", views.cierre_reabrir, name="cierre-reabrir"),
    # Reconciliación bancaria (S3 resto)
    path("conciliacion/", views.conciliacion_lista, name="conciliacion-lista"),
    path("conciliacion/nueva/", views.conciliacion_nueva, name="conciliacion-nueva"),
    path("conciliacion/<int:pk>/", views.conciliacion_detalle, name="conciliacion-detalle"),
    path("conciliacion/<int:pk>/importar/", views.conciliacion_importar, name="conciliacion-importar"),
    path("conciliacion/<int:pk>/automatch/", views.conciliacion_automatch, name="conciliacion-automatch"),
    path("conciliacion/linea/<int:linea_pk>/match/", views.conciliacion_match, name="conciliacion-match"),
    path("conciliacion/linea/<int:linea_pk>/desmatch/", views.conciliacion_desmatch, name="conciliacion-desmatch"),
    # Wizard "+ Nuevo movimiento" (dummy-proof)
    path("movimiento/nuevo/", views.movimiento_nuevo, name="movimiento-nuevo"),
    path("movimiento/traspaso/", views.movimiento_traspaso, name="movimiento-traspaso"),
    path("movimiento/ajuste/", views.movimiento_ajuste, name="movimiento-ajuste"),
]
