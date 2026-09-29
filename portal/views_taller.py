"""El Taller: invitar y revocar el acceso de un cliente a La Recepción.

Vive en la app raíz `portal/` (y no en `apps.la_cartera`) porque es la misma
lógica que La Recepción usa del otro lado; aquí sólo están las dos puertas del
equipo. Ambas por permiso granular (§4 #20) y por HTMX: re-pintan el recuadro
«Portal de clientes» de la ficha del cliente.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from lib.permisos import requiere_permiso

from . import servicios
from .models import AccesoCliente


def contexto_ficha(usuario, cliente) -> dict:
    """Lo que el recuadro de la ficha necesita. Vacío si no puede verlo."""
    from lib.permisos import (
        puede_invitar_portal,
        puede_revocar_portal,
        puede_ver_accesos_portal,
        tiene_rol,
    )

    # El failsafe duro del super_admin es el mismo que da `requiere_permiso`.
    sa = tiene_rol(usuario, "super_admin")
    ve = sa or puede_ver_accesos_portal(usuario)
    invita = sa or puede_invitar_portal(usuario)
    if not (ve or invita):
        return {"portal_visible": False}
    return {
        "portal_visible": True,
        "portal_invitables": servicios.invitables_de(cliente),
        "portal_puede_invitar": invita and cliente.activo,
        "portal_puede_revocar": sa or puede_revocar_portal(usuario),
        "portal_url": servicios.url_recepcion(),
    }


def _recuadro(request, cliente, aviso: str = "", error: str = "", status: int = 200):
    ctx = {"cliente": cliente, **contexto_ficha(request.user, cliente),
           "portal_aviso": aviso, "portal_error": error}
    return render(request, "portal/_recuadro_ficha.html", ctx, status=status)


@login_required
@require_POST
@requiere_permiso("recepcion", "invitar")
def invitar(request, cliente_pk: int):
    from apps.la_cartera.models import Cliente

    cliente = get_object_or_404(Cliente.objects.prefetch_related("contactos"), pk=cliente_pk)
    email = request.POST.get("email", "")
    try:
        res = servicios.invitar(cliente, email, request.user, request)
    except servicios.ErrorPortal as exc:
        # 200 y no 4xx: HTMX no pinta una respuesta de error y el aviso se perdería.
        return _recuadro(request, cliente, error=str(exc))
    if res.correo_ok:
        aviso = f"Listo: le mandamos a {res.acceso.email} su invitación al portal."
        return _recuadro(request, cliente, aviso=aviso)
    return _recuadro(
        request, cliente,
        error=(f"{res.acceso.email} ya tiene acceso, pero el correo no salió "
               f"({res.error_correo or 'El Cartero no contestó'}). Revisa El Cartero en "
               "Gerencia y usa «Reenviar»."))


@login_required
@require_POST
@requiere_permiso("recepcion", "revocar")
def revocar(request, acceso_pk: int):
    acceso = get_object_or_404(AccesoCliente.objects.select_related("cliente"), pk=acceso_pk)
    servicios.revocar(acceso, request.user, request)
    return _recuadro(request, acceso.cliente,
                     aviso=f"{acceso.email} ya no puede entrar al portal. Si tenía una sesión abierta, se cerró.")
