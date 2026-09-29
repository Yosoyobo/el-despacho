"""La Gerencia → Ajustes → KPIs (S-KPIs-V2, 2026-09-29).

Decisiones de Oscar en la ronda de KPIs: catálogo administrable + constructor,
«Gerencia arma, cada quien ajusta», y metas proporcionales al periodo, con
dirección, por persona o cliente y con aviso si van en riesgo.

Cuatro pestañas, todas con `kpis.configurar`:

- **Catálogo** — todos los KPIs: prenderlo/apagarlo para todos, quién lo ve
  (el permiso del dato), si mejora subiendo o bajando, umbrales amarillo/rojo
  y su último valor anotado.
- **Tableros** — qué KPIs ve cada rol en «Tu tablero» del Inicio, en orden
  (botones ↑/↓, decisión Pre-S2b.1: sin arrastrar), y el tablero por omisión.
- **Metas** — del despacho, de una persona o de un cliente, con su estado de
  hoy y las que propone El Chalán a partir de la historia.
- **Constructor** — KPIs nuevos sin programar (`views_kpis_constructor.py`).

Los modelos viven en El Taller (`apps.taller_home`); La Gerencia los trae en
su imagen (`tests/gerencia/test_gerencia_trae_lo_que_importa.py`).
"""

from __future__ import annotations

import contextlib
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from lib.permisos import requiere_permiso
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

TABS = [
    {"clave": "catalogo", "etiqueta": "Catálogo", "url": "/ajustes/kpis/"},
    {"clave": "tableros", "etiqueta": "Tableros por rol", "url": "/ajustes/kpis/tableros/"},
    {"clave": "metas", "etiqueta": "Metas", "url": "/ajustes/kpis/metas/"},
]

_MODULOS = {
    "proyectos": "Proyectos", "pizarron": "Tareas", "buzon": "Buzón", "recados": "Recados",
    "checador": "Checador", "cartera": "Clientes", "tesoreria": "Tesorería",
    "cotizaciones": "Cotizaciones", "facturacion": "Facturación", "contaduria": "Contaduría",
    "catalogo": "Catálogo", "interfono": "Interfón", "site": "El Site", "chalanes": "Chalanes",
    "directorio": "Directorio", "gerencia": "La Gerencia", "rutas": "Rutas",
    "papeleo": "Papeleo", "comunicacion": "Comunicación", "nomina": "Nómina",
}


def _emitir(tipo: str, request, payload: dict):
    # Un evento perdido no tumba el guardado.
    with contextlib.suppress(Exception):
        emitir(EventoPortavoz(tipo=tipo, actor_id=request.user.pk,
                              actor_email=request.user.email, payload=payload))


def etiqueta_permisos(permisos: tuple[str, ...]) -> str:
    """`("tesoreria.ver",)` → «Tesorería · ver». Vacío: «Todos»."""
    if not permisos:
        return "Todos"
    partes = []
    for p in permisos:
        modulo, _, accion = p.partition(".")
        partes.append(f"{_MODULOS.get(modulo, modulo.title())} · {accion.replace('_', ' ')}")
    return " + ".join(partes)


def _decimal_o_none(texto: str | None):
    """Vacío = sin valor (no cero): regla «vacío hereda, 0 es cero»."""
    texto = (texto or "").strip().replace(",", "").replace("$", "").replace("%", "")
    if texto == "":
        return None
    try:
        return Decimal(texto)
    except InvalidOperation:
        raise ValueError(texto) from None


def _catalogo():
    from apps.taller_home.kpis import CATEGORIAS, KPIS

    etiquetas = dict(CATEGORIAS)
    return KPIS, etiquetas


def _ultimos_valores() -> dict:
    """`{slug: (fecha, valor)}` de la foto más reciente de cada KPI (7 días)."""
    from datetime import date, timedelta

    from apps.taller_home.models import SnapshotKPI

    salida: dict = {}
    for slug, fecha, valor in (
        SnapshotKPI.objects.filter(fecha__gte=date.today() - timedelta(days=7))
        .order_by("kpi_slug", "-fecha").values_list("kpi_slug", "fecha", "valor")
    ):
        salida.setdefault(slug, (fecha, valor))
    return salida


