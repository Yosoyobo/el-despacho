from apps.buzon_admin import handlers as _err
from apps.interfono_admin.views import perfil_notificaciones as _perfil_notif
from django.conf import settings
from django.urls import include, path, re_path

from interfono.urls_compartidas import urlpatterns_suscripcion, urlpatterns_sw
from lib.aviso_deploy_views import banner_deploy, semaforo_deploy


def _redirect_a_taller(prefijo: str):
    """Devuelve view function que redirige `prefijo + resto` a Taller."""
    from django.http import HttpResponseRedirect

    def _vista(request, resto: str = ""):
        base = getattr(settings, "TALLER_URL", "https://taller.ninomeando.com/").rstrip("/") + "/"
        destino = f"{base}{prefijo.strip('/')}/{resto}"
        if request.META.get("QUERY_STRING"):
            destino += "?" + request.META["QUERY_STRING"]
        return HttpResponseRedirect(destino)
    return _vista

urlpatterns = [
    path("sistema/aviso-deploy/", banner_deploy, name="aviso-deploy"),
    path("sistema/aviso-deploy/semaforo/", semaforo_deploy, name="aviso-deploy-semaforo"),
    *urlpatterns_sw,
    *urlpatterns_suscripcion,
    path("", include("auth_google.urls", namespace="google_oauth")),
    path("interfono/", include("apps.interfono_admin.urls")),
    path("perfil/notificaciones/", _perfil_notif, name="interfono-perfil"),
    path("", include("apps.gerencia_home.urls")),
    path("", include("apps.auth_gerencia.urls")),
    path("directorio/", include("apps.el_directorio.urls")),
    path("ajustes/", include("apps.los_ajustes.urls")),
    path("legal/", include("apps.legal.urls")),
    # Pre-S2b.2: Catálogo y Buzón viven en El Taller. Aquí solo redirects
    # para preservar bookmarks viejos.
    re_path(r"^catalogo/(?P<resto>.*)$", _redirect_a_taller("catalogo/")),
    re_path(r"^buzon/(?P<resto>.*)$", _redirect_a_taller("buzon/")),
    path("catalogos/", include("apps.centros_costo.urls")),
    path("site/", include("apps.el_site.urls")),
    path("chalanes/", include("apps.los_chalanes.urls", namespace="los_chalanes")),
    path("proximamente/", include("proximamente.urls", namespace="proximamente")),
    path("api/", include("referencias.urls", namespace="referencias")),
    path("", include("apps.api.urls")),
]

handler404 = _err.handler404
handler500 = _err.handler500
