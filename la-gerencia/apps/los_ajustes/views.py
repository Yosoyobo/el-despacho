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
    from ajustes.models.alias_remitente import disponibles_para
    from lib import cartero
    cfg = ConfiguracionCorreo.obtener()
    return render(request, "ajustes/cartero.html", {
        "cfg": cfg,
        # Sin usuario => sólo los departamentales verificados. Es lo correcto:
        # un alias personal en este slot saldría a nombre de quien no mandó el
        # correo, y `puede_usarlo` lo negaría de todos modos.
        "alias_despacho": disponibles_para(None),
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
    # El `<select>` se puede manipular, así que la dirección se valida aquí:
    # sólo un alias del despacho ya comprobado entra (vacío = remitente general).
    escogido = (request.POST.get("remitente_chalan") or "").strip().lower()
    if escogido:
        from ajustes.models.alias_remitente import disponibles_para
        validos = {a.email.strip().lower() for a in disponibles_para(None)}
        cfg.remitente_chalan = escogido if escogido in validos else ""
    else:
        cfg.remitente_chalan = ""
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
    messages.success(request, f"El correo quedó configurado (canal: {cfg.get_proveedor_display()}).")
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


def _slug_libre(base: str) -> str:
    """Slug único a partir del nombre. Desambigua con un sufijo numérico."""
    from django.utils.text import slugify

    from ajustes.models import PlantillaCorreo

    raiz = (slugify(base) or "plantilla")[:36]
    slug = raiz
    n = 2
    while PlantillaCorreo.objects.filter(slug=slug).exists():
        sufijo = f"-{n}"
        slug = raiz[: 40 - len(sufijo)] + sufijo
        n += 1
    return slug


@requiere_permiso("ajustes", "acceder")
def cartero_plantillas(request):
    """Lista las plantillas de El Cartero: las de sistema y las propias."""
    from ajustes.models import PlantillaCorreo
    from ajustes.plantillas_correo_default import SLUGS_PLANTILLA

    # `obtener` siembra la fila de sistema que falte (p.ej. tras agregar una
    # plantilla nueva al catálogo sin migración dedicada).
    for slug in SLUGS_PLANTILLA:
        PlantillaCorreo.obtener(slug)

    from ajustes.models.alias_remitente import faltan_por_dar_de_alta

    todas = list(PlantillaCorreo.objects.all())
    return render(request, "ajustes/cartero_plantillas.html", {
        "de_sistema": [p for p in todas if p.sistema],
        "propias": [p for p in todas if not p.sistema],
        "borradores": [p for p in todas if p.es_borrador],
        "alias_faltantes": faltan_por_dar_de_alta(),
    })


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def cartero_plantilla_nueva(request):
    """Crea una plantilla propia y abre su editor."""
    from ajustes.models import PlantillaCorreo

    nombre = (request.POST.get("nombre") or "").strip()
    if not nombre:
        messages.error(request, "Ponle un nombre a la plantilla.")
        return redirect("ajustes-cartero-plantillas")

    pl = PlantillaCorreo.objects.create(
        slug=_slug_libre(nombre), nombre=nombre[:120],
        descripcion=(request.POST.get("descripcion") or "").strip()[:200],
        asunto="", cuerpo_html="", activa=True,
        sistema=False, origen="manual", actualizado_por=request.user,
    )
    _emitir_plantilla("plantilla_correo.creada", pl, request.user)
    messages.success(request, f"Plantilla «{pl.nombre}» creada. Ahora dale cuerpo.")
    return redirect("ajustes-cartero-plantilla-editar", slug=pl.slug)


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def cartero_plantilla_borrar(request, slug: str):
    """Borra una plantilla propia. Las de sistema no se tocan."""
    from ajustes.models import PlantillaCorreo

    pl = get_object_or_404(PlantillaCorreo, slug=slug)
    if pl.sistema:
        messages.error(
            request,
            f"«{pl.nombre}» la manda el propio sistema; no se puede borrar. "
            "Si no la quieres, apágala.",
        )
        return redirect("ajustes-cartero-plantillas")
    # PROTECT en ReglaCorreo.plantilla: una plantilla con reglas no se va sin
    # avisar, o el evento se quedaría mudo sin que nadie lo note.
    if pl.reglas.exists():
        reglas = ", ".join(r.descripcion_humana() for r in pl.reglas.all()[:3])
        messages.error(
            request,
            f"«{pl.nombre}» la usa una regla automática ({reglas}). "
            "Quita la regla primero.",
        )
        return redirect("ajustes-cartero-plantillas")
    nombre = pl.nombre
    _emitir_plantilla("plantilla_correo.borrada", pl, request.user)
    pl.delete()
    messages.success(request, f"Plantilla «{nombre}» borrada.")
    return redirect("ajustes-cartero-plantillas")


@requiere_permiso("ajustes", "acceder")
def cartero_plantilla_editar(request, slug: str):
    """Editor gráfico (GrapesJS) de una plantilla. GET muestra; POST guarda."""
    from ajustes.models import PlantillaCorreo
    from ajustes.plantillas_correo_default import variables_de
    pl = PlantillaCorreo.obtener(slug)
    if request.method == "POST":
        pl.asunto = (request.POST.get("asunto") or "").strip()
        pl.cuerpo_html = request.POST.get("cuerpo_html") or ""
        pl.descripcion = (request.POST.get("descripcion") or "").strip()[:200]
        pl.remitente_email = (request.POST.get("remitente_email") or "").strip()
        pl.remitente_nombre = (request.POST.get("remitente_nombre") or "").strip()[:120]
        # Activar un borrador de El Chalán es justamente "ya lo revisé".
        pl.activa = bool(request.POST.get("activa"))
        if not pl.sistema and pl.activa and pl.origen == "chalan":
            pl.origen = "manual"
        pl.actualizado_por = request.user
        pl.save()
        _emitir_plantilla("plantilla_correo.actualizada", pl, request.user)
        messages.success(request, f"Plantilla «{pl.nombre}» guardada.")
        return redirect("ajustes-cartero-plantillas")
    return render(request, "ajustes/cartero_plantilla_editar.html", {
        "pl": pl,
        "variables": variables_de(slug),
        "alias_verificado": _alias_verificado(pl.remitente_email),
        "alias_conocidos": _alias_conocidos(),
    })


def _alias_verificado(email: str) -> bool:
    """¿Esta dirección ya se dio de alta en Google y se comprobó?"""
    from ajustes.models import AliasRemitente

    email = (email or "").strip().lower()
    if not email:
        return True  # sin alias no hay nada que dar de alta
    return AliasRemitente.objects.filter(email=email, verificado=True).exists()


def _alias_conocidos() -> list[str]:
    """Direcciones ya registradas, para sugerirlas y evitar dedazos."""
    from ajustes.models import AliasRemitente

    return list(AliasRemitente.objects.values_list("email", flat=True))


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def cartero_plantilla_probar(request, slug: str):
    """Manda esta plantilla de prueba, con SU remitente, a quien se indique.

    Es la única forma de comprobar un alias: Gmail no rechaza un remitente que
    no le pertenece, lo reescribe en silencio.
    """
    from ajustes.models import PlantillaCorreo
    from lib import cartero, correo_contexto

    pl = get_object_or_404(PlantillaCorreo, slug=slug)
    destino = (request.POST.get("destino") or request.user.email or "").strip()
    if not destino:
        messages.error(request, "Dime a qué correo mando la prueba.")
        return redirect("ajustes-cartero-plantilla-editar", slug=slug)

    contexto = correo_contexto.armar(
        representante=request.user,
        extra={
            "cliente": "Cliente de prueba", "empresa": "Empresa de prueba",
            "proyecto": "Proyecto de prueba", "estado": "en proceso",
            "folio": "LC-0000", "monto": "1,234.00",
            "asunto": "Prueba", "mensaje": "Este es un mensaje de prueba.",
        },
    )
    asunto, html = pl.render(contexto)
    remitente = pl.remitente_efectivo()
    res = cartero.enviar(destinatario=destino, asunto=f"[Prueba] {asunto}",
                         html=html, remitente=remitente)
    if res.ok:
        if remitente:
            messages.success(
                request,
                f"Prueba enviada a {destino}. Revisa de quién llegó: si NO dice "
                f"«{remitente}», el alias todavía no está dado de alta en «Enviar "
                "como» de la cuenta de correo y Google lo reemplazó.",
            )
        else:
            messages.success(request, f"Prueba enviada a {destino}.")
    else:
        messages.error(request, f"No se pudo enviar: {res.error}")
    return redirect("ajustes-cartero-plantilla-editar", slug=slug)


def _emitir_plantilla(tipo: str, pl, actor) -> None:
    import contextlib
    # La auditoría no bloquea la edición: si El Portavoz falla, la plantilla
    # igual se guardó.
    with contextlib.suppress(Exception):
        emitir(EventoPortavoz(
            tipo=tipo, actor_id=actor.pk, actor_email=actor.email,
            payload={"slug": pl.slug, "nombre": pl.nombre},
        ))


# ── Reglas: qué evento dispara qué plantilla ──────────────────────────────


@requiere_permiso("ajustes", "acceder")
def cartero_reglas(request):
    """Lista las reglas evento → plantilla."""
    from ajustes.models import PlantillaCorreo, ReglaCorreo
    from ajustes.models.regla_correo import EVENTOS_CORREO, META_EVENTOS

    reglas = list(ReglaCorreo.objects.select_related("plantilla"))
    return render(request, "ajustes/cartero_reglas.html", {
        "reglas": reglas,
        "eventos": [
            {"valor": v, "etiqueta": e, "meta": META_EVENTOS.get(v, {})}
            for v, e in EVENTOS_CORREO
        ],
        "plantillas": PlantillaCorreo.objects.filter(activa=True),
        "estados_proyecto": _estados_de_proyecto(),
    })


def _estados_de_proyecto():
    """Estados configurables, para el selector de la regla de proyecto."""
    try:
        from apps.los_proyectos.models.estado import EstadoProyecto
        return list(EstadoProyecto.objects.filter(activo=True).order_by("orden"))
    except Exception:  # noqa: BLE001 — Gerencia sin la app cargada
        return []


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def cartero_regla_guardar(request):
    """Crea o actualiza una regla. `pk` vacío = nueva."""
    from ajustes.models import PlantillaCorreo, ReglaCorreo
    from ajustes.models.regla_correo import META_EVENTOS

    pk = (request.POST.get("pk") or "").strip()
    evento = (request.POST.get("evento") or "").strip()
    if evento not in META_EVENTOS:
        messages.error(request, "Ese evento no existe.")
        return redirect("ajustes-cartero-reglas")

    # pk no numérico → get_object_or_404 lanza ValueError (500), no 404.
    try:
        plantilla_pk = int(request.POST.get("plantilla") or 0)
    except ValueError:
        plantilla_pk = 0
    plantilla = get_object_or_404(PlantillaCorreo, pk=plantilla_pk)
    estado_slug = (request.POST.get("estado_slug") or "").strip()
    try:
        dias = max(1, int(request.POST.get("dias") or 90))
    except ValueError:
        dias = 90

    datos = {
        "plantilla": plantilla, "estado_slug": estado_slug, "dias": dias,
        "activa": bool(request.POST.get("activa")),
    }
    if pk:
        regla = get_object_or_404(ReglaCorreo, pk=pk)
        for campo, valor in datos.items():
            setattr(regla, campo, valor)
        regla.evento = evento
        regla.save()
        messages.success(request, "Regla actualizada.")
    else:
        # El unique (evento, estado_slug) evita duplicar el mismo aviso.
        if ReglaCorreo.objects.filter(evento=evento, estado_slug=estado_slug).exists():
            messages.error(
                request,
                "Ya hay una regla para ese evento. Edítala en lugar de crear otra.",
            )
            return redirect("ajustes-cartero-reglas")
        ReglaCorreo.objects.create(evento=evento, creado_por=request.user, **datos)
        messages.success(
            request,
            "Regla creada. Recuerda encenderla cuando la plantilla esté lista.",
        )
    return redirect("ajustes-cartero-reglas")


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def cartero_regla_borrar(request, pk: int):
    from ajustes.models import ReglaCorreo

    regla = get_object_or_404(ReglaCorreo, pk=pk)
    regla.delete()
    messages.success(request, "Regla eliminada.")
    return redirect("ajustes-cartero-reglas")


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


# ── Direcciones de envío (qué alias hay que dar de alta en Google) ─────────


@requiere_permiso("ajustes", "acceder")
def cartero_remitentes(request):
    """Qué direcciones usan las plantillas y cuáles falta dar de alta.

    La lista NO se captura: se deriva de lo que declaran las plantillas. Lo
    único que se guarda es lo que la app no puede averiguar sola — si alguien
    ya creó el alias en Google y comprobó que llega bien.
    """
    from ajustes.models.alias_remitente import remitentes_en_uso
    from cuentas.models.usuario import Usuario
    from lib import cartero

    filas = remitentes_en_uso()
    return render(request, "ajustes/cartero_remitentes.html", {
        "filas": filas,
        "faltan": [f for f in filas if f["en_uso"] and not f["verificado"]],
        "personales_sin_dueno": [
            f for f in filas if f["es_personal"] and f["usuario"] is None
        ],
        "usuarios": Usuario.objects.filter(is_active=True).order_by("nombre_completo"),
        "cuenta_envia": cartero._cred("smtp_user") or cartero._cred("smtp_from_email"),
    })


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def cartero_remitente_dueno(request):
    """Liga (o suelta) una dirección a una persona.

    Con dueño, el alias es PERSONAL: sólo esa persona puede mandar desde él.
    Sin dueño, vuelve a ser del despacho y lo usa cualquiera con permiso.
    """
    from ajustes.models import AliasRemitente
    from cuentas.models.usuario import Usuario

    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        messages.error(request, "Falta la dirección.")
        return redirect("ajustes-cartero-remitentes")

    alias, _ = AliasRemitente.objects.get_or_create(email=email)
    crudo = (request.POST.get("usuario") or "").strip()
    if not crudo:
        alias.usuario = None
        alias.save(update_fields=["usuario"])
        messages.success(request, f"{email} queda como dirección del despacho.")
        return redirect("ajustes-cartero-remitentes")

    try:
        alias.usuario = Usuario.objects.get(pk=int(crudo))
    except (ValueError, Usuario.DoesNotExist):
        messages.error(request, "Esa persona no existe.")
        return redirect("ajustes-cartero-remitentes")
    alias.save(update_fields=["usuario"])
    messages.success(
        request,
        f"{email} queda a nombre de {alias.usuario.nombre_completo}. "
        "Nadie más podrá enviar desde esa dirección.",
    )
    return redirect("ajustes-cartero-remitentes")


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def cartero_remitente_marcar(request):
    """Marca (o desmarca) una dirección como ya dada de alta y comprobada."""
    from ajustes.models import AliasRemitente

    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        messages.error(request, "Falta la dirección.")
        return redirect("ajustes-cartero-remitentes")

    alias, _ = AliasRemitente.objects.get_or_create(email=email)
    if request.POST.get("desmarcar"):
        alias.desmarcar()
        messages.success(request, f"{email} vuelve a la lista de pendientes.")
    else:
        alias.marcar_verificado(request.user)
        messages.success(request, f"{email} queda marcada como lista.")
    return redirect("ajustes-cartero-remitentes")


@requiere_permiso("ajustes", "acceder")
@require_http_methods(["POST"])
def cartero_remitente_probar(request):
    """Manda una prueba DESDE esa dirección, para ver si Google la respeta."""
    from lib import cartero

    email = (request.POST.get("email") or "").strip()
    destino = (request.POST.get("destino") or request.user.email or "").strip()
    if not email or not destino:
        messages.error(request, "Falta la dirección o el destinatario.")
        return redirect("ajustes-cartero-remitentes")

    res = cartero.probar(destino, remitente=email)
    if res.ok:
        messages.success(
            request,
            f"Prueba enviada a {destino}. Abre ese correo y mira de quién llegó: "
            f"si dice {email}, el alias ya quedó y puedes marcarlo como listo. "
            "Si dice otra dirección, Google lo reemplazó y falta darlo de alta.",
        )
    else:
        messages.error(request, f"No se pudo enviar: {res.error}")
    return redirect("ajustes-cartero-remitentes")

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
    messages.success(request, f"Metas de KPI guardadas ({cambios}).")
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
        # Sprint Fiscal 2026-07: retención de IVA como tasa nominal (Anexo 20),
        # ya no la fracción num/den (deprecada).
        cfg.ret_iva_honorarios = _tasa("ret_iva_honorarios", cfg.ret_iva_honorarios)
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



# ── Rutas — los supuestos con los que el planeador estima la vuelta ───────

@requiere_permiso("ajustes", "acceder")
@require_http_methods(["GET", "POST"])
def rutas_panel(request):
    """Velocidad, tiempo por parada, hora de salida y tope de paradas.

    De estos cuatro números salen las **horas estimadas** que ve el runner en su
    ruta. Si no se parecen a la realidad, la ruta le promete horas que no va a
    cumplir y deja de creerle — por eso los ajusta quien conoce la ciudad y el
    trabajo, no quien escribe el código (Oscar, 2026-08-23).
    """
    from datetime import time as _time
    from decimal import Decimal, InvalidOperation

    from ajustes.models import ConfiguracionRutas

    cfg = ConfiguracionRutas.obtener()

    if request.method == "POST":
        def _entero(nombre, actual, minimo, tope):
            try:
                return max(minimo, min(int(request.POST.get(nombre) or actual), tope))
            except (TypeError, ValueError):
                return actual

        try:
            velocidad = Decimal(str(request.POST.get("velocidad_kmh") or cfg.velocidad_kmh))
        except (InvalidOperation, ValueError, TypeError):
            velocidad = cfg.velocidad_kmh
        # Cero dividiría entre cero al estimar tiempos.
        cfg.velocidad_kmh = max(Decimal("1"), min(velocidad, Decimal("200")))
        cfg.minutos_por_parada = _entero("minutos_por_parada", cfg.minutos_por_parada, 0, 240)
        cfg.max_paradas_por_ruta = _entero("max_paradas_por_ruta",
                                           cfg.max_paradas_por_ruta, 1, 25)

        crudo = (request.POST.get("hora_inicio") or "").strip()
        if crudo:
            try:
                h, m = crudo.split(":")[:2]
                cfg.hora_inicio = _time(int(h), int(m))
            except (TypeError, ValueError):
                pass  # hora ilegible: se queda la de antes

        cfg.save()
        # Que el cambio se note ya, sin esperar el minuto de caché del planeador.
        try:
            from apps.el_pizarron.planeador import olvidar_configuracion
            olvidar_configuracion()
        except Exception:  # noqa: BLE001 — Gerencia no depende del Taller para guardar
            pass
        emitir(EventoPortavoz(
            tipo="ajuste.rutas_configurada",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={
                "velocidad_kmh": str(cfg.velocidad_kmh),
                "minutos_por_parada": cfg.minutos_por_parada,
                "hora_inicio": cfg.hora_inicio.strftime("%H:%M"),
                "max_paradas": cfg.max_paradas_por_ruta,
            },
        ))
        messages.success(request, "Supuestos del planeador de rutas actualizados.")
        return redirect("ajustes-rutas")

    # Si el mapa está en pie, las distancias son de calle y no estimaciones a
    # vuelo de pájaro. La pantalla tiene que decir cuál de las dos cosas está
    # pasando: hasta 2026-08-24 afirmaba «se mide en línea recta» y desde que
    # entró OSRM eso dejó de ser cierto.
    try:
        from lib import ruteo
        mapa_vivo = ruteo.disponible(forzar=True)
    except Exception:  # noqa: BLE001 — no poder preguntar no rompe la pantalla
        mapa_vivo = False

    return render(request, "ajustes/rutas_panel.html", {
        "cfg": cfg,
        "mapa_vivo": mapa_vivo,
    })


# ── Documentos — cómo se arman los PDF que ve el cliente ─────────────────

@requiere_permiso("ajustes", "acceder")
@require_http_methods(["GET", "POST"])
def documentos_panel(request):
    """Márgenes, pie, tamaño de hoja y quién arma el PDF.

    Estos valores vivían como constantes en el código y sólo se podían mover
    con un despliegue (Oscar, 2026-08-24: «debemos poder editar todo lo posible
    de los PDFs en el GUI de la gerencia»).

    El selector de motor es además la salida de emergencia: si los documentos
    salen mal con Chromium, se vuelve a Google con un clic en vez de esperar a
    que pase un despliegue completo — que es justo lo que uno quiere tener a
    mano el día que un formato se rompe frente a un cliente.
    """
    from decimal import Decimal, InvalidOperation

    from ajustes.models import ConfiguracionDocumento
    from ajustes.models.documento import MOTORES, TAMANOS_CHOICES

    cfg = ConfiguracionDocumento.obtener()

    if request.method == "POST":
        def _entero(nombre, actual, minimo, tope):
            try:
                return max(minimo, min(int(request.POST.get(nombre) or actual), tope))
            except (TypeError, ValueError):
                return actual

        # Las opciones se validan contra las del modelo: el `select` del
        # navegador se puede manipular, así que no se confía en lo que llega.
        motor = (request.POST.get("motor") or "").strip()
        if motor in {clave for clave, _ in MOTORES}:
            cfg.motor = motor
        tamano = (request.POST.get("tamano_papel") or "").strip()
        if tamano in {clave for clave, _ in TAMANOS_CHOICES}:
            cfg.tamano_papel = tamano

        # Tope de 216pt (3 pulgadas): más que eso deja la hoja sin contenido.
        cfg.margen_superior_pt = _entero("margen_superior_pt", cfg.margen_superior_pt, 0, 216)
        cfg.margen_inferior_pt = _entero("margen_inferior_pt", cfg.margen_inferior_pt, 0, 216)
        cfg.margen_izquierdo_pt = _entero("margen_izquierdo_pt", cfg.margen_izquierdo_pt, 0, 216)
        cfg.margen_derecho_pt = _entero("margen_derecho_pt", cfg.margen_derecho_pt, 0, 216)

        cfg.pie_texto = (request.POST.get("pie_texto") or "").strip()[:120]
        cfg.numerar_paginas = bool(request.POST.get("numerar_paginas"))
        cfg.encabezado_texto = (request.POST.get("encabezado_texto") or "").strip()[:120]
        cfg.marca_borrador = (request.POST.get("marca_borrador") or "").strip()[:30]

        try:
            inter = Decimal(str(request.POST.get("interlineado") or cfg.interlineado))
        except (InvalidOperation, ValueError, TypeError):
            inter = cfg.interlineado
        # Menos de 0.8 encima los acentos; más de 2 desperdicia media hoja.
        cfg.interlineado = max(Decimal("0.8"), min(inter, Decimal("2.0")))

        cfg.actualizado_por = request.user
        cfg.save()

        # Que el cambio se vea en el siguiente PDF y no dentro de un minuto.
        try:
            from lib.documentos import olvidar_configuracion
            olvidar_configuracion()
        except Exception:  # noqa: BLE001 — guardar no depende de poder limpiar el caché
            pass

        emitir(EventoPortavoz(
            tipo="ajuste.documentos_configurado",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={
                "motor": cfg.motor,
                "tamano_papel": cfg.tamano_papel,
                "margen_superior_pt": cfg.margen_superior_pt,
                "numerar_paginas": cfg.numerar_paginas,
            },
        ))
        messages.success(request, "Formato de los documentos actualizado.")
        return redirect("ajustes-documentos")

    # Para que la pantalla pueda decir si el motor propio está en pie ahora
    # mismo, en vez de dejar al usuario adivinando por qué eligió uno y sale
    # el otro.
    try:
        from lib import gotenberg
        gotenberg_vivo = gotenberg.disponible(forzar=True)
    except Exception:  # noqa: BLE001
        gotenberg_vivo = False

    return render(request, "ajustes/documentos_panel.html", {
        "cfg": cfg,
        "motores": MOTORES,
        "tamanos": TAMANOS_CHOICES,
        "gotenberg_vivo": gotenberg_vivo,
        "alto_util_pt": cfg.alto_util_pt,
    })



# ── Servicios del NUC — las piezas que corren junto a El Despacho ────────

@requiere_permiso("ajustes", "acceder")
@require_http_methods(["GET"])
def servicios_panel(request):
    """Qué hay corriendo en el servidor, para qué sirve y si responde AHORA.

    Existe para que no haya piezas invisibles (Oscar, 2026-08-24: «todo lo que
    estamos integrando debe tener su GUI y sus ajustes en el sidebar»). Un
    servicio que corre pero no se ve es peor que uno que no está: nadie sabe si
    funciona ni por dónde empezar el día que falle.

    Cada uno se sondea de verdad; no se da por vivo porque el compose lo
    declare.
    """
    from lib.site import servicios

    lista = servicios.estado()
    return render(request, "ajustes/servicios_panel.html", {
        "servicios": lista,
        "resumen": servicios.resumen(lista),
    })


# ── CFDI que llegaron por correo y esperan dueño ─────────────────────────

@requiere_permiso("ajustes", "acceder")
@require_http_methods(["GET", "POST"])
def cfdi_panel(request):
    """Los comprobantes que entraron y no se pudieron ligar solos.

    El ligado automático es deliberadamente prudente: sólo cuando hay UNA
    factura que coincide. Cuando hay dos o ninguna, el comprobante llega aquí
    con el motivo escrito, porque adivinar dejaría la contabilidad apoyada en
    una suposición que nadie revisó.
    """
    from apps.facturacion.models import (
        ESTADO_IGNORADO,
        ESTADO_LIGADO,
        ESTADO_PENDIENTE,
        CfdiEntrante,
    )
    from django.utils import timezone

    if request.method == "POST":
        pk = request.POST.get("pk")
        accion = (request.POST.get("accion") or "").strip()
        obj = CfdiEntrante.objects.filter(pk=pk).first()
        if obj is None:
            messages.error(request, "Ese comprobante ya no está.")
            return redirect("ajustes-cfdi")

        if accion == "ignorar":
            obj.estado = ESTADO_IGNORADO
            obj.resuelto_en = timezone.now()
            obj.resuelto_por = request.user
            obj.save(update_fields=["estado", "resuelto_en", "resuelto_por"])
            messages.success(request, "Comprobante marcado como ignorado.")
        elif accion == "ligar":
            from apps.facturacion.models import Factura

            fac = Factura.objects.filter(pk=request.POST.get("factura")).first()
            if fac is None:
                messages.error(request, "No se encontró esa factura.")
                return redirect("ajustes-cfdi")
            obj.factura = fac
            obj.estado = ESTADO_LIGADO
            obj.resuelto_en = timezone.now()
            obj.resuelto_por = request.user
            obj.save()
            # El folio fiscal se copia a la factura por el camino de siempre.
            try:
                fac.cfdi_uuid = obj.uuid
                fac.save(update_fields=["cfdi_uuid"])
            except Exception:  # noqa: BLE001 — el registro ya quedó ligado
                pass
            messages.success(request, f"Comprobante ligado a {fac.codigo}.")
        return redirect("ajustes-cfdi")

    filtro = (request.GET.get("estado") or ESTADO_PENDIENTE).strip()
    qs = CfdiEntrante.objects.select_related("factura")
    if filtro != "todos":
        qs = qs.filter(estado=filtro)

    return render(request, "ajustes/cfdi_panel.html", {
        "cfdis": list(qs[:200]),
        "filtro": filtro,
        "pendientes": CfdiEntrante.objects.filter(estado=ESTADO_PENDIENTE).count(),
    })


# ── El Análisis — los umbrales con los que El Chalán juzga ───────────────

@requiere_permiso("ajustes", "acceder")
@require_http_methods(["GET", "POST"])
def analisis_panel(request):
    """Umbrales de El Análisis + costo por hora de cada rol.

    Aquí se decide qué considera el sistema un margen sano, cuántos días de
    silencio dan por perdida una cotización y cuánto cuesta una hora de cada
    rol. De estos números salen las alertas y la lectura del Chalán.
    """
    from decimal import Decimal, InvalidOperation

    from ajustes.models import ConfiguracionAnalisis, TarifaRol
    from cuentas.models.rol import Rol

    cfg = ConfiguracionAnalisis.obtener()

    if request.method == "POST":
        def _entero(nombre, actual, tope=3650):
            try:
                return max(0, min(int(request.POST.get(nombre) or actual), tope))
            except (TypeError, ValueError):
                return actual

        def _decimal(nombre, actual, tope=Decimal("1000")):
            try:
                valor = Decimal(str(request.POST.get(nombre) or actual))
            except (InvalidOperation, ValueError, TypeError):
                return actual
            return max(Decimal("0"), min(valor, tope))

        cfg.dias_silencio_cotizacion = _entero("dias_silencio_cotizacion",
                                               cfg.dias_silencio_cotizacion, 365)
        cfg.marcar_perdidas_solo = bool(request.POST.get("marcar_perdidas_solo"))
        cfg.margen_sano_pct = _decimal("margen_sano_pct", cfg.margen_sano_pct, Decimal("100"))
        cfg.margen_critico_pct = _decimal("margen_critico_pct", cfg.margen_critico_pct,
                                          Decimal("100"))
        cfg.dias_mora_alerta = _entero("dias_mora_alerta", cfg.dias_mora_alerta, 365)
        cfg.tarifa_hora_default = _decimal("tarifa_hora_default", cfg.tarifa_hora_default,
                                           Decimal("100000"))
        cfg.prorratear_jornada = bool(request.POST.get("prorratear_jornada"))
        cfg.horas_jornada_tope = _entero("horas_jornada_tope", cfg.horas_jornada_tope, 24)
        cfg.auto_activar_aprendizajes = bool(request.POST.get("auto_activar_aprendizajes"))
        cfg.confianza_minima_auto = _decimal("confianza_minima_auto",
                                             cfg.confianza_minima_auto, Decimal("1"))
        cfg.dias_ventana_aprendizaje = _entero("dias_ventana_aprendizaje",
                                               cfg.dias_ventana_aprendizaje, 365)
        cfg.analisis_diario_activo = bool(request.POST.get("analisis_diario_activo"))
        cfg.actualizado_por = request.user
        cfg.save()

        # Tarifas por rol: llegan como tarifa_<rol_id>.
        for rol in Rol.objects.all():
            crudo = request.POST.get(f"tarifa_{rol.pk}")
            if crudo is None:
                continue
            try:
                monto = Decimal(str(crudo or "0"))
            except (InvalidOperation, ValueError):
                continue
            monto = max(Decimal("0"), min(monto, Decimal("100000")))
            TarifaRol.objects.update_or_create(
                rol=rol,
                defaults={"costo_hora": monto, "activo": monto > 0,
                          "actualizado_por": request.user},
            )

        emitir(EventoPortavoz(
            tipo="ajuste.analisis_configurado",
            actor_id=request.user.pk, actor_email=request.user.email,
            payload={
                "margen_sano_pct": float(cfg.margen_sano_pct),
                "dias_silencio": cfg.dias_silencio_cotizacion,
                "auto_activar_aprendizajes": cfg.auto_activar_aprendizajes,
            },
        ))
        messages.success(request, "Guardado. El Análisis ya usa estos números.")
        return redirect("ajustes-analisis")

    tarifas = {t.rol_id: t for t in TarifaRol.objects.all()}
    roles = [
        {"rol": rol, "costo_hora": (tarifas.get(rol.pk).costo_hora if tarifas.get(rol.pk) else None)}
        for rol in Rol.objects.all().order_by("nombre")
    ]
    return render(request, "ajustes/analisis.html", {"cfg": cfg, "roles": roles})


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
            "La cobranza automática quedó "
            + ("ACTIVADA." if cfg.activa else "desactivada."),
        )
        return redirect("ajustes-cobranza")

    from lib import cartero
    return render(request, "ajustes/cobranza.html", {
        "cfg": cfg,
        "correo_configurado": cartero.esta_configurado(),
        "canal_correo": cartero.proveedor_activo(),
    })