def _fila_catalogo(kpi, cfg, ultimo) -> dict:
    from apps.taller_home.kpi_meta import DIRECCIONES
    from apps.taller_home.kpi_valor import formatear

    direcciones = dict(DIRECCIONES)
    efectiva = (cfg.direccion if cfg and cfg.direccion else "") or kpi.direccion
    return {
        "kpi": kpi,
        "activo": cfg.activo if cfg else True,
        "direccion": cfg.direccion if cfg else "",
        "direccion_catalogo": direcciones.get(kpi.direccion, kpi.direccion),
        "direccion_efectiva": efectiva,
        "umbral_amarillo": "" if not cfg or cfg.umbral_amarillo is None
        else f"{cfg.umbral_amarillo.normalize():f}",
        "umbral_rojo": "" if not cfg or cfg.umbral_rojo is None
        else f"{cfg.umbral_rojo.normalize():f}",
        "permisos": etiqueta_permisos(kpi.permisos),
        "ultimo": formatear(float(ultimo[1]), kpi.formato) if ultimo else "",
        "ultimo_fecha": ultimo[0] if ultimo else None,
        "acumula": {"dia": "del día", "semana": "de la semana", "mes": "del mes",
                    "ano": "del año"}.get(kpi.acumula, "saldo al corte"),
        "personal": kpi.personal,
    }


# ── Catálogo ─────────────────────────────────────────────────────────────


@requiere_permiso("kpis", "configurar")
def catalogo(request):
    from apps.taller_home.kpi_meta import DIRECCIONES
    from apps.taller_home.tablero import configs

    kpis, etiquetas = _catalogo()
    cfgs = configs()
    ultimos = _ultimos_valores()
    grupos: dict[str, list] = {}
    for kpi in kpis:
        grupos.setdefault(kpi.categoria, []).append(
            _fila_catalogo(kpi, cfgs.get(kpi.slug), ultimos.get(kpi.slug))
        )
    orden = [c for c, _ in etiquetas.items()] + sorted(set(grupos) - set(etiquetas))
    apagados = sum(1 for c in cfgs.values() if not c.activo)
    return render(request, "ajustes/kpis/catalogo.html", {
        "tabs": TABS, "activo": "catalogo",
        "grupos": [{"clave": c, "etiqueta": etiquetas.get(c, c.title()), "filas": grupos[c]}
                   for c in orden if c in grupos],
        "direcciones": DIRECCIONES,
        "total": len(kpis), "apagados": apagados,
    })


@requiere_permiso("kpis", "configurar")
@require_http_methods(["POST"])
def catalogo_guardar(request, slug: str):
    """Guarda un renglón del catálogo. Con HTMX devuelve el renglón."""
    from apps.taller_home.kpi_meta import DIRECCIONES
    from apps.taller_home.kpis import kpi_por_slug
    from apps.taller_home.models import ConfigKPI

    kpi = kpi_por_slug(slug)
    if kpi is None:
        return HttpResponseBadRequest("KPI inexistente.")
    direccion = (request.POST.get("direccion") or "").strip()
    if direccion and direccion not in dict(DIRECCIONES):
        return HttpResponseBadRequest("Dirección inválida.")
    error = ""
    try:
        amarillo = _decimal_o_none(request.POST.get("umbral_amarillo"))
        rojo = _decimal_o_none(request.POST.get("umbral_rojo"))
    except ValueError as exc:
        amarillo = rojo = None
        error = f"«{exc}» no es un número."
    if not error:
        cfg, _ = ConfigKPI.objects.get_or_create(kpi_slug=slug)
        cfg.activo = request.POST.get("activo") == "1"
        # Si coincide con la del catálogo, no se guarda: si el código cambia, se sigue.
        cfg.direccion = "" if direccion == kpi.direccion else direccion
        cfg.umbral_amarillo = amarillo
        cfg.umbral_rojo = rojo
        cfg.actualizado_por = request.user
        cfg.save()
        _emitir("kpi.configuracion_actualizada", request,
                {"que": "catalogo", "kpi_slug": slug, "activo": cfg.activo})
    else:
        cfg = ConfigKPI.objects.filter(kpi_slug=slug).first()

    if request.headers.get("HX-Request"):
        ultimo = _ultimos_valores().get(slug)
        return render(request, "ajustes/kpis/_fila_catalogo.html", {
            "f": _fila_catalogo(kpi, cfg, ultimo), "direcciones": DIRECCIONES,
            "guardado": not error, "error": error,
        })
    if error:
        messages.error(request, error)
    else:
        messages.success(request, f"«{kpi.titulo}» guardado.")
    return redirect(f"/ajustes/kpis/#kpi-{slug}")


# ── Tableros por rol ─────────────────────────────────────────────────────


def _rol_de(valor: str | None):
    """`"omision"` → None (el tablero por omisión); un pk → ese Rol."""
    from cuentas.models.rol import Rol

    if not valor or valor == "omision":
        return None
    return get_object_or_404(Rol, pk=valor)


