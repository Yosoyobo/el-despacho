"""Los Ajustes — UI para configurar TODAS las credenciales del sistema.
Solo super_admin (regla #3). Los valores se cifran con La Bóveda antes de DB.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from ajustes.models import TasaImpositiva
from ajustes.models.credencial import SLOTS_CREDENCIAL, Credencial
from lib.analistas import analizar as analistas_analizar
from lib.analistas.reemplazo import TodosLosAnalistasFallaron
from lib.permisos import requires_role
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import TasaForm


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


# ── Tasas Impositivas ────────────────────────────────────────────────────────

@requires_role("super_admin")
def tasas_lista(request):
    tasas = TasaImpositiva.objects.all()
    return render(request, "ajustes/tasas.html", {"tasas": tasas})


@requires_role("super_admin")
@require_http_methods(["POST"])
def probar_analistas(request):
    """Smoke test: pide a la cadena DEFAULT (Anthropic → OpenAI) responder
    'ok' a un prompt mínimo. Útil para validar configuración tras editar
    las llaves IA. No revela el contenido — solo provider/modelo/latencia."""
    prompt = "Responde la palabra 'ok' en minúsculas, nada más."
    try:
        res = analistas_analizar("smoke", prompt, max_tokens=10, temperatura=0.0, actor_id=request.user.pk)
    except TodosLosAnalistasFallaron as exc:
        messages.error(request, f"Los Analistas no respondieron: {exc}")
        return redirect("ajustes-panel")
    except Exception as exc:
        messages.error(request, f"Error permanente: {exc}")
        return redirect("ajustes-panel")
    messages.success(
        request,
        f"OK — {res.provider}/{res.modelo} respondió en {res.latencia_ms} ms (≈ ${res.costo_usd}).",
    )
    return redirect("ajustes-panel")


@requires_role("super_admin")
@require_http_methods(["GET", "POST"])
def tasa_nueva(request):
    if request.method == "POST":
        form = TasaForm(request.POST)
        if form.is_valid():
            t = form.save()
            emitir(EventoPortavoz(
                tipo="ajuste.tasa_guardada",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"tasa_id": t.pk, "nombre": t.nombre, "modo": "crear"},
            ))
            messages.success(request, f"Tasa «{t.nombre}» creada.")
            return redirect("ajustes-tasas")
    else:
        form = TasaForm()
    return render(request, "ajustes/tasa_form.html", {"form": form, "modo": "nuevo"})


@requires_role("super_admin")
@require_http_methods(["GET", "POST"])
def tasa_editar(request, pk: int):
    t = get_object_or_404(TasaImpositiva, pk=pk)
    if request.method == "POST":
        form = TasaForm(request.POST, instance=t)
        if form.is_valid():
            form.save()
            emitir(EventoPortavoz(
                tipo="ajuste.tasa_guardada",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"tasa_id": t.pk, "nombre": t.nombre, "modo": "editar"},
            ))
            messages.success(request, "Tasa actualizada.")
            return redirect("ajustes-tasas")
    else:
        form = TasaForm(instance=t)
    return render(request, "ajustes/tasa_form.html", {"form": form, "modo": "editar", "tasa": t})
