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


# ── Google Drive — asistente guiado ──────────────────────────────────────────

# Email de la service account, extraído del JSON, para mostrarlo en el paso 6
# (el usuario lo necesita para compartir la carpeta). NO es secreto.
def _drive_email_servicio() -> str | None:
    import json
    crudo = Credencial.obtener("google_drive_service_account_json")
    if not crudo:
        return None
    try:
        return json.loads(crudo).get("client_email")
    except Exception:
        return None


def _drive_contexto():
    return {
        "json_configurado": Credencial.esta_configurado("google_drive_service_account_json"),
        "carpeta_configurada": Credencial.esta_configurado("google_drive_carpeta_raiz_id"),
        "carpeta_id": Credencial.obtener("google_drive_carpeta_raiz_id") or "",
        "email_servicio": _drive_email_servicio(),
        "ultimo_test": Credencial.objects.filter(
            clave="google_drive_carpeta_raiz_id"
        ).values("ultimo_test_en", "ultimo_test_ok", "ultimo_test_mensaje").first(),
    }


@requires_role("super_admin")
def google_drive_guia(request):
    return render(request, "ajustes/google_drive.html", _drive_contexto())


@requires_role("super_admin")
@require_http_methods(["POST"])
def google_drive_guardar(request):
    """Guarda los dos slots de Drive sin borrar accidentalmente.

    A diferencia del `guardar` genérico, un campo vacío NO borra el valor ya
    configurado — solo se ignora. Esto evita que el usuario pierda el JSON al
    actualizar nada más el ID de la carpeta.
    """
    from lib.google_drive import drive

    json_sa = (request.POST.get("service_account_json") or "").strip()
    carpeta = (request.POST.get("carpeta_raiz_id") or "").strip()
    # El ID a veces se pega como URL completa de Drive — extraemos el ID.
    if "drive.google.com" in carpeta and "/folders/" in carpeta:
        carpeta = carpeta.split("/folders/", 1)[1].split("?")[0].split("/")[0]

    guardados = []
    if json_sa:
        Credencial.guardar("google_drive_service_account_json", json_sa, usuario=request.user)
        guardados.append("cuenta de servicio")
    if carpeta:
        Credencial.guardar("google_drive_carpeta_raiz_id", carpeta, usuario=request.user)
        guardados.append("carpeta")

    if guardados:
        drive.recargar()
        emitir(EventoPortavoz(
            tipo="ajuste.credencial_guardada",
            actor_id=request.user.pk,
            actor_email=request.user.email,
            payload={"clave": "google_drive", "campos": guardados},
        ))
        messages.success(request, f"Guardado ({', '.join(guardados)}). Ahora prueba la conexión.")
    else:
        messages.info(request, "No escribiste nada nuevo; no se cambió la configuración.")
    return redirect("ajustes-google-drive")


@requires_role("super_admin")
@require_http_methods(["POST"])
def google_drive_probar(request):
    """Llama de verdad a Drive y guarda el resultado para mostrar el semáforo."""
    from django.utils import timezone

    from lib.google_drive import drive
    res = drive.probar()

    # Persistimos el resultado en el slot de la carpeta (sirve de ancla para el
    # semáforo aunque el JSON esté vacío). Solo si la fila existe.
    fila = Credencial.objects.filter(clave="google_drive_carpeta_raiz_id").first()
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