def _kpis_que_ve_el_rol(rol) -> list:
    """Lo que un rol puede ver por su JSON de permisos (super_admin: todo)."""
    from apps.taller_home.kpis import KPIS
    from apps.taller_home.permisos_kpi import puede_ver_con
    from apps.taller_home.tablero import apagados

    from lib.permisos_defaults import con_universales

    fuera = apagados()
    if rol is None or rol.clave == "super_admin":
        return [k for k in KPIS if k.slug not in fuera]
    mapa = con_universales(rol.permisos or {})
    return [k for k in KPIS if k.slug not in fuera and puede_ver_con(mapa, k.permisos)]


def _contexto_tablero(rol) -> dict:
    from apps.taller_home.kpis import kpi_por_slug
    from apps.taller_home.tablero import base_de_rol

    from cuentas.models.rol import Rol

    kpis, etiquetas = _catalogo()
    slugs = base_de_rol(rol)
    visibles = {k.slug for k in _kpis_que_ve_el_rol(rol)}
    filas = []
    for i, slug in enumerate(slugs):
        kpi = kpi_por_slug(slug)
        filas.append({
            "slug": slug, "titulo": kpi.titulo if kpi else slug,
            "existe": kpi is not None, "lo_ve": slug in visibles,
            "primero": i == 0, "ultimo": i == len(slugs) - 1,
        })
    disponibles: dict[str, list] = {}
    for k in _kpis_que_ve_el_rol(rol):
        if k.slug not in slugs:
            disponibles.setdefault(etiquetas.get(k.categoria, k.categoria), []).append(k)
    personas = rol.usuarios.filter(is_active=True).count() if rol is not None else None
    return {
        "rol": rol, "rol_valor": rol.pk if rol else "omision",
        "roles": Rol.objects.order_by("nombre"),
        "filas": filas, "disponibles": disponibles, "personas": personas,
    }


@requiere_permiso("kpis", "configurar")
def tableros(request):
    rol = _rol_de(request.GET.get("rol"))
    return render(request, "ajustes/kpis/tableros.html", {
        "tabs": TABS, "activo": "tableros", **_contexto_tablero(rol),
    })


@requiere_permiso("kpis", "configurar")
@require_http_methods(["POST"])
def tablero_accion(request):
    """Agregar, quitar, subir, bajar, copiar el por omisión o vaciar."""
    from apps.taller_home.kpis import kpi_por_slug
    from apps.taller_home.models import TableroKPI
    from apps.taller_home.tablero import base_de_rol

    rol = _rol_de(request.POST.get("rol"))
    accion = request.POST.get("accion", "")
    slug = request.POST.get("slug", "")
    slugs = base_de_rol(rol)

    if accion == "agregar":
        if kpi_por_slug(slug) is None:
            return HttpResponseBadRequest("KPI inexistente.")
        if slug not in slugs:
            slugs.append(slug)
    elif accion == "quitar":
        slugs = [s for s in slugs if s != slug]
    elif accion in ("subir", "bajar") and slug in slugs:
        i = slugs.index(slug)
        j = i - 1 if accion == "subir" else i + 1
        if 0 <= j < len(slugs):
            slugs[i], slugs[j] = slugs[j], slugs[i]
    elif accion == "copiar_omision" and rol is not None:
        slugs = base_de_rol(None)
    elif accion == "vaciar" and rol is not None:
        slugs = []
    else:
        return HttpResponseBadRequest("Acción inválida.")

    qs = TableroKPI.objects.filter(rol=rol) if rol else TableroKPI.objects.filter(rol__isnull=True)
    qs.delete()
    TableroKPI.objects.bulk_create(
        [TableroKPI(rol=rol, kpi_slug=s, orden=i) for i, s in enumerate(slugs)]
    )
    _emitir("kpi.configuracion_actualizada", request,
            {"que": "tablero", "rol": rol.clave if rol else "omision", "accion": accion,
             "kpi_slug": slug, "total": len(slugs)})

    if request.headers.get("HX-Request"):
        return render(request, "ajustes/kpis/_tablero.html", _contexto_tablero(rol))
    return redirect(f"/ajustes/kpis/tableros/?rol={rol.pk if rol else 'omision'}")


# ── Metas ────────────────────────────────────────────────────────────────


def _opciones_meta() -> list[dict]:
    """Los KPIs a los que se les puede poner meta, con los ámbitos que admiten."""
    kpis, etiquetas = _catalogo()
    salida = []
    for k in kpis:
        ambitos = [a for a in ("despacho", "persona", "cliente") if k.admite_meta(a)]
        if not ambitos:
            continue
        salida.append({
            "kpi": k, "ambitos": ",".join(ambitos),
            "categoria": etiquetas.get(k.categoria, k.categoria),
            "periodo": {"dia": "diaria", "semana": "semanal", "mes": "mensual",
                        "ano": "anual"}.get(k.acumula, "al corte"),
            "baja": k.direccion == "baja",
        })
    return salida


