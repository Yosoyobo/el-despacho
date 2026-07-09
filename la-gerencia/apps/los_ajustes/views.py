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
from lib.permisos import requiere_permiso
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


@requiere_permiso("ajustes", "acceder")
def panel(request):
    return render(request, "ajustes/panel.html", {"slots": _estado_slots()})


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["GET", "POST"])
def recordatorios_panel(request):
    """Config global de recordatorios de tareas por vencer (S-Chalanes-UX #4)."""
    from cuentas.models import ConfigRecordatorios

    config = ConfigRecordatorios.get_solo()
    if request.method == "POST":
        config.dias_antes_csv = (request.POST.get("dias_antes_csv") or "").strip()
        config.avisar_el_dia = bool(request.POST.get("avisar_el_dia"))
        config.avisar_vencidas = bool(request.POST.get("avisar_vencidas"))
        config.incluir_asignado = bool(request.POST.get("incluir_asignado"))
        config.incluir_lider = bool(request.POST.get("incluir_lider"))
        config.incluir_admins = bool(request.POST.get("incluir_admins"))
        config.activo = bool(request.POST.get("activo"))
        config.save()
        emitir(EventoPortavoz(
            tipo="recordatorios.config_actualizada",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"activo": config.activo, "dias_antes": config.dias_antes},
        ))
        messages.success(request, "Configuración de recordatorios guardada.")
        return redirect("ajustes-recordatorios")
    return render(request, "ajustes/recordatorios.html", {"config": config})


@requiere_permiso("ajustes", "acceder")
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


@requiere_permiso("ajustes", "acceder")
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


# ── El Cartero — canal de correo (SMTP / n8n) ─────────────────────────────


def _estado_smtp():
    """[(clave, etiqueta, descripcion, tipo_input, valor_o_configurado), ...]."""
    from lib.cartero import SLOTS_SMTP
    out = []
    for clave, etiqueta, desc, tipo in SLOTS_SMTP:
        val = Credencial.obtener(clave) or ""
        # No revelamos contraseñas: solo si están configuradas. El resto sí
        # se muestra (host/puerto/usuario/remitente no son secretos).
        if tipo == "password":
            out.append((clave, etiqueta, desc, tipo, "", bool(val)))
        else:
            out.append((clave, etiqueta, desc, tipo, val, bool(val)))
    return out


@requiere_permiso("ajustes", "acceder")
def cartero_panel(request):
    """Asistente de El Cartero: elige canal (SMTP/n8n) + configura SMTP."""
    from ajustes.models import ConfiguracionCorreo
    from lib import cartero
    cfg = ConfiguracionCorreo.obtener()
    return render(request, "ajustes/cartero.html", {
        "cfg": cfg,
        "smtp_slots": _estado_smtp(),
        "n8n_configurado": bool(Credencial.obtener("n8n_webhook_url")),
        "proveedor_activo": cfg.proveedor,
        "configurado": cartero.esta_configurado(),
    })


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def cartero_guardar(request):
    """Guarda el canal activo + nombre del remitente + slots SMTP."""
    from ajustes.models import ConfiguracionCorreo
    from lib.cartero import SLOTS_SMTP

    cfg = ConfiguracionCorreo.obtener()
    proveedor = (request.POST.get("proveedor") or "").strip()
    if proveedor in {"smtp", "n8n"}:
        cfg.proveedor = proveedor
    cfg.remitente_nombre = (request.POST.get("remitente_nombre") or "").strip() or "Learning Center"
    # V6 Bloque 7A: flags de correos automáticos (checkbox → bool).
    cfg.auto_bienvenida = bool(request.POST.get("auto_bienvenida"))
    cfg.auto_pago = bool(request.POST.get("auto_pago"))
    cfg.actualizado_por = request.user
    cfg.save()

    # Slots SMTP: solo guardamos los que vengan con valor (la contraseña en
    # blanco NO borra la guardada — hay que dejarla explícitamente vacía con
    # el checkbox de "borrar contraseña").
    for clave, _etq, _desc, tipo in SLOTS_SMTP:
        if tipo == "password":
            if request.POST.get("smtp_password_borrar"):
                Credencial.guardar(clave, "", usuario=request.user)
            else:
                nuevo = (request.POST.get(clave) or "").strip()
                if nuevo:
                    Credencial.guardar(clave, nuevo, usuario=request.user)
        else:
            Credencial.guardar(clave, (request.POST.get(clave) or "").strip(),
                               usuario=request.user)

    emitir(EventoPortavoz(
        tipo="ajuste.cartero_configurado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"proveedor": cfg.proveedor},
    ))
    messages.success(request, f"El Cartero quedó configurado (canal: {cfg.get_proveedor_display()}).")
    return redirect("ajustes-cartero")


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def cartero_probar(request):
    """Manda un correo de prueba al super_admin por el canal activo."""
    from lib import cartero
    destino = (request.POST.get("destinatario") or request.user.email or "").strip()
    res = cartero.probar(destino)
    if res.ok:
        messages.success(request, f"Prueba enviada por {res.proveedor} a {destino}. {res.detalle}")
    else:
        messages.error(request, f"No se pudo enviar la prueba: {res.error}")
    return redirect("ajustes-cartero")


