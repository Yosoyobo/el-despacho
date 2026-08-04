"""Resumen ejecutivo del calendario (LC 2026-07-29, rehecho 2026-08-04).

Oscar (2026-08-04) lo pidió como **la lista de todo lo que viene**: detallado lo
más próximo —hoy, esta semana y las siguientes cuatro— y general de ahí en
adelante. Además: nombres de proyecto (nunca códigos), listas numeradas, las
tareas atrasadas en amarillo con el proyecto al lado, y las entregas con sus
productos anidados.

Las secciones se arman **con consultas, no con IA**: un calendario no tiene nada
que interpretar, así que sale exacto, instantáneo y gratis (mismo criterio que el
reporte de pendientes del Dashboard). El Chalán pone encima **una frase** de
lectura de la carga; si no responde, las secciones se muestran igual.

Cada renglón es un dict `{texto, tono, sub}`:
  · `tono` = "" normal · "atrasado" (amarillo).
  · `sub`  = sub-viñetas (los productos de una entrega).

Respeta permisos: todo sale de `services.eventos_por_dia` /
`_proyectos_visibles_qs` / `_tareas_visibles`, que ya filtran por lo que el
usuario puede ver.
"""

from __future__ import annotations

from datetime import date, timedelta

# Tope por sección: un resumen ejecutivo no puede tener 80 renglones.
LIMITE_SECCION = 12

# Ventana de las entregas con su detalle de productos.
DIAS_ENTREGAS = 90

# Semanas completas que se detallan DESPUÉS de la semana en curso (Oscar: «1, 2,
# 3, 4 semanas»). Lo que cae más allá se resume en una línea general.
SEMANAS_FUTURAS = 4

_DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
_MESES = ("ene", "feb", "mar", "abr", "may", "jun",
          "jul", "ago", "sep", "oct", "nov", "dic")

_TITULOS_SEMANA = ("La próxima semana", "En 2 semanas", "En 3 semanas", "En 4 semanas")


def _dia_legible(d: date, hoy: date) -> str:
    """«hoy», «mañana» o «vie 31 jul» — corto, para leer de un golpe."""
    if d == hoy:
        return "hoy"
    if d == hoy + timedelta(days=1):
        return "mañana"
    return f"{_DIAS[d.weekday()]} {d.day} {_MESES[d.month - 1]}"


def _rango_legible(ini: date, fin: date) -> str:
    """«10–16 ago» / «28 ago–3 sep», para el título de cada semana."""
    if ini.month == fin.month:
        return f"{ini.day}–{fin.day} {_MESES[fin.month - 1]}"
    return f"{ini.day} {_MESES[ini.month - 1]}–{fin.day} {_MESES[fin.month - 1]}"


def _linea(texto: str, *, tono: str = "", sub: list[str] | None = None) -> dict:
    return {"texto": texto, "tono": tono, "sub": sub or []}


def _texto_evento(ev: dict) -> str:
    """El evento como se lee: título ya formateado (emoji + hora) + su
    subtítulo, que para las tareas es el NOMBRE del proyecto (no el código)."""
    titulo = (ev.get("titulo") or "").strip()
    sub = (ev.get("subtitulo") or "").strip()
    return f"{titulo} — {sub}" if sub else titulo


def _productos_de(proyecto) -> list[str]:
    """Los productos que se entregan, con su cantidad. El alias del proyecto
    manda sobre el nombre del catálogo (`nombre_visible`)."""
    try:
        lineas = list(proyecto.productos_incluidos)
    except Exception:  # noqa: BLE001 — un proyecto raro no tumba el resumen
        return []
    salida: list[str] = []
    for pp in lineas[:6]:
        cantidad = getattr(pp, "cantidad", None)
        nombre = pp.nombre_visible
        salida.append(f"{nombre} · {cantidad} pz" if cantidad else nombre)
    if len(lineas) > 6:
        salida.append(f"y {len(lineas) - 6} producto(s) más")
    return salida


def _lineas_de_rango(por_dia: dict, ini: date, fin: date, hoy: date) -> list[dict]:
    """Los eventos de un rango de días, en orden, con su día al frente."""
    lineas: list[dict] = []
    dia = ini
    while dia <= fin:
        for ev in por_dia.get(dia, []):
            lineas.append(_linea(f"{_dia_legible(dia, hoy)}: {_texto_evento(ev)}"))
        dia += timedelta(days=1)
    return lineas


def _seccion_tareas(usuario, hoy: date) -> list[dict]:
    """Tareas abiertas por fecha. Las ATRASADAS van en amarillo y con el nombre
    del proyecto al lado (Oscar 2026-08-04, punto 3)."""
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    from apps.el_pizarron.views import _tareas_visibles

    tareas = (
        _tareas_visibles(usuario)
        .filter(archivada=False)
        .exclude(estado__in=slugs_terminales_tarea())
        .select_related("proyecto", "asignada_a")
        .order_by("fecha_compromiso", "pk")
        .distinct()[: LIMITE_SECCION + 1]
    )
    lineas: list[dict] = []
    for t in tareas:
        atrasada = bool(t.fecha_compromiso and t.fecha_compromiso < hoy)
        cuando = _dia_legible(t.fecha_compromiso, hoy) if t.fecha_compromiso else "sin fecha"
        quien = ""
        if t.asignada_a_id:
            quien = f" ({t.asignada_a.nombre_completo or t.asignada_a.email})"
        proyecto = ""
        if t.proyecto_id:
            proyecto = f" - {t.proyecto.nombre or t.proyecto.codigo}"
        texto = f"{cuando}: {t.titulo}{proyecto}{quien}"
        lineas.append(_linea(texto, tono="atrasado" if atrasada else ""))
    return lineas


