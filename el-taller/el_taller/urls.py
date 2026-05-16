from apps.buzon_empleado import handlers as _err
from django.urls import include, path

from interfono.urls_compartidas import urlpatterns_suscripcion, urlpatterns_sw

# El admin de Django vive solo en La Gerencia (Django project con `django.contrib.admin`
# en INSTALLED_APPS). El Taller no lo necesita y no tiene la app instalada.
urlpatterns = [
    *urlpatterns_sw,
    *urlpatterns_suscripcion,
    path("", include("auth_google.urls", namespace="google_oauth")),
    path("perfil/notificaciones/", include("apps.perfil_notificaciones.urls")),
    path("", include("apps.taller_home.urls")),
    path("", include("apps.auth_taller.urls")),
    path("legal/", include("apps.legal.urls")),
    path("cartera/", include("apps.la_cartera.urls")),
    path("proyectos/", include("apps.los_proyectos.urls")),
    path("", include("apps.el_pizarron.urls")),
    path("", include("apps.buzon_empleado.urls")),
    path("proximamente/", include("proximamente.urls", namespace="proximamente")),
]

handler404 = _err.handler404
handler500 = _err.handler500
