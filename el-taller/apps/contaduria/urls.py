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
]