def _seccion_entregas(usuario, hoy: date) -> list[dict]:
    """«fecha · proyecto» con sus productos anidados (Oscar, punto 4)."""
    from django.utils import timezone

    from .services import _proyectos_visibles_qs

    proyectos = (
        _proyectos_visibles_qs(usuario)
        .filter(fecha_compromiso__date__gte=hoy,
                fecha_compromiso__date__lte=hoy + timedelta(days=DIAS_ENTREGAS))
        .order_by("fecha_compromiso")[: LIMITE_SECCION + 1]
    )
    lineas: list[dict] = []
    for p in proyectos:
        cuando = _dia_legible(timezone.localtime(p.fecha_compromiso).date(), hoy)
        nombre = p.nombre or p.codigo
        lineas.append(_linea(f"{cuando} · {nombre}", sub=_productos_de(p)))
    return lineas


def secciones_calendario(usuario) -> list[dict]:
    """Las secciones del resumen, en orden de lectura.

    Devuelve `[{titulo, lineas}]` donde cada línea es `{texto, tono, sub}`. Las
    secciones vacías se omiten salvo «Hoy», que siempre sale (que no haya nada
    hoy también es información).
    """
    from django.utils import timezone

    from .services import eventos_por_dia

    hoy = timezone.localdate()
    lunes = hoy - timedelta(days=hoy.weekday())
    # La semana en curso + las 4 siguientes van al detalle.
    fin_detalle = lunes + timedelta(days=7 * (SEMANAS_FUTURAS + 1) - 1)
    # Un solo barrido para toda la ventana detallada (y para «hoy»).
    por_dia = eventos_por_dia(usuario, min(hoy, lunes), fin_detalle)

    secciones: list[dict] = [{
        "titulo": "Hoy",
        "lineas": [_linea(_texto_evento(ev)) for ev in por_dia.get(hoy, [])]
                  or [_linea("Nada agendado.")],
    }]

    # Resto de la semana en curso (de mañana al domingo).
    domingo = lunes + timedelta(days=6)
    if hoy < domingo:
        candidatas = [("Esta semana", _lineas_de_rango(por_dia, hoy + timedelta(days=1), domingo, hoy))]
    else:
        candidatas = []

    # Las siguientes semanas completas, cada una con su rango en el título.
    for i in range(SEMANAS_FUTURAS):
        ini = lunes + timedelta(days=7 * (i + 1))
        fin = ini + timedelta(days=6)
        candidatas.append((
            f"{_TITULOS_SEMANA[i]} ({_rango_legible(ini, fin)})",
            _lineas_de_rango(por_dia, ini, fin, hoy),
        ))

    candidatas.append(("Tareas", _seccion_tareas(usuario, hoy)))
    candidatas.append(("Siguientes entregas", _seccion_entregas(usuario, hoy)))
    candidatas.append(("Más adelante", _mas_adelante(usuario, fin_detalle + timedelta(days=1))))

    for titulo, lineas in candidatas:
        if lineas:
            secciones.append({"titulo": titulo, "lineas": lineas[:LIMITE_SECCION]})
    return secciones


def _mas_adelante(usuario, desde: date) -> list[dict]:
    """Lo que cae después de la ventana detallada: general pero claro.

    Oscar: «y lo demás algo general pero claro» — cuántas entregas y tareas hay,
    en qué rango de fechas, y cuál es la más próxima.
    """
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    from apps.el_pizarron.views import _tareas_visibles
    from django.utils import timezone

    from .services import _proyectos_visibles_qs

    entregas = list(
        _proyectos_visibles_qs(usuario)
        .filter(fecha_compromiso__date__gte=desde)
        .order_by("fecha_compromiso")[:200]
    )
    tareas = list(
        _tareas_visibles(usuario)
        .filter(archivada=False, fecha_compromiso__gte=desde)
        .exclude(estado__in=slugs_terminales_tarea())
        .select_related("proyecto")
        .order_by("fecha_compromiso")
        .distinct()[:200]
    )
    if not entregas and not tareas:
        return []

    lineas: list[dict] = []
    if entregas:
        primera = timezone.localtime(entregas[0].fecha_compromiso).date()
        ultima = timezone.localtime(entregas[-1].fecha_compromiso).date()
        detalle = f"{len(entregas)} entrega(s) entre {_fecha_larga(primera)} y {_fecha_larga(ultima)}"
        lineas.append(_linea(
            detalle,
            sub=[f"{_fecha_larga(timezone.localtime(p.fecha_compromiso).date())} · "
                 f"{p.nombre or p.codigo}" for p in entregas[:3]],
        ))
    if tareas:
        lineas.append(_linea(
            f"{len(tareas)} tarea(s) con fecha, la más próxima el "
            f"{_fecha_larga(tareas[0].fecha_compromiso)}"
            f" ({tareas[0].titulo})",
        ))
    return lineas


def _fecha_larga(d: date) -> str:
    """«14 sep» con el año sólo si no es el actual."""
    from django.utils import timezone
    texto = f"{d.day} {_MESES[d.month - 1]}"
    return texto if d.year == timezone.localdate().year else f"{texto} {d.year}"


def texto_calendario(usuario) -> str:
    """Las secciones en texto plano y NUMERADAS (para el prompt del Chalán y
    para copiar al portapapeles)."""
    partes: list[str] = []
    for sec in secciones_calendario(usuario):
        partes.append(f"{sec['titulo']}:")
        for i, linea in enumerate(sec["lineas"], start=1):
            marca = " (atrasada)" if linea["tono"] == "atrasado" else ""
            partes.append(f"{i}. {linea['texto']}{marca}")
            partes += [f"   • {s}" for s in linea["sub"]]
        partes.append("")
    return "\n".join(partes).strip()


__all__ = ["secciones_calendario", "texto_calendario", "LIMITE_SECCION"]
