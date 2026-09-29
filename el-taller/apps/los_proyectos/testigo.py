"""Qué vigila El Testigo en un proyecto (S-Pendientes-Sep28 · Deploy 3).

El proyecto es el caso difícil del aviso de edición pisada: se autoguarda cada
vez que alguien toca un campo, y sus tarjetas de producto guardan por FUERA de
los campos del form —en un JSON que arma el navegador— los procesos de
producción, los procesos de venta y las opciones de volumen.

Así que además de los campos del proyecto y de cada línea, se vigilan esos tres
«hijos» de cada línea. Para saber si una línea los cambiaría, lo que manda el
navegador se normaliza con LAS MISMAS funciones que después los guardan
(`services_procesos.*_normalizados`) y se compara con lo que hay en la base
puesto en la misma forma.

Lo que NO se vigila, a propósito:

- **El orden de las tarjetas** (`orden`): lo guarda el arrastre por su cuenta y
  no es un dato del negocio; detener el autoguardado por él sería ruido.
- Los campos auxiliares que no salen de la base (`imagen_quitar` y los tres
  JSON crudos): su valor inicial siempre es vacío, así que nunca «cambian».

**La pestaña de una versión de cotización** (`ppv`) también se vigila
(`edicion_version`). Va en el MISMO POST que el proyecto, pero se carga por HTMX
después de la página, así que no cabe en el testigo del proyecto: lleva el suyo
en otro oculto (`CAMPO_VERSION`) y un contenedor propio por versión
(`edicion-testigo-ppv-<pk>`; con el pk, un autoguardado que regresa tarde no le
pone a la v2 el testigo de la v1). La vista revisa las dos piezas juntas
(`lib.edicion.revisar_juntas`): si una choca no se guarda ninguna, y el aviso
sale en el contenedor del proyecto, que es el que tiene el «Guardar la mía».
En la foto de una versión los procesos, ventas y escalas son columnas JSON de la
misma fila, pero el navegador los manda igual que en la línea viva, así que se
comparan igual: lo guardado y lo mandado pasan por el mismo normalizador.
"""

from __future__ import annotations

import json

from lib import edicion as ed

#: El oculto con el testigo de la pestaña de una versión (ver el docstring).
CAMPO_VERSION = "_edicion_testigo_ppv"

#: Lo que se ignora de cada línea (ver el docstring).
IGNORAR_LINEA = ("orden", "imagen_quitar", "procesos_json", "ventas_json", "escalas_json")

_CAMPOS_ESCALA = (
    "cantidad", "merma", "precio_unitario", "precio_unitario_expr",
    "costo_unitario", "costo_unitario_expr", "impresion_costo",
    "impresion_costo_expr", "impresion_por_pieza", "extras_json",
    "activa", "visible_pdf",
)


def _proceso(d) -> dict:
    tipo = d["tipo"]
    return {
        "tipo": tipo,
        "proveedor_id": d.get("proveedor_id"),
        "descripcion": (d.get("descripcion") or "") if tipo == "operativo" else "",
        "costo": d.get("costo"),
        "por_pieza": bool(d.get("por_pieza")),
        "costo_expr": d.get("costo_expr") or "",
    }


def _venta(d) -> dict:
    return {
        "descripcion": d.get("descripcion") or "",
        "cantidad": d.get("cantidad"),
        "precio_unitario": d.get("precio_unitario"),
        "precio_expr": d.get("precio_expr") or "",
    }


def _escala(d) -> dict:
    return {c: d.get(c) for c in _CAMPOS_ESCALA}


