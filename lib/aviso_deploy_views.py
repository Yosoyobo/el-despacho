"""Vista compartida HTMX para el banner de aviso de deploy.

Importar desde el `urls.py` de cada Django project:

    from lib.aviso_deploy_views import banner_deploy
    urlpatterns += [path("sistema/aviso-deploy/", banner_deploy)]
"""

from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import render

from lib.aviso_deploy import obtener_deploy_en_curso


def banner_deploy(request):
    """GET /sistema/aviso-deploy/ — devuelve el partial si hay deploy, 204 si no.

    Sin auth: el banner aparece también en pantallas de login (deliberado,
    para que un intento fallido durante deploy quede explicado).
    HTMX self-replacing: cuando devolvemos 204, el div se borra solo.
    """
    sha = obtener_deploy_en_curso()
    if not sha:
        return HttpResponse(status=204)
    return render(
        request,
        "_componentes_tailadmin/_banner_deploy.html",
        {"hay_deploy_en_curso": True, "deploy_commit_sha": sha},
    )
