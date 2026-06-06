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


# ── Google Drive — asistente guiado (OAuth sin clave) ─────────────────────────

_DRIVE_OAUTH_STATE = "drive_oauth_state"


def _drive_redirect_uri(request) -> str:
    """URI de callback que debe registrarse en el cliente OAuth de Google."""
    return f"{request.scheme}://{request.get_host()}/ajustes/google-drive/oauth/callback"


def _drive_contexto(request):
    from lib.google_oauth import GoogleOAuthConfig
    return {
        "oauth_listo": GoogleOAuthConfig.esta_configurado(),
        "conectado": Credencial.esta_configurado("google_drive_oauth_refresh_token"),
        "carpeta_lista": Credencial.esta_configurado("google_drive_carpeta_raiz_id"),
        "redirect_uri": _drive_redirect_uri(request),
        "ultimo_test": Credencial.objects.filter(
            clave="google_drive_oauth_refresh_token"
        ).values("ultimo_test_en", "ultimo_test_ok", "ultimo_test_mensaje").first(),
    }


@requires_role("super_admin")
def google_drive_guia(request):
    return render(request, "ajustes/google_drive.html", _drive_contexto(request))


@requires_role("super_admin")
@require_http_methods(["POST"])
def google_drive_conectar(request):
    """Arranca el consentimiento OAuth: redirige al admin a Google."""
    import secrets

    from lib.google_drive import construir_url_consentimiento
    from lib.google_oauth import GoogleOAuthConfig

    if not GoogleOAuthConfig.esta_configurado():
        messages.error(request, "Primero configura el cliente OAuth de Google (el del login con Google).")
        return redirect("ajustes-google-drive")

    state = secrets.token_urlsafe(24)
    request.session[_DRIVE_OAUTH_STATE] = state
    try:
        url = construir_url_consentimiento(_drive_redirect_uri(request), state)
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"No se pudo iniciar la conexión: {exc}")
        return redirect("ajustes-google-drive")
    return redirect(url)


@requires_role("super_admin")
def google_drive_callback(request):
    """Recibe el `code` de Google, guarda el refresh token y crea la carpeta."""
    from lib.google_drive import drive, intercambiar_codigo_por_refresh_token

    error = request.GET.get("error")
    if error:
        messages.error(request, f"Google canceló la conexión: {error}")
        return redirect("ajustes-google-drive")

    state_recibido = request.GET.get("state")
    state_esperado = request.session.pop(_DRIVE_OAUTH_STATE, None)
    if not state_esperado or state_recibido != state_esperado:
        messages.error(request, "La sesión de conexión expiró o no coincide. Intenta de nuevo.")
        return redirect("ajustes-google-drive")

    code = request.GET.get("code")
    if not code:
        messages.error(request, "Google no devolvió el código de autorización.")
        return redirect("ajustes-google-drive")

    try:
        refresh = intercambiar_codigo_por_refresh_token(code, _drive_redirect_uri(request))
        Credencial.guardar("google_drive_oauth_refresh_token", refresh, usuario=request.user)
        drive.recargar()
        drive.obtener_o_crear_carpeta_raiz()  # crea la carpeta raíz ya mismo
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"No se pudo completar la conexión: {exc}")
        return redirect("ajustes-google-drive")

    emitir(EventoPortavoz(
        tipo="ajuste.drive_conectado",
        actor_id=request.user.pk,
        actor_email=request.user.email,
        payload={},
    ))
    messages.success(request, "¡Cuenta de Google conectada! La carpeta de adjuntos quedó lista.")
    return redirect("ajustes-google-drive")


@requires_role("super_admin")
@require_http_methods(["POST"])
def google_drive_desconectar(request):
    """Borra el refresh token y el ID de carpeta (no borra la carpeta en Drive)."""
    from lib.google_drive import drive
    Credencial.guardar("google_drive_oauth_refresh_token", "")
    Credencial.guardar("google_drive_carpeta_raiz_id", "")
    drive.recargar()
    emitir(EventoPortavoz(
        tipo="ajuste.drive_desconectado",
        actor_id=request.user.pk,
        actor_email=request.user.email,
        payload={},
    ))
    messages.success(request, "Google Drive se desconectó. La carpeta sigue en tu Drive.")
    return redirect("ajustes-google-drive")


@requires_role("super_admin")
@require_http_methods(["POST"])
def google_drive_probar(request):
    """Llama de verdad a Drive y guarda el resultado para mostrar el semáforo."""
    from django.utils import timezone

    from lib.google_drive import drive
    res = drive.probar()

    fila = Credencial.objects.filter(clave="google_drive_oauth_refresh_token").first()
    if fila:
        fila.ultimo_test_en = timezone.now()
        fila.ultimo_test_ok = res["ok"]
        fila.ultimo_test_mensaje = res["mensaje"][:240]
        fila.save(update_fields=["ultimo_test_en", "ultimo_test_ok", "ultimo_test_mensaje"])

    if res["ok"]:
        messages.success(request, res["mensaje"])
    else:
        messages.error(request, res["mensaje"])
    emitir(EventoPortavoz(
        tipo="ajuste.drive_probado",
        actor_id=request.user.pk,
        actor_email=request.user.email,
        payload={"estado": res["estado"], "ok": res["ok"]},
    ))
    return redirect("ajustes-google-drive")


