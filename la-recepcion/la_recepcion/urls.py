"""URLs de La Recepción — el portal de clientes.

Las rutas públicas están listadas en `apps.portal_cliente.middleware.RUTAS_PUBLICAS`;
todo lo demás exige una sesión de cliente viva (cerrado por default).
"""

from apps.portal_cliente import views
from django.urls import path

from lib.aviso_deploy_views import banner_deploy, semaforo_deploy
from lib.salud_views import salud

handler404 = "apps.portal_cliente.views.no_encontrado"

urlpatterns = [
    # Sondas y avisos (públicos).
    path("ping", views.ping, name="recepcion-ping"),
    # El monitor del taller pregunta aquí (ver docs/MONITOR_SALUD.md).
    path("salud", salud, name="salud"),
    path("sistema/aviso-deploy/", banner_deploy, name="aviso-deploy"),
    path("sistema/aviso-deploy/semaforo/", semaforo_deploy, name="aviso-deploy-semaforo"),
    # Entrar / salir (públicos).
    path("entrar/", views.entrar, name="recepcion-entrar"),
    path("entrar/<str:token>/", views.canjear, name="recepcion-canjear"),
    path("auth/google/iniciar", views.google_iniciar, name="recepcion-google-iniciar"),
    path("auth/google/callback", views.google_callback, name="recepcion-google-callback"),
    path("salir/", views.salir, name="recepcion-salir"),
    # Legales (§4 #8, públicos).
    path("legal/privacidad", views.privacidad, name="legal-privacidad"),
    path("legal/terminos", views.terminos, name="legal-terminos"),
    # Lo del cliente (con sesión).
    path("", views.inicio, name="recepcion-inicio"),
    path("proyectos/", views.proyectos, name="recepcion-proyectos"),
    path("proyectos/<str:codigo>/", views.proyecto, name="recepcion-proyecto"),
    path("cotizaciones/", views.cotizaciones, name="recepcion-cotizaciones"),
    path("cotizaciones/<int:pk>/", views.cotizacion, name="recepcion-cotizacion"),
    path("cotizaciones/<int:pk>/pdf/", views.cotizacion_pdf, name="recepcion-cotizacion-pdf"),
    path("cotizaciones/<int:pk>/aprobar/", views.cotizacion_aprobar, name="recepcion-cotizacion-aprobar"),
    path("cotizaciones/<int:pk>/rechazar/", views.cotizacion_rechazar, name="recepcion-cotizacion-rechazar"),
    path("facturas/", views.facturas, name="recepcion-facturas"),
    path("facturas/<int:pk>/", views.factura, name="recepcion-factura"),
    path("facturas/<int:pk>/pdf/", views.factura_pdf, name="recepcion-factura-pdf"),
    path("facturas/<int:pk>/xml/", views.factura_xml, name="recepcion-factura-xml"),
]
