"""Las puertas del equipo (El Taller). Se montan en `/recepcion/`."""

from django.urls import path

from . import views_taller

urlpatterns = [
    path("recepcion/cliente/<int:cliente_pk>/invitar/", views_taller.invitar, name="portal-invitar"),
    path("recepcion/acceso/<int:acceso_pk>/revocar/", views_taller.revocar, name="portal-revocar"),
    path("recepcion/acceso/<int:acceso_pk>/copiar-enlace/", views_taller.copiar_enlace, name="portal-copiar-enlace"),
    path("recepcion/acceso/<int:acceso_pk>/cambiar-enlace/", views_taller.cambiar_enlace, name="portal-cambiar-enlace"),
    # Documentos del cliente.
    path("recepcion/cliente/<int:cliente_pk>/documentos/", views_taller.documentos_recuadro, name="portal-documentos"),
    path("recepcion/cliente/<int:cliente_pk>/documentos/subir/", views_taller.documento_subir, name="portal-documento-subir"),
    path("recepcion/documento/<int:pk>/archivo/", views_taller.documento_archivo, name="portal-documento-archivo"),
    path("recepcion/documento/<int:pk>/revisar/", views_taller.documento_revisar, name="portal-documento-revisar"),
    path("recepcion/documento/<int:pk>/aplicar-csf/", views_taller.documento_aplicar_csf, name="portal-documento-aplicar-csf"),
    path("recepcion/documento/<int:pk>/leer/", views_taller.documento_leer, name="portal-documento-leer"),
]
