"""El Directorio — CRUD de usuarios internos. Solo super_admin y dueño."""

import contextlib

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from cuentas.models.permiso_usuario import PermisoUsuario
from cuentas.models.usuario import Usuario
from lib.permisos import requiere_permiso, usuarios_con_rol
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import UsuarioForm


@requiere_permiso("directorio", "ver")
def lista(request):
    from django.db.models import Count

    from lib.graficas import donut_desde_conteo

    qs = Usuario.objects.all().prefetch_related("roles_extra").order_by("nombre_completo")
    activos = Usuario.objects.filter(is_active=True).count()
    total = Usuario.objects.count()
    por_rol = dict(
        Usuario.objects.filter(is_active=True)
        .values_list("rol").annotate(c=Count("id")).values_list("rol", "c")
    )
    etiquetas = {
        "super_admin": "Super admin", "dueno": "Admin",
        "contador": "Contador", "disenador": "Diseñador",
    }
    kpis = {
        "activos": activos,
        "inactivos": total - activos,
        # V6 Bloque 10: cuenta admins por rol primario O rol personalizado
        # (usuarios_con_rol ya filtra is_active=True).
        "admins": usuarios_con_rol("super_admin", "dueno").count(),
        "total": total,
    }
    # S-Directorio-Panel-V1: enriquece cada usuario con su Proveedor IA efectivo,
    # gasto IA 30d y semáforo de presupuesto, para la fila compacta.
    from decimal import Decimal

    from chalanes.services import proveedor_efectivo, proveedores_configurados
    from cuentas.models.presupuesto_ia import PresupuestoIA
    from lib.analistas.registry import apodo as _apodo
    from lib.analistas.stats import gasto_mes_por_usuario, gasto_por_usuario_dias

    usuarios = list(qs)
    g30 = gasto_por_usuario_dias(30)
    gmes = gasto_mes_por_usuario()
    presup = {p.usuario_id: p for p in PresupuestoIA.objects.filter(activo=True)}
    for u in usuarios:
        # V9: roles personalizados (roles_extra) para mostrarlos junto al primario.
        u.roles_extra_nombres = sorted(r.nombre for r in u.roles_extra.all())
        ef = proveedor_efectivo(u)
        u.ia_efectivo = ef
        u.ia_efectivo_apodo = {"auto": "Auto", "mixto": "Mixto"}.get(ef) or _apodo(ef)
        u.gasto_30d = g30.get(u.pk, Decimal("0"))
        p = presup.get(u.pk)
        u.ia_rebasado = bool(p and p.tope_usd > 0 and gmes.get(u.pk, Decimal("0")) >= p.tope_usd)
    chips_ia = [{"nombre": n, "apodo": _apodo(n)} for n in proveedores_configurados()]

    return render(request, "directorio/lista.html", {
        "usuarios": usuarios,
        "chips_ia": chips_ia,
        "kpis": kpis,
        "donut_roles_json": donut_desde_conteo(por_rol, etiquetas=etiquetas),
        "cabeceras_directorio": [
            {"label": "Nombre"},
            {"label": "Email"},
            {"label": "Rol"},
            # Sprint de pendientes 2026-09-28: quién está en línea y dónde anda.
            # La celda sale vacía si quien mira no tiene (equipo, ver_actividad).
            {"label": "Última actividad"},
            {"label": "Proveedor IA"},
            {"label": "Gasto IA 30d", "align": "right"},
            {"label": "Estado"},
            {"label": "", "align": "right"},
        ],
    })


@requiere_permiso("directorio", "gestionar")
@require_http_methods(["GET", "POST"])
def crear(request):
    if request.method == "POST":
        form = UsuarioForm(request.POST)
        if form.is_valid():
            u = form.save()
            emitir(EventoPortavoz(
                tipo="usuario.creado",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={"usuario_id": u.pk, "email": u.email, "rol": u.rol},
            ))
            messages.success(request, f"Usuario {u.email} creado.")
            return redirect("directorio-lista")
    else:
        form = UsuarioForm()
    return render(request, "directorio/form.html", {"form": form, "modo": "crear"})


@requiere_permiso("directorio", "gestionar")
@require_http_methods(["GET", "POST"])
def editar(request, pk: int):
    u = get_object_or_404(Usuario, pk=pk)
    if request.method == "POST":
        form = UsuarioForm(request.POST, instance=u)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario actualizado.")
            return redirect("directorio-lista")
    else:
        form = UsuarioForm(instance=u)
    return render(request, "directorio/form.html", {"form": form, "modo": "editar", "usuario": u})


