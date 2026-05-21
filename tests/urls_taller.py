"""URLconf de pruebas: monta solo El Taller (los S1b CRUDs)."""
from django.urls import include, path

from interfono.urls_compartidas import urlpatterns_suscripcion, urlpatterns_sw

urlpatterns = [
    *urlpatterns_sw,
    *urlpatterns_suscripcion,
    path("", include("auth_google.urls", namespace="google_oauth")),
    path("perfil/notificaciones/", include("apps.perfil_notificaciones.urls")),
    path("", include("apps.perfil_chalanes.urls")),
    path("", include("apps.taller_home.urls")),
    path("", include("apps.auth_taller.urls")),
    path("legal/", include("apps.legal.urls")),
    path("cartera/", include("apps.la_cartera.urls")),
    path("proyectos/", include("apps.los_proyectos.urls")),
    path("catalogo/", include("apps.el_catalogo.urls")),
    path("", include("apps.el_pizarron.urls")),
    path("", include("apps.buzon_empleado.urls")),
    path("recados/", include("apps.recados.urls", namespace="recados")),
    path("", include("apps.el_dictado.urls")),
    path("tesoreria/", include("apps.tesoreria.urls", namespace="tesoreria")),
    path("cotizaciones/", include("apps.cotizaciones.urls", namespace="cotizaciones")),
    path("facturacion/", include("apps.facturacion.urls", namespace="facturacion")),
    path("contaduria/", include("apps.contaduria.urls", namespace="contaduria")),
    path("proximamente/", include("proximamente.urls", namespace="proximamente")),
    path("api/", include("referencias.urls", namespace="referencias")),
]