# ── Plantillas de correo (editor gráfico + IA) ────────────────────────────


@requiere_permiso("ajustes", "acceder")
def cartero_plantillas(request):
    """Lista las plantillas editables de El Cartero."""
    from ajustes.models import PlantillaCorreo
    from ajustes.plantillas_correo_default import SLUGS_PLANTILLA
    plantillas = [PlantillaCorreo.obtener(slug) for slug in SLUGS_PLANTILLA]
    return render(request, "ajustes/cartero_plantillas.html", {"plantillas": plantillas})


@requiere_permiso("ajustes", "acceder")
def cartero_plantilla_editar(request, slug: str):
    """Editor gráfico (GrapesJS) de una plantilla. GET muestra; POST guarda."""
    from ajustes.models import PlantillaCorreo
    from ajustes.plantillas_correo_default import variables_de
    pl = PlantillaCorreo.obtener(slug)
    if request.method == "POST":
        pl.asunto = (request.POST.get("asunto") or "").strip()
        pl.cuerpo_html = request.POST.get("cuerpo_html") or ""
        pl.actualizado_por = request.user
        pl.save()
        messages.success(request, f"Plantilla «{pl.nombre}» guardada.")
        return redirect("ajustes-cartero-plantillas")
    return render(request, "ajustes/cartero_plantilla_editar.html", {
        "pl": pl,
        "variables": variables_de(slug),
    })


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def cartero_plantilla_redactar(request, slug: str):
    """El Chalán redacta/mejora el HTML de la plantilla. Devuelve JSON."""
    from django.http import JsonResponse

    from ajustes.plantillas_correo_default import variables_de
    from lib import cartero_ia
    intencion = request.POST.get("intencion") or ""
    html_actual = request.POST.get("html_actual") or ""
    res = cartero_ia.redactar(
        intencion=intencion, html_actual=html_actual,
        variables=variables_de(slug), usuario=request.user,
    )
    return JsonResponse(res)


# ── Google Drive — asistente guiado (OAuth sin clave) ─────────────────────────

_DRIVE_OAUTH_STATE = "drive_oauth_state"


def _drive_redirect_uri(request) -> str:
    """URI de callback que debe registrarse en el cliente OAuth de Google."""
    return f"{request.scheme}://{request.get_host()}/ajustes/google-drive/oauth/callback"


def _drive_contexto(request):
    from lib.google_drive import cliente_configurado, cliente_id_actual
    cliente_dedicado = Credencial.esta_configurado("google_drive_oauth_client_id")
    return {
        "oauth_listo": cliente_configurado(),
        "cliente_dedicado": cliente_dedicado,
        "usando_login": cliente_configurado() and not cliente_dedicado,
        "cliente_id": cliente_id_actual() or "",
        "conectado": Credencial.esta_configurado("google_drive_oauth_refresh_token"),
        "carpeta_lista": Credencial.esta_configurado("google_drive_carpeta_raiz_id"),
        "redirect_uri": _drive_redirect_uri(request),
        "ultimo_test": Credencial.objects.filter(
            clave="google_drive_oauth_refresh_token"
        ).values("ultimo_test_en", "ultimo_test_ok", "ultimo_test_mensaje").first(),
    }