# ── Tasas Impositivas ────────────────────────────────────────────────────────

@requires_role("super_admin")
def tasas_lista(request):
    tasas = TasaImpositiva.objects.all()
    return render(request, "ajustes/tasas.html", {"tasas": tasas})


@requires_role("super_admin")
@require_http_methods(["POST"])
def probar_google_oauth(request):
    """Valida credenciales Google OAuth haciendo un round-trip con code dummy
    al endpoint de token. invalid_grant ⇒ credenciales OK; invalid_client ⇒
    credenciales mal."""
    from lib.google_oauth import probar_conexion
    res = probar_conexion()
    if res["ok"]:
        messages.success(request, f"Google OAuth — {res['detalle']}")
    else:
        messages.error(request, f"Google OAuth — {res['detalle']}")
    return redirect("ajustes-panel")


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
        messages.error(request, f"Los Chalanes no respondieron: {exc}")
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


# ── S-LC-Feedback-V5 c6: orden global del sidebar del Taller ───────


@requires_role("super_admin")
def sidebar_panel(request):
    from cuentas.models.sidebar_orden import SLUGS_SIDEBAR_TALLER, SidebarOrden
    existentes = {s.slug: s for s in SidebarOrden.objects.all()}
    items = []
    for slug, label in SLUGS_SIDEBAR_TALLER:
        fila = existentes.get(slug)
        items.append({
            "slug": slug,
            "label": label,
            "orden": fila.orden if fila else 999,
            "oculto": fila.oculto if fila else False,
        })
    items.sort(key=lambda x: (x["orden"], x["slug"]))
    return render(request, "ajustes/sidebar_panel.html", {"items": items})


@requires_role("super_admin")
@require_http_methods(["POST"])
def sidebar_guardar(request):
    from cuentas.models.sidebar_orden import SLUGS_SIDEBAR_TALLER, SidebarOrden
    cambios = 0
    for slug, _ in SLUGS_SIDEBAR_TALLER:
        orden_raw = request.POST.get(f"orden__{slug}", "").strip()
        oculto = request.POST.get(f"oculto__{slug}") == "1"
        try:
            orden = int(orden_raw)
        except (TypeError, ValueError):
            continue
        SidebarOrden.objects.update_or_create(
            slug=slug, defaults={"orden": orden, "oculto": oculto},
        )
        cambios += 1
    emitir(EventoPortavoz(
        tipo="sidebar.orden_actualizado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"items_actualizados": cambios},
    ))
    messages.success(request, f"Orden del sidebar guardado ({cambios} items).")
    return redirect("ajustes-sidebar")


# ── S-LC-Feedback-V5 c8: metas KPI ────────────────────────────────


@requires_role("super_admin")
def metas_kpi_panel(request):
    # Importamos perezosamente para evitar cargar `apps.taller_home` en
    # los tests de Gerencia (sus settings pueden no incluir esa app).
    try:
        from apps.taller_home.models.meta_kpi import MetaKPI
        existentes = {m.kpi_slug: m for m in MetaKPI.objects.all()}
    except Exception:
        existentes = {}
    # Slugs sugeridos (los más comunes); el super_admin puede agregar más
    # escribiendo el slug en el form. Esto es lista guía, no un cerrado.
    slugs_sugeridos = [
        ("ingresos-mes", "Ingresos del mes"),
        ("egresos-mes", "Egresos del mes"),
        ("utilidad-mes", "Utilidad del mes"),
        ("facturado-mes", "Facturado del mes"),
        ("cxc-total", "Cuentas por cobrar (objetivo: bajar)"),
        ("contaduria-utilidad-neta-mes", "Utilidad neta contable mes"),
    ]
    filas = []
    for slug, label in slugs_sugeridos:
        m = existentes.get(slug)
        filas.append({
            "slug": slug, "label": label,
            "valor": m.valor if m else "",
            "periodo": m.periodo if m else "mes",
            "activa": m.activa if m else True,
        })
    return render(request, "ajustes/metas_kpi_panel.html", {"filas": filas})


@requires_role("super_admin")
@require_http_methods(["POST"])
def metas_kpi_guardar(request):
    from decimal import Decimal, InvalidOperation

    from apps.taller_home.models.meta_kpi import MetaKPI
    cambios = 0
    for key in request.POST:
        if not key.startswith("valor__"):
            continue
        slug = key[len("valor__"):]
        valor_raw = (request.POST.get(key) or "").strip()
        if not valor_raw:
            # Vacío = borrar meta.
            MetaKPI.objects.filter(kpi_slug=slug).delete()
            cambios += 1
            continue
        try:
            valor = Decimal(valor_raw.replace(",", ""))
        except InvalidOperation:
            continue
        periodo = request.POST.get(f"periodo__{slug}", "mes")
        activa = request.POST.get(f"activa__{slug}") == "1"
        MetaKPI.objects.update_or_create(
            kpi_slug=slug,
            defaults={
                "valor": valor, "periodo": periodo, "activa": activa,
                "actualizado_por": request.user,
            },
        )
        cambios += 1
    emitir(EventoPortavoz(
        tipo="meta_kpi.actualizada",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"metas_actualizadas": cambios},
    ))
    messages.success(request, f"Metas KPI guardadas ({cambios}).")
    return redirect("ajustes-metas-kpi")