@requiere_permiso("directorio", "gestionar")
@require_http_methods(["POST"])
def bloquear(request, pk: int):
    u = get_object_or_404(Usuario, pk=pk)
    if u.pk == request.user.pk:
        messages.error(request, "No puedes bloquearte a ti mismo.")
        return redirect("directorio-lista")
    u.is_active = not u.is_active
    u.save(update_fields=["is_active"])
    if not u.is_active:
        emitir(EventoPortavoz(
            tipo="usuario.bloqueado",
            actor_id=request.user.pk,
            actor_email=request.user.email,
            payload={"usuario_id": u.pk, "email": u.email},
        ))
    messages.success(request, f"Usuario {'activado' if u.is_active else 'bloqueado'}.")
    return redirect("directorio-lista")


# ── Permisos granulares (Pre-S2b.1) ─────────────────────────────────────────


@requiere_permiso("directorio", "permisos")
@require_http_methods(["GET", "POST"])
def permisos(request, pk: int):
    """Página completa de la grilla por persona (la misma del tab Permisos del
    panel, sin los roles). Comparte `_secciones_permisos` y `_guardar_grilla`
    con el panel: guardar tal cual no cambia ningún permiso efectivo."""
    u = get_object_or_404(Usuario, pk=pk)

    if request.method == "POST":
        if "restablecer" in request.POST:
            _restablecer_grilla(u, request.user)
        else:
            _guardar_grilla(u, set(request.POST.getlist("permisos")), None, request.user)
        with contextlib.suppress(Exception):
            emitir(EventoPortavoz(
                tipo="permisos.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"usuario_id": u.pk, "email": u.email},
            ))
        messages.success(request, f"Permisos de {u.email} actualizados.")
        return redirect("directorio-permisos", pk=u.pk)

    return render(request, "directorio/permisos.html", {
        "usuario": u, "secciones": _secciones_permisos(u),
    })


# ── S-LC-Feedback-V5 c7: CRUD de Roles personalizados ─────────────


@requiere_permiso("directorio", "roles")
def roles_lista(request):
    from cuentas.models.rol import Rol
    roles = Rol.objects.all().order_by("nombre")
    return render(request, "directorio/roles_lista.html", {"roles": roles})


def _clave_unica(nombre: str) -> str:
    """Genera una clave estable y única para un rol nuevo a partir del nombre."""
    from django.utils.text import slugify

    from cuentas.models.rol import Rol
    base = slugify(nombre) or "rol"
    clave = base
    i = 2
    while Rol.objects.filter(clave=clave).exists():
        clave = f"{base}-{i}"
        i += 1
    return clave


@requiere_permiso("directorio", "roles")
@require_http_methods(["GET", "POST"])
def rol_nuevo(request):
    from cuentas.models.rol import Rol
    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        descripcion = (request.POST.get("descripcion") or "").strip()
        permisos = _permisos_desde_checkboxes(request)
        if not nombre:
            messages.error(request, "El nombre del rol es obligatorio.")
            return render(request, "directorio/rol_form.html", {"modo": "nuevo", "nombre": nombre, "descripcion": descripcion, "secciones": _secciones_rol(permisos)})
        if Rol.objects.filter(nombre=nombre).exists():
            messages.error(request, f"Ya existe un rol llamado «{nombre}».")
            return render(request, "directorio/rol_form.html", {"modo": "nuevo", "nombre": nombre, "descripcion": descripcion, "secciones": _secciones_rol(permisos)})
        # Todo rol nace con los universales (`equipo.ver_actividad`): la persona
        # de ese rol los trae igual por su fila, y sin ellos «ver como rol»
        # mostraría otra pantalla. Se quitan por persona, no por rol.
        from lib.permisos_defaults import con_universales
        rol = Rol.objects.create(clave=_clave_unica(nombre), nombre=nombre, descripcion=descripcion, permisos=con_universales(permisos), sistema=False)
        emitir(EventoPortavoz(
            tipo="rol.creado", actor_id=request.user.pk, actor_email=request.user.email,
            payload={"rol_id": rol.pk, "nombre": rol.nombre, "clave": rol.clave},
        ))
        messages.success(request, f"Rol «{rol.nombre}» creado.")
        return redirect("directorio-roles")
    from lib.permisos_defaults import con_universales
    return render(request, "directorio/rol_form.html", {"modo": "nuevo", "secciones": _secciones_rol(con_universales({}))})