def hijos_de(proyecto) -> dict[int, dict[str, str]]:
    """Procesos, ventas y escalas de TODAS las líneas, en tres consultas.

    Devuelve `{pk_linea: {"procesos": canónico, "ventas": …, "escalas": …}}`."""
    from .models import ProyectoProductoEscala, ProyectoProductoProceso, ProyectoProductoVenta

    salida: dict[int, dict[str, list]] = {}

    def _lista(pk, clave):
        return salida.setdefault(pk, {"procesos": [], "ventas": [], "escalas": []})[clave]

    for p in (ProyectoProductoProceso.objects.filter(producto__proyecto=proyecto)
              .order_by("producto_id", "orden", "creado_en")):
        _lista(p.producto_id, "procesos").append(_proceso({
            "tipo": p.tipo, "proveedor_id": p.proveedor_id, "descripcion": p.descripcion,
            "costo": p.costo, "por_pieza": p.por_pieza, "costo_expr": p.costo_expr,
        }))
    for v in (ProyectoProductoVenta.objects.filter(producto__proyecto=proyecto)
              .order_by("producto_id", "orden", "creado_en")):
        _lista(v.producto_id, "ventas").append(_venta({
            "descripcion": v.descripcion, "cantidad": v.cantidad,
            "precio_unitario": v.precio_unitario, "precio_expr": v.precio_expr,
        }))
    for e in (ProyectoProductoEscala.objects.filter(producto__proyecto=proyecto)
              .order_by("producto_id", "orden", "creado_en")):
        _lista(e.producto_id, "escalas").append(_escala({c: getattr(e, c) for c in _CAMPOS_ESCALA}))

    return {pk: {k: ed.lista_canonica(v) for k, v in d.items()} for pk, d in salida.items()}


_VACIO = ed.lista_canonica([])


def _posteado(form, campo, normalizar, forma):
    """Lo que manda el navegador para un hijo, normalizado y canónico (o SIN_DATO)."""
    def _calc():
        crudo = form.data.get(form.add_prefix(campo))
        if crudo is None:
            return ed.SIN_DATO
        deseados = normalizar(crudo)
        if deseados is None:
            return ed.SIN_DATO     # JSON ilegible: el guardado tampoco lo toca
        return ed.lista_canonica([forma(d) for d in deseados])
    return _calc


def _legible(form, campo, normalizar, renglon):
    def _calc():
        deseados = normalizar(form.data.get(form.add_prefix(campo))) or []
        return " · ".join(renglon(d) for d in deseados) or "(ninguno)"
    return _calc


def _renglon_proceso(d) -> str:
    nombre = d.get("descripcion") or ("Impresión" if d.get("tipo") == "impresion" else "Proceso")
    return f"{nombre} ${d.get('costo')}"


def _renglon_venta(d) -> str:
    return f"{d.get('descripcion') or 'Proceso de venta'} × {d.get('cantidad')} a ${d.get('precio_unitario')}"


def _renglon_escala(d) -> str:
    precio = d.get("precio_unitario")
    return f"{d.get('cantidad')} pz a {'$' + str(precio) if precio is not None else 'precio de la opción A'}"


def edicion_proyecto(proyecto, form, formset) -> ed.Edicion:
    """La `Edicion` del detalle (y del editar) de un proyecto."""
    from .services_procesos import escalas_normalizadas, procesos_normalizados, ventas_normalizadas

    hijos = hijos_de(proyecto) if getattr(proyecto, "pk", None) else {}

    def extras_linea(f):
        inst = f.instance
        pk = getattr(inst, "pk", None)
        if pk is None:
            return {}
        actual = hijos.get(pk, {})
        nombre = inst.nombre_visible or "el producto"
        return {
            "procesos": ed.Extra(
                etiqueta=f"Procesos de producción de «{nombre}»",
                actual=actual.get("procesos", _VACIO),
                posteado=_posteado(f, "procesos_json", procesos_normalizados, _proceso),
                legible=_legible(f, "procesos_json", procesos_normalizados, _renglon_proceso),
            ),
            "ventas": ed.Extra(
                etiqueta=f"Procesos de venta de «{nombre}»",
                actual=actual.get("ventas", _VACIO),
                posteado=_posteado(f, "ventas_json", ventas_normalizadas, _venta),
                legible=_legible(f, "ventas_json", ventas_normalizadas, _renglon_venta),
            ),
            "escalas": ed.Extra(
                etiqueta=f"Opciones de volumen de «{nombre}»",
                actual=actual.get("escalas", _VACIO),
                posteado=_posteado(f, "escalas_json", escalas_normalizadas, _escala),
                legible=_legible(f, "escalas_json", escalas_normalizadas, _renglon_escala),
            ),
        }

    grupos = {}
    if formset is not None:
        grupos["productos"] = ed.Grupo(
            formset,
            etiqueta_linea=lambda pp: f"«{pp.nombre_visible or 'producto'}»",
            extras_linea=extras_linea,
            ignorar=IGNORAR_LINEA,
        )
    return ed.Edicion(proyecto, form, grupos=grupos)


