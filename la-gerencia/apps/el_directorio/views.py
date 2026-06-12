"""El Directorio — CRUD de usuarios internos. Solo super_admin y dueño."""

import contextlib

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from cuentas.models.permiso_usuario import PermisoUsuario
from cuentas.models.usuario import Usuario
from lib.permisos import requires_role, usuarios_con_rol
from lib.permisos_defaults import DEFAULTS_POR_ROL
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .forms import UsuarioForm


@requires_role("super_admin", "dueno")
def lista(request):
    from django.db.models import Count

    from lib.graficas import donut_desde_conteo

    qs = Usuario.objects.all().order_by("nombre_completo")
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
            {"label": "Proveedor IA"},
            {"label": "Gasto IA 30d", "align": "right"},
            {"label": "Estado"},
            {"label": "", "align": "right"},
        ],
    })


@requires_role("super_admin", "dueno")
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


@requires_role("super_admin", "dueno")
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


@requires_role("super_admin", "dueno")
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


@requires_role("super_admin")
@require_http_methods(["GET", "POST"])
def permisos(request, pk: int):
    """UI de gestión de PermisoUsuario para un usuario específico."""
    u = get_object_or_404(Usuario, pk=pk)
    defaults_rol = DEFAULTS_POR_ROL.get(u.rol, {})

    if request.method == "POST":
        if "restablecer" in request.POST:
            # Borra todo y vuelve a sembrar.
            PermisoUsuario.objects.filter(usuario=u).delete()
            for modulo, permisos_lista in defaults_rol.items():
                for permiso in permisos_lista:
                    PermisoUsuario.objects.create(
                        usuario=u, modulo=modulo, permiso=permiso, activo=True,
                        modificado_por=request.user,
                    )
        else:
            seleccionados = set(request.POST.getlist("permisos"))
            todos = []
            for modulo, permisos_lista in defaults_rol.items():
                for permiso in permisos_lista:
                    todos.append((modulo, permiso))
            for modulo, permiso in todos:
                clave = f"{modulo}.{permiso}"
                activo = clave in seleccionados
                PermisoUsuario.objects.update_or_create(
                    usuario=u, modulo=modulo, permiso=permiso,
                    defaults={"activo": activo, "modificado_por": request.user},
                )
        with contextlib.suppress(Exception):
            emitir(EventoPortavoz(
                tipo="permisos.actualizado",
                actor_id=request.user.pk, actor_email=request.user.email,
                payload={"usuario_id": u.pk, "email": u.email},
            ))
        messages.success(request, f"Permisos de {u.email} actualizados.")
        return redirect("directorio-permisos", pk=u.pk)

    # GET: construye estructura {modulo: [(permiso, activo), ...]}
    activos = {
        (p.modulo, p.permiso): p.activo
        for p in PermisoUsuario.objects.filter(usuario=u)
    }
    secciones = []
    for modulo, permisos_lista in defaults_rol.items():
        filas = [(p, activos.get((modulo, p), True)) for p in permisos_lista]
        secciones.append((modulo, filas))

    return render(request, "directorio/permisos.html", {
        "usuario": u, "secciones": secciones,
    })


# ── S-LC-Feedback-V5 c7: CRUD de Roles personalizados ─────────────


@requires_role("super_admin")
def roles_lista(request):
    from cuentas.models.rol import Rol
    roles = Rol.objects.all().order_by("sistema", "nombre")
    return render(request, "directorio/roles_lista.html", {"roles": roles})


@requires_role("super_admin")
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
        rol = Rol.objects.create(nombre=nombre, descripcion=descripcion, permisos=permisos, sistema=False)
        emitir(EventoPortavoz(
            tipo="rol.creado", actor_id=request.user.pk, actor_email=request.user.email,
            payload={"rol_id": rol.pk, "nombre": rol.nombre},
        ))
        messages.success(request, f"Rol «{rol.nombre}» creado.")
        return redirect("directorio-roles")
    return render(request, "directorio/rol_form.html", {"modo": "nuevo", "secciones": _secciones_rol({})})


