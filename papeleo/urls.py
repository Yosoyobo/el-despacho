from django.urls import path

from . import entrada, views

urlpatterns = [
    path("papeleo/", views.buscar, name="papeleo-buscar"),
    path("papeleo/subir", views.subir, name="papeleo-subir"),
    path("papeleo/<int:documento_id>/", views.ver, name="papeleo-ver"),
    # El documento se sirve por proxy, con el permiso comprobado: la dirección
    # de Paperless sólo existe en el tailnet y tiene su propia sesión.
    path("papeleo/<int:documento_id>/archivo", views.archivo, name="papeleo-archivo"),
    path("papeleo/<int:documento_id>/bajar", views.descargar, name="papeleo-descargar"),
    path("papeleo/<int:documento_id>/miniatura", views.miniatura, name="papeleo-miniatura"),
    path("papeleo/sugerencias", views.sugerencias, name="papeleo-sugerencias"),
    path("papeleo/<int:documento_id>/ligar", views.ligar, name="papeleo-ligar"),
    path("papeleo/liga/<int:pk>/quitar", views.desligar, name="papeleo-desligar"),
    # La puerta del robot: sin sesión y con token. Va aparte de las pantallas a
    # propósito, para que se lea de un golpe que ésta es la que no pide login.
    path("papeleo/entra", entrada.papeleo_entrante, name="papeleo-entra"),
]
