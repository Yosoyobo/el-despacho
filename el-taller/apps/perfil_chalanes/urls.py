from django.urls import path

from . import views

urlpatterns = [
    path("perfil/chalanes/", views.panel, name="perfil-chalanes"),
    path("perfil/chalanes/guardar", views.guardar, name="perfil-chalanes-guardar"),
    path("perfil/chalanes/<slug:nombre>/saldo", views.consultar_saldo, name="perfil-chalanes-saldo"),
]