@requiere_permiso("directorio", "roles")
@require_http_methods(["GET", "POST"])
def rol_editar(request, pk: int):
    from cuentas.models.rol import Rol
    rol = get_object_or_404(Rol, pk=pk)
    if request.method == "POST":
        # El `nombre` es libremente editable (la identidad la lleva `clave`, que
        # nunca cambia). Solo super_admin queda protegido contra cambios de
        # permisos para no neutralizar el failsafe.
        nombre = (request.POST.get("nombre") or "").strip()
        descripcion = (request.POST.get("descripcion") or "").strip()
        if not nombre:
            messages.error(request, "El nombre del rol es obligatorio.")
            return render(request, "directorio/rol_form.html", {"modo": "editar", "rol": rol, "nombre": rol.nombre, "descripcion": descripcion, "secciones": _secciones_rol(rol.permisos)})
        if Rol.objects.filter(nombre=nombre).exclude(pk=rol.pk).exists():
            messages.error(request, f"Ya existe un rol llamado «{nombre}».")
            return render(request, "directorio/rol_form.html", {"modo": "editar", "rol": rol, "nombre": nombre, "descripcion": descripcion, "secciones": _secciones_rol(rol.permisos)})
        rol.nombre = nombre
        rol.descripcion = descripcion
        if rol.clave != "super_admin":
            rol.permisos = _permisos_desde_checkboxes(request)
        rol.save()
        emitir(EventoPortavoz(
            tipo="rol.actualizado", actor_id=request.user.pk, actor_email=request.user.email,
            payload={"rol_id": rol.pk, "nombre": rol.nombre, "clave": rol.clave},
        ))
        messages.success(request, f"Rol «{rol.nombre}» actualizado.")
        return redirect("directorio-roles")
    return render(request, "directorio/rol_form.html", {
        "modo": "editar", "rol": rol,
        "nombre": rol.nombre,
        "descripcion": rol.descripcion,
        "secciones": _secciones_rol(rol.permisos),
    })


@requiere_permiso("directorio", "roles")
@require_http_methods(["POST"])
def rol_borrar(request, pk: int):
    from cuentas.models.rol import Rol
    rol = get_object_or_404(Rol, pk=pk)
    if rol.protegido:
        messages.error(request, f"El rol «{rol.nombre}» no se puede borrar.")
        return redirect("directorio-roles")
    nombre = rol.nombre
    rol.delete()
    emitir(EventoPortavoz(
        tipo="rol.borrado", actor_id=request.user.pk, actor_email=request.user.email,
        payload={"nombre": nombre},
    ))
    messages.success(request, f"Rol «{nombre}» borrado.")
    return redirect("directorio-roles")


# ── S-Directorio-Panel-V1: modal de detalle con tabs (Datos · IA · Permisos) ──


def _es_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _ctx_ia(usuario) -> dict:
    """Contexto del tab IA: estaciones con default global + override, Chalanes
    disponibles, panel de uso 7/30/90d y estado del presupuesto."""
    from chalanes.estaciones import ESTACIONES_DICT
    from chalanes.models import CuadroChalanes
    from chalanes.services import overrides_de, proveedor_efectivo
    from cuentas.models.presupuesto_ia import PresupuestoIA
    from cuentas.servicios_presupuesto import evaluar
    from lib.analistas import registry as reg
    from lib.analistas.capacidades import Capability
    from lib.analistas.stats import uso_por_usuario

    cuadro = {c.estacion: c for c in CuadroChalanes.objects.all()}
    overs = overrides_de(usuario)
    chalanes = [
        {"nombre": n, "apodo": reg.apodo(n),
         "vision": Capability.VISION in (getattr(f, "capacidades", set()) or set())}
        for n, f in reg._FACTORIES.items()
    ]
    filas = []
    for slug, meta in ESTACIONES_DICT.items():
        c = cuadro.get(slug)
        default_prov = c.proveedor if c else meta["proveedor_default"]
        ov = overs.get(slug)
        elegibles = [ch for ch in chalanes if (not meta["requiere_vision"] or ch["vision"])]
        filas.append({
            "slug": slug, "etiqueta": meta["etiqueta"],
            "requiere_vision": meta["requiere_vision"],
            "default_apodo": reg.apodo(default_prov),
            "elegibles": elegibles,
            "override_prov": ov[0] if ov else "",
            "override_modelo": ov[1] if ov else "",
        })
    return {
        "usuario": usuario,
        "filas_ia": filas,
        "chalanes_ia": chalanes,
        "ia_efectivo": proveedor_efectivo(usuario),
        "uso_ia": uso_por_usuario(usuario.pk),
        "presupuesto": evaluar(usuario),
        "politicas": PresupuestoIA.POLITICAS,
    }