@requiere_permiso("kpis", "configurar")
def metas(request):
    from apps.la_cartera.models import Cliente
    from apps.taller_home.curaduria import proponer_metas
    from apps.taller_home.metas import estado_de_metas

    from cuentas.models.usuario import Usuario

    try:
        propuestas = proponer_metas()
    except Exception:  # noqa: BLE001 — sin historia no hay propuestas; la pantalla sigue
        propuestas = []
    return render(request, "ajustes/kpis/metas.html", {
        "tabs": TABS, "activo": "metas",
        "filas": estado_de_metas(activas_solo=False),
        "opciones": _opciones_meta(),
        "personas": Usuario.objects.filter(is_active=True).order_by("nombre_completo", "email"),
        "clientes": Cliente.objects.filter(activo=True).order_by("razon_social"),
        "propuestas": propuestas,
        "prefill": request.GET.get("kpi", ""),
        "prefill_valor": request.GET.get("valor", ""),
    })


@requiere_permiso("kpis", "configurar")
@require_http_methods(["POST"])
def meta_crear(request):
    from apps.la_cartera.models import Cliente
    from apps.taller_home.kpis import kpi_por_slug
    from apps.taller_home.metas import periodo_de
    from apps.taller_home.models import MetaKPI

    from cuentas.models.usuario import Usuario

    kpi = kpi_por_slug(request.POST.get("kpi_slug", ""))
    ambito = request.POST.get("ambito", "despacho")
    if kpi is None or not kpi.admite_meta(ambito):
        messages.error(request, "Ese KPI no admite una meta de ese tipo.")
        return redirect("ajustes-kpis-metas")
    try:
        valor = _decimal_o_none(request.POST.get("valor"))
    except ValueError:
        valor = None
    if valor is None or valor <= 0:
        messages.error(request, "Pon un valor mayor que cero para la meta.")
        return redirect("ajustes-kpis-metas")

    usuario = cliente = None
    if ambito == "persona":
        usuario = Usuario.objects.filter(pk=request.POST.get("usuario") or 0, is_active=True).first()
        if usuario is None:
            messages.error(request, "Elige a la persona de la meta.")
            return redirect("ajustes-kpis-metas")
    elif ambito == "cliente":
        cliente = Cliente.objects.filter(pk=request.POST.get("cliente") or 0).first()
        if cliente is None:
            messages.error(request, "Elige el cliente de la meta.")
            return redirect("ajustes-kpis-metas")

    meta, creada = MetaKPI.objects.update_or_create(
        kpi_slug=kpi.slug, ambito=ambito, usuario=usuario, cliente=cliente,
        defaults={"valor": valor, "periodo": periodo_de(kpi), "activa": True,
                  "actualizado_por": request.user, "avisado_periodo": ""},
    )
    _emitir("meta_kpi.actualizada", request,
            {"meta_id": meta.pk, "kpi_slug": kpi.slug, "ambito": ambito, "creada": creada})
    messages.success(request, f"Meta de «{kpi.titulo}» {'creada' if creada else 'actualizada'}.")
    return redirect("ajustes-kpis-metas")


@requiere_permiso("kpis", "configurar")
@require_http_methods(["POST"])
def meta_guardar(request, pk: int):
    from apps.taller_home.models import MetaKPI

    meta = get_object_or_404(MetaKPI, pk=pk)
    if request.POST.get("borrar") == "1":
        slug = meta.kpi_slug
        meta.delete()
        _emitir("meta_kpi.actualizada", request, {"meta_id": pk, "kpi_slug": slug, "borrada": True})
        messages.success(request, "Meta borrada.")
        return redirect("ajustes-kpis-metas")
    try:
        valor = _decimal_o_none(request.POST.get("valor"))
    except ValueError:
        valor = None
    if valor is None or valor <= 0:
        messages.error(request, "El valor de la meta debe ser mayor que cero.")
        return redirect("ajustes-kpis-metas")
    cambio_valor = valor != meta.valor
    meta.valor = valor
    meta.activa = request.POST.get("activa") == "1"
    meta.actualizado_por = request.user
    if cambio_valor:
        meta.avisado_periodo = ""   # con otra meta, se vuelve a poder avisar
    meta.save()
    _emitir("meta_kpi.actualizada", request, {"meta_id": pk, "kpi_slug": meta.kpi_slug})
    messages.success(request, "Meta guardada.")
    return redirect("ajustes-kpis-metas")


@requiere_permiso("kpis", "configurar")
def metas_viejo(request):
    """La URL de antes (`/ajustes/metas-kpi/`) lleva a la pestaña de metas."""
    return redirect("ajustes-kpis-metas")