@requires_role("super_admin")
@require_http_methods(["GET", "POST"])
def rol_editar(request, pk: int):
    from cuentas.models.rol import Rol
    rol = get_object_or_404(Rol, pk=pk)
    if request.method == "POST":
        if rol.sistema and rol.nombre == "super_admin":
            messages.error(request, "El rol super_admin del sistema no se puede editar.")
            return redirect("directorio-roles")
        descripcion = (request.POST.get("descripcion") or "").strip()
        permisos = _permisos_desde_checkboxes(request)
        rol.descripcion = descripcion
        rol.permisos = permisos
        rol.save()
        emitir(EventoPortavoz(
            tipo="rol.actualizado", actor_id=request.user.pk, actor_email=request.user.email,
            payload={"rol_id": rol.pk, "nombre": rol.nombre},
        ))
        messages.success(request, f"Rol «{rol.nombre}» actualizado.")
        return redirect("directorio-roles")
    return render(request, "directorio/rol_form.html", {
        "modo": "editar", "rol": rol,
        "nombre": rol.nombre,
        "descripcion": rol.descripcion,
        "secciones": _secciones_rol(rol.permisos),
    })


@requires_role("super_admin")
@require_http_methods(["POST"])
def rol_borrar(request, pk: int):
    from cuentas.models.rol import Rol
    rol = get_object_or_404(Rol, pk=pk)
    if rol.sistema:
        messages.error(request, f"El rol sistema «{rol.nombre}» no se puede borrar.")
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


def _secciones_permisos(u):
    """Grilla módulo×acción para el editor por-usuario. Muestra TODO el catálogo
    (no solo los defaults del rol primario) para poder conceder cualquier permiso
    a cualquier usuario — incluido `miembro`, que no tiene defaults. El estado
    "marcado por default" sigue lo que el rol primario otorga."""
    from lib.permisos_defaults import catalogo_permisos, defaults_de
    activos = {
        (p.modulo, p.permiso): p.activo
        for p in PermisoUsuario.objects.filter(usuario=u)
    }
    base = defaults_de(u.rol)
    secciones = []
    for modulo, permisos_lista in catalogo_permisos().items():
        defm = base.get(modulo, [])
        filas = [(p, activos.get((modulo, p), p in defm)) for p in permisos_lista]
        secciones.append((modulo, filas))
    return secciones


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


@requires_role("super_admin")
def panel(request, pk: int):
    """GET HTMX → modal de detalle con tabs. El tab Datos viene precargado."""
    u = get_object_or_404(Usuario, pk=pk)
    return render(request, "directorio/_modal_panel.html", {
        "usuario": u, "form": UsuarioForm(instance=u),
    })


@requires_role("super_admin")
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


@requires_role("super_admin")
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


@requires_role("super_admin")
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


@requires_role("super_admin")
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


@requires_role("super_admin")
@require_http_methods(["GET", "POST"])
def panel_permisos(request, pk: int):
    from cuentas.models.rol import Rol
    u = get_object_or_404(Usuario, pk=pk)
    if request.method == "POST":
        from lib.permisos_defaults import catalogo_permisos
        seleccionados = set(request.POST.getlist("permisos"))
        for modulo, permisos_lista in catalogo_permisos().items():
            for permiso in permisos_lista:
                PermisoUsuario.objects.update_or_create(
                    usuario=u, modulo=modulo, permiso=permiso,
                    defaults={"activo": f"{modulo}.{permiso}" in seleccionados,
                              "modificado_por": request.user},
                )
        u.roles_extra.set(Rol.objects.filter(pk__in=request.POST.getlist("roles_extra")))
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


@requires_role("super_admin")
@require_http_methods(["GET", "POST"])
def asignar_roles_extra(request, pk: int):
    from cuentas.models.rol import Rol
    u = get_object_or_404(Usuario, pk=pk)
    if request.method == "POST":
        ids = request.POST.getlist("roles_extra")
        u.roles_extra.set(Rol.objects.filter(pk__in=ids))
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