def _estado_grilla(u):
    """Lo que la grilla necesita de la persona: sus filas propias (sólo las del
    catálogo), los pares que dan sus roles asignados y, por par, los nombres de
    los roles que lo dan (para decir «por su rol X»)."""
    from lib.permisos_defaults import catalogo_permisos
    universo = {(m, a) for m, acciones in catalogo_permisos().items() for a in acciones}
    filas = {
        (m, a): activo
        for m, a, activo in PermisoUsuario.objects.filter(usuario=u).values_list("modulo", "permiso", "activo")
        if (m, a) in universo
    }
    roles_por_par: dict[tuple[str, str], list[str]] = {}
    for nombre, permisos_del_rol in u.roles_extra.order_by("nombre").values_list("nombre", "permisos"):
        for m, acciones in (permisos_del_rol or {}).items():
            for a in acciones or ():
                roles_por_par.setdefault((m, a), []).append(nombre)
    return universo, filas, roles_por_par


# (efectivo, algún rol lo da) → de dónde viene la casilla.
_ORIGEN = {(True, True): "rol", (True, False): "mano", (False, True): "quitado", (False, False): ""}


def _secciones_permisos(u):
    """Grilla módulo×acción para el editor por persona. Muestra TODO el catálogo
    para poder conceder cualquier permiso a cualquiera —incluido un `miembro`—.

    Cada casilla sale marcada según el permiso EFECTIVO, el mismo que contesta
    `lib.permisos.puede()` (fila propia; si no hay, sus roles asignados), y dice
    de dónde viene: `rol` (se lo da un rol), `mano` (encendido sólo para esta
    persona) o `quitado` (su rol lo da, pero se le apagó a esta persona)."""
    from lib.permisos import efectivo_por_filas
    from lib.permisos_defaults import catalogo_permisos
    _universo, filas, roles_por_par = _estado_grilla(u)
    por_rol = set(roles_por_par)
    secciones = []
    for modulo, permisos_lista in catalogo_permisos().items():
        casillas = []
        for p in permisos_lista:
            par = (modulo, p)
            roles = roles_por_par.get(par, [])
            activo = efectivo_por_filas(filas, por_rol, par)
            origen = _ORIGEN[(activo, bool(roles))]
            casillas.append({"permiso": p, "activo": activo, "origen": origen,
                             "roles": ", ".join(roles)})
        secciones.append((modulo, casillas))
    return secciones


def _aplicar_plan(u, escribir, borrar, actor):
    from django.db.models import Q
    if borrar:
        cual = Q()
        for m, a in borrar:
            cual |= Q(modulo=m, permiso=a)
        PermisoUsuario.objects.filter(cual, usuario=u).delete()
    for (m, a), activo in escribir.items():
        PermisoUsuario.objects.update_or_create(
            usuario=u, modulo=m, permiso=a,
            defaults={"activo": activo, "modificado_por": actor},
        )


def _guardar_grilla(u, marcadas, roles_nuevos, actor):
    """Guarda la grilla de una persona sin que nadie gane ni pierda por guardar.

    `marcadas` son los `modulo.accion` que llegaron marcados; `roles_nuevos`,
    los `Rol` que quedan asignados (None = no se tocan). Si el mismo POST
    cambia los roles, lo que no se tocó sigue a los roles NUEVOS. Sólo quedan
    filas donde la persona difiere de sus roles (`lib.permisos.plan_de_grilla`).
    """
    from django.db import transaction

    from lib.permisos import invalidar_cache_permisos, pares_de_roles, plan_de_grilla

    elegidos = set()
    for clave in marcadas:
        m, _, a = clave.partition(".")
        elegidos.add((m, a))
    with transaction.atomic():
        universo, filas, roles_por_par = _estado_grilla(u)
        roles_antes = set(roles_por_par)
        if roles_nuevos is not None:
            u.roles_extra.set(roles_nuevos)
            # S-Roles-V2: el rol primario se DERIVA de los roles asignados.
            from lib.permisos import sincronizar_rol_primario
            sincronizar_rol_primario(u)
        roles_despues = pares_de_roles(u.roles_extra.values_list("permisos", flat=True))
        escribir, borrar = plan_de_grilla(filas, roles_antes, roles_despues,
                                          elegidos & universo, universo)
        _aplicar_plan(u, escribir, borrar, actor)
    invalidar_cache_permisos()