@requiere_permiso("ajustes", "acceder")
def google_drive_guia(request):
    return render(request, "ajustes/google_drive.html", _drive_contexto(request))


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def google_drive_guardar_cliente(request):
    """Recibe el JSON del cliente OAuth, extrae id/secret y los cifra en La Bóveda.

    Usa slots DEDICADOS de Drive para no tocar el cliente del login con Google.
    Verifica que el redirect URI del callback ya esté en el JSON y avisa si no.
    """
    from lib.google_drive import parsear_cliente_json

    texto = (request.POST.get("cliente_json") or "").strip()
    if not texto:
        messages.error(request, "Pega el contenido del archivo JSON del cliente OAuth.")
        return redirect("ajustes-google-drive")

    try:
        datos = parsear_cliente_json(texto)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("ajustes-google-drive")

    Credencial.guardar("google_drive_oauth_client_id", datos["client_id"], usuario=request.user)
    Credencial.guardar("google_drive_oauth_client_secret", datos["client_secret"], usuario=request.user)

    emitir(EventoPortavoz(
        tipo="ajuste.credencial_guardada",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"clave": "google_drive_oauth_client"},
    ))

    callback = _drive_redirect_uri(request)
    if callback in datos.get("redirect_uris", []):
        messages.success(request, "Cliente OAuth guardado. La dirección de regreso ya está registrada ✓. Ahora conecta tu cuenta.")
    else:
        messages.warning(
            request,
            f"Cliente OAuth guardado, pero tu archivo no incluye la dirección de "
            f"regreso «{callback}». Agrégala en Google Cloud (paso 2) antes de conectar.",
        )
    return redirect("ajustes-google-drive")


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def google_drive_conectar(request):
    """Arranca el consentimiento OAuth: redirige al admin a Google."""
    import secrets

    from lib.google_drive import cliente_configurado, construir_url_consentimiento

    if not cliente_configurado():
        messages.error(request, "Primero pega el archivo de cliente OAuth (paso 2).")
        return redirect("ajustes-google-drive")

    state = secrets.token_urlsafe(24)
    request.session[_DRIVE_OAUTH_STATE] = state
    try:
        url = construir_url_consentimiento(_drive_redirect_uri(request), state)
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"No se pudo iniciar la conexión: {exc}")
        return redirect("ajustes-google-drive")
    return redirect(url)


@requiere_permiso("ajustes", "acceder")
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


@requiere_permiso("ajustes", "acceder")
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


@requiere_permiso("ajustes", "acceder")
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

@requiere_permiso("ajustes", "acceder")
def tasas_lista(request):
    tasas = TasaImpositiva.objects.all()
    return render(request, "ajustes/tasas.html", {"tasas": tasas})


@requiere_permiso("ajustes", "acceder")
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


@requiere_permiso("ajustes", "acceder")
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


@requiere_permiso("ajustes", "acceder")
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


@requiere_permiso("ajustes", "acceder")
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


@requiere_permiso("ajustes", "acceder")
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


@requiere_permiso("ajustes", "acceder")
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


@requiere_permiso("ajustes", "acceder")
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


@requiere_permiso("ajustes", "acceder")
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


# ── Configuración Fiscal (figuras fiscales editables) ────────────────────