# ── La pestaña de una versión de cotización ────────────────────────────────


def _guardado(valor, normalizar, forma) -> str:
    """Lo que la foto tiene guardado en una columna JSON, en la forma canónica de
    lo mandado: pasa por el MISMO normalizador que lo que llega del navegador."""
    try:
        deseados = normalizar(json.dumps(valor or [], default=str))
    except Exception:  # noqa: BLE001 - una foto rara no tumba el testigo
        deseados = None
    return ed.lista_canonica([forma(d) for d in (deseados or [])])


def edicion_version(cot, formset) -> ed.Edicion:
    """La `Edicion` de la pestaña de una versión: sólo líneas, sin form propio.

    La firma queda en la cotización (ninguna fila de la foto tiene
    `actualizado_en`), que además es lo que el guardado de la pestaña reescribe
    —sus líneas del documento—: así la pantalla de la cotización también sabe
    quién fue."""
    from .services_procesos import escalas_normalizadas, procesos_normalizados, ventas_normalizadas

    etiqueta_version = getattr(cot, "version_label", "") or "versión"
    # Lo guardado se lee AHORA, antes de que `is_valid()` toque las instancias.
    guardado: dict[int, dict[str, str]] = {}
    for f in ed._formas_existentes(formset):
        inst = f.instance
        if getattr(inst, "pk", None) is None:
            continue
        guardado[inst.pk] = {
            "procesos": _guardado(inst.procesos_json, procesos_normalizados, _proceso),
            "ventas": _guardado(inst.ventas_json, ventas_normalizadas, _venta),
            "escalas": _guardado(inst.escalas_json, escalas_normalizadas, _escala),
        }

    def _nombre(inst) -> str:
        return f"«{inst.nombre_visible or 'producto'}» ({etiqueta_version})"

    def extras_linea(f):
        inst = f.instance
        pk = getattr(inst, "pk", None)
        if pk is None:
            return {}
        actual = guardado.get(pk, {})
        nombre = _nombre(inst)
        return {
            "procesos": ed.Extra(
                etiqueta=f"Procesos de producción de {nombre}",
                actual=actual.get("procesos", _VACIO),
                posteado=_posteado(f, "procesos_json", procesos_normalizados, _proceso),
                legible=_legible(f, "procesos_json", procesos_normalizados, _renglon_proceso),
            ),
            "ventas": ed.Extra(
                etiqueta=f"Procesos de venta de {nombre}",
                actual=actual.get("ventas", _VACIO),
                posteado=_posteado(f, "ventas_json", ventas_normalizadas, _venta),
                legible=_legible(f, "ventas_json", ventas_normalizadas, _renglon_venta),
            ),
            "escalas": ed.Extra(
                etiqueta=f"Opciones de volumen de {nombre}",
                actual=actual.get("escalas", _VACIO),
                posteado=_posteado(f, "escalas_json", escalas_normalizadas, _escala),
                legible=_legible(f, "escalas_json", escalas_normalizadas, _renglon_escala),
            ),
        }

    grupo = ed.Grupo(formset, etiqueta_linea=_nombre, extras_linea=extras_linea,
                     ignorar=IGNORAR_LINEA)
    return ed.Edicion(cot, None, grupos={"version": grupo}, campo=CAMPO_VERSION)


def contexto_version(cot, testigo: str) -> dict:
    """Lo que necesita `edicion/_testigo_pieza.html` para la pestaña."""
    return {"id": f"{ed.ID_CONTENEDOR}-ppv-{cot.pk}", "campo": CAMPO_VERSION,
            "testigo": testigo}