def _restablecer_grilla(u, actor):
    """«Restablecer»: quita todo lo puesto a mano en la grilla. Queda lo que dan
    sus roles asignados, más los universales (`PERMISOS_UNIVERSALES`, que todo
    usuario trae desde que nace aunque ningún rol se los dé). Éste SÍ cambia
    permisos: es lo que el botón pide."""
    from django.db import transaction

    from lib.permisos import invalidar_cache_permisos
    from lib.permisos_defaults import PERMISOS_UNIVERSALES
    with transaction.atomic():
        universo, filas, roles_por_par = _estado_grilla(u)
        escribir = {
            (m, a): True
            for m, acciones in PERMISOS_UNIVERSALES.items() for a in acciones
            if (m, a) in universo and (m, a) not in roles_por_par
        }
        borrar = {par for par in filas if par not in escribir}
        _aplicar_plan(u, escribir, borrar, actor)
    invalidar_cache_permisos()


def _permisos_desde_checkboxes(request):
    """Arma el dict {modulo: [acciones]} desde los checkboxes `permisos`
    (valor `modulo.accion`), validando contra el catálogo canónico."""
    from lib.permisos_defaults import catalogo_permisos
    sel = set(request.POST.getlist("permisos"))
    out: dict[str, list[str]] = {}
    for modulo, acciones in catalogo_permisos().items():
        elegidas = [a for a in acciones if f"{modulo}.{a}" in sel]
        if elegidas:
            out[modulo] = elegidas
    return out


def _secciones_rol(permisos):
    """Grilla módulo×acción para el form de Rol, con las acciones del rol marcadas."""
    from lib.permisos_defaults import catalogo_permisos
    permisos = permisos or {}
    secciones = []
    for modulo, acciones in catalogo_permisos().items():
        marcadas = set(permisos.get(modulo) or [])
        filas = [(a, a in marcadas) for a in acciones]
        secciones.append((modulo, filas))
    return secciones


@requiere_permiso("directorio", "panel")
def panel(request, pk: int):
    """GET HTMX → modal de detalle con tabs. El tab Datos viene precargado."""
    from lib.permisos import roles_display
    u = get_object_or_404(Usuario, pk=pk)
    return render(request, "directorio/_modal_panel.html", {
        "usuario": u, "form": UsuarioForm(instance=u),
        # V9: roles legibles (primario + roles_extra) para mostrarlos en la ficha.
        "roles": roles_display(u),
    })


@requiere_permiso("directorio", "panel")
@require_http_methods(["GET", "POST"])
def panel_datos(request, pk: int):
    u = get_object_or_404(Usuario, pk=pk)
    if request.method == "POST":
        form = UsuarioForm(request.POST, instance=u)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario actualizado.")
            return HttpResponse(status=204, headers={"HX-Redirect": reverse("directorio-lista")})
    else:
        form = UsuarioForm(instance=u)
    return render(request, "directorio/_tab_datos.html", {"usuario": u, "form": form})


@requiere_permiso("directorio", "ia")
@require_http_methods(["GET", "POST"])
def panel_ia(request, pk: int):
    u = get_object_or_404(Usuario, pk=pk)
    from chalanes.estaciones import ESTACIONES_DICT
    from chalanes.services import set_override
    if request.method == "POST":
        for slug in ESTACIONES_DICT:
            prov = request.POST.get(f"prov_{slug}", "")
            modelo = request.POST.get(f"modelo_{slug}", "")
            set_override(u, slug, prov, modelo, request.user)
        messages.success(request, "Asignación de Chalanes actualizada.")
        return render(request, "directorio/_tab_ia.html", {**_ctx_ia(u), "guardado": True})
    return render(request, "directorio/_tab_ia.html", _ctx_ia(u))


