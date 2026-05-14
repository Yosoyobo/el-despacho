"""Los Ajustes — UI para configurar TODAS las credenciales del sistema.
Solo super_admin (regla #3). Los valores se cifran con La Bóveda antes de DB.
"""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from ajustes.models.credencial import SLOTS_CREDENCIAL, Credencial
from lib.permisos import requires_role
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


def _estado_slots():
    """Devuelve [(clave, etiqueta, descripcion, configurado_bool), ...] para la UI."""
    configurados = set(Credencial.objects.values_list("clave", flat=True))
    return [
        (clave, etiqueta, desc, clave in configurados)
        for (clave, etiqueta, desc) in SLOTS_CREDENCIAL
    ]


@requires_role("super_admin")
def panel(request):
    return render(request, "ajustes/panel.html", {"slots": _estado_slots()})


@requires_role("super_admin")
@require_http_methods(["POST"])
def guardar(request):
    clave = (request.POST.get("clave") or "").strip()
    valor = (request.POST.get("valor") or "").strip()
    if not clave:
        messages.error(request, "Clave requerida.")
        return redirect("ajustes-panel")

    # Validar contra catálogo conocido o aceptar custom (extensible)
    claves_conocidas = {c for c, _, _ in SLOTS_CREDENCIAL}
    if clave not in claves_conocidas and not request.POST.get("permitir_custom"):
        messages.error(request, f"Slot desconocido: {clave}")
        return redirect("ajustes-panel")

    Credencial.guardar(clave, valor, usuario=request.user)
    if valor:
        messages.success(request, f"Credencial '{clave}' guardada (cifrada).")
        emitir(EventoPortavoz(
            tipo="ajuste.credencial_guardada",
            actor_id=request.user.pk,
            actor_email=request.user.email,
            payload={"clave": clave},
        ))
    else:
        messages.success(request, f"Credencial '{clave}' eliminada.")
    return redirect("ajustes-panel")


@requires_role("super_admin")
@require_http_methods(["POST"])
def probar(request, clave: str):
    """Stub de prueba — en S2+ cada slot tendrá su prueba real (ping a API, etc).
    Por ahora valida que el valor sea descifrable."""
    val = Credencial.obtener(clave)
    if val is None:
        messages.error(request, f"'{clave}' no está configurado.")
    else:
        messages.success(request, f"'{clave}' es descifrable (longitud {len(val)} chars).")
    return redirect("ajustes-panel")
