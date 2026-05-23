"""Vistas compartidas HTMX para el aviso de deploy (banner + semáforo).

Importar desde el `urls.py` de cada Django project:

    from lib.aviso_deploy_views import banner_deploy, semaforo_deploy
    urlpatterns += [
        path("sistema/aviso-deploy/", banner_deploy),
        path("sistema/aviso-deploy/semaforo/", semaforo_deploy),
    ]
"""

from __future__ import annotations

from django.shortcuts import render

from lib.aviso_deploy import obtener_deploy_en_curso


def banner_deploy(request):
    """GET /sistema/aviso-deploy/ — devuelve el partial con el banner.

    Always renders the partial; el partial decide si mostrar el contenido
    o quedarse vacío. Mantiene el polling HTMX activo sin importar el estado.
    """
    sha = obtener_deploy_en_curso()
    return render(
        request,
        "_componentes_tailadmin/_banner_deploy.html",
        {"hay_deploy_en_curso": bool(sha), "deploy_commit_sha": sha},
    )


def semaforo_deploy(request):
    """GET /sistema/aviso-deploy/semaforo/ — devuelve el partial del semáforo.

    🟢 todo OK · 🔴 deploy en curso. Self-replacing HTMX cada 10s.
    """
    sha = obtener_deploy_en_curso()
    return render(
        request,
        "_componentes_tailadmin/_semaforo_deploy.html",
        {"hay_deploy_en_curso": bool(sha), "deploy_commit_sha": sha},
    )