@requiere_permiso("ajustes", "acceder")
@require_http_methods(["GET", "POST"])
def fiscal_panel(request):
    """Régimen + tasas de ISR/PTU/IVA editables. Las consume Contaduría
    (estimación) y Proyectos (IVA)."""
    from decimal import Decimal, InvalidOperation

    from ajustes.models import ConfiguracionFiscal
    from ajustes.models.fiscal import ISR_BASE_CHOICES, REGIMEN_CHOICES

    cfg = ConfiguracionFiscal.obtener()
    if request.method == "POST":
        regimen = (request.POST.get("regimen") or "").strip()
        if regimen in dict(REGIMEN_CHOICES):
            cfg.regimen = regimen
        isr_base = (request.POST.get("isr_base") or "").strip()
        if isr_base in dict(ISR_BASE_CHOICES):
            cfg.isr_base = isr_base
        cfg.ptu_aplica = bool(request.POST.get("ptu_aplica"))

        def _tasa(nombre, actual):
            try:
                v = Decimal(str(request.POST.get(nombre) or actual))
            except (InvalidOperation, ValueError):
                return actual
            return max(Decimal("0"), min(v, Decimal("100")))

        cfg.isr_tasa = _tasa("isr_tasa", cfg.isr_tasa)
        cfg.ptu_tasa = _tasa("ptu_tasa", cfg.ptu_tasa)
        cfg.iva_tasa = _tasa("iva_tasa", cfg.iva_tasa)
        cfg.ret_isr_honorarios = _tasa("ret_isr_honorarios", cfg.ret_isr_honorarios)

        def _entero(nombre, actual):
            try:
                v = int(request.POST.get(nombre) or actual)
            except (TypeError, ValueError):
                return actual
            return max(1, min(v, 100))

        cfg.ret_iva_honorarios_num = _entero("ret_iva_honorarios_num", cfg.ret_iva_honorarios_num)
        cfg.ret_iva_honorarios_den = _entero("ret_iva_honorarios_den", cfg.ret_iva_honorarios_den)
        cfg.actualizado_por = request.user
        cfg.save()
        emitir(EventoPortavoz(
            tipo="ajuste.fiscal_configurada",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"regimen": cfg.regimen, "isr_base": cfg.isr_base,
                     "isr_tasa": float(cfg.isr_tasa), "iva_tasa": float(cfg.iva_tasa)},
        ))
        messages.success(request, "Configuración fiscal guardada.")
        return redirect("ajustes-fiscal")

    return render(request, "ajustes/fiscal.html", {
        "cfg": cfg,
        "regimenes": REGIMEN_CHOICES,
        "isr_bases": ISR_BASE_CHOICES,
    })


# ── La Cobranza — recordatorios automáticos de pago (S3 resto) ───────────

@requiere_permiso("ajustes", "acceder")
@require_http_methods(["GET", "POST"])
def cobranza_panel(request):
    """Política de recordatorios de cobranza al cliente. Arranca apagada."""
    from ajustes.models import ConfiguracionCobranza

    cfg = ConfiguracionCobranza.obtener()
    if request.method == "POST":
        cfg.activa = bool(request.POST.get("activa"))
        cfg.incluir_pdf = bool(request.POST.get("incluir_pdf"))

        def _entero(nombre, default, maximo=365):
            try:
                v = int(request.POST.get(nombre) or default)
            except (TypeError, ValueError):
                v = default
            return max(0, min(v, maximo))

        cfg.dias_entre_recordatorios = _entero("dias_entre_recordatorios", 7)
        cfg.max_recordatorios = _entero("max_recordatorios", 4, maximo=50)
        cfg.recordar_pre_vencimiento_dias = _entero("recordar_pre_vencimiento_dias", 0)
        cfg.actualizado_por = request.user
        cfg.save()
        emitir(EventoPortavoz(
            tipo="ajuste.cobranza_configurada",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={"activa": cfg.activa, "dias_entre": cfg.dias_entre_recordatorios},
        ))
        messages.success(
            request,
            "La Cobranza quedó " + ("ACTIVADA." if cfg.activa else "desactivada."),
        )
        return redirect("ajustes-cobranza")

    from lib import cartero
    return render(request, "ajustes/cobranza.html", {
        "cfg": cfg,
        "correo_configurado": cartero.esta_configurado(),
        "canal_correo": cartero.proveedor_activo(),
    })