@requiere_permiso("directorio", "ia")
@require_http_methods(["POST"])
def ia_forzar(request, pk: int):
    u = get_object_or_404(Usuario, pk=pk)
    from chalanes.services import forzar_proveedor, limpiar_overrides
    prov = (request.POST.get("proveedor") or "").strip()
    if prov in ("", "auto"):
        limpiar_overrides(u, request.user)
        messages.success(request, "Chalanes en automático (usa el Cuadro del equipo).")
    else:
        forzar_proveedor(u, prov, request.user)
        messages.success(request, "Proveedor IA forzado en todas las estaciones.")
    return render(request, "directorio/_tab_ia.html", {**_ctx_ia(u), "guardado": True})


@requiere_permiso("directorio", "ia")
@require_http_methods(["POST"])
def presupuesto(request, pk: int):
    from decimal import Decimal, InvalidOperation

    from cuentas.models.presupuesto_ia import PresupuestoIA
    u = get_object_or_404(Usuario, pk=pk)
    try:
        tope = Decimal((request.POST.get("tope_usd") or "0").replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        tope = Decimal("0")
    if tope < 0:
        tope = Decimal("0")
    politica = request.POST.get("politica") or PresupuestoIA.POLITICA_ALERTAR
    if politica not in dict(PresupuestoIA.POLITICAS):
        politica = PresupuestoIA.POLITICA_ALERTAR
    activo = bool(request.POST.get("activo"))
    PresupuestoIA.objects.update_or_create(
        usuario=u,
        defaults={"tope_usd": tope, "politica": politica, "activo": activo,
                  "actualizado_por": request.user},
    )
    emitir(EventoPortavoz(
        tipo="usuario.presupuesto_ia_actualizado",
        actor_id=request.user.pk, actor_email=request.user.email,
        payload={"usuario_id": u.pk, "tope_usd": float(tope), "politica": politica, "activo": activo},
    ))
    messages.success(request, "Presupuesto de IA actualizado.")
    return render(request, "directorio/_tab_ia.html", {**_ctx_ia(u), "guardado": True})


@requiere_permiso("directorio", "permisos")
@require_http_methods(["GET", "POST"])
def panel_permisos(request, pk: int):
    from cuentas.models.rol import Rol
    u = get_object_or_404(Usuario, pk=pk)
    if request.method == "POST":
        # Roles y casillas en un solo guardado: lo que no se tocó sigue a los
        # roles NUEVOS (asignar un rol y guardar en el mismo clic se lo da).
        _guardar_grilla(
            u, set(request.POST.getlist("permisos")),
            list(Rol.objects.filter(pk__in=request.POST.getlist("roles_extra"))),
            request.user,
        )
        with contextlib.suppress(Exception):
            emitir(EventoPortavoz(
                tipo="permisos.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"usuario_id": u.pk, "email": u.email},
            ))
        messages.success(request, f"Permisos de {u.email} actualizados.")
        return render(request, "directorio/_tab_permisos.html", {
            "usuario": u, "secciones": _secciones_permisos(u), "guardado": True,
            "roles_disponibles": Rol.objects.all().order_by("sistema", "nombre"),
            "roles_actuales_ids": set(u.roles_extra.values_list("pk", flat=True)),
        })
    return render(request, "directorio/_tab_permisos.html", {
        "usuario": u, "secciones": _secciones_permisos(u),
        "roles_disponibles": Rol.objects.all().order_by("sistema", "nombre"),
        "roles_actuales_ids": set(u.roles_extra.values_list("pk", flat=True)),
    })


@requiere_permiso("directorio", "permisos")
@require_http_methods(["GET", "POST"])
def asignar_roles_extra(request, pk: int):
    from cuentas.models.rol import Rol
    u = get_object_or_404(Usuario, pk=pk)
    if request.method == "POST":
        ids = request.POST.getlist("roles_extra")
        u.roles_extra.set(Rol.objects.filter(pk__in=ids))
        from lib.permisos import sincronizar_rol_primario
        sincronizar_rol_primario(u)
        emitir(EventoPortavoz(
            tipo="usuario.roles_extra_actualizados", actor_id=request.user.pk, actor_email=request.user.email,
            payload={"usuario_id": u.pk, "roles_ids": list(ids)},
        ))
        messages.success(request, f"Roles extra actualizados para {u.nombre_completo}.")
        return redirect("directorio-asignar-roles-extra", pk=u.pk)
    return render(request, "directorio/asignar_roles_extra.html", {
        "usuario": u,
        "roles_disponibles": Rol.objects.all().order_by("sistema", "nombre"),
        "roles_actuales_ids": set(u.roles_extra.values_list("pk", flat=True)),
    })
