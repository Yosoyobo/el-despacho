"""Mini-Chalán del quick-create de proyecto (revisión buzón R2).

El usuario describe los productos del proyecto en lenguaje natural y El Chalán
los interpreta a líneas concretas. **Propone, no aplica** (regla §20): la vista
muestra un preview con checkboxes y el usuario confirma cuáles agregar.

Diseño defensivo: `interpretar_productos` NUNCA lanza — devuelve
`{ok, productos, error}`. `aplicar_productos` re-valida permisos y solo crea
productos nuevos en el Catálogo si el usuario tiene `catalogo.crear`.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

_MAX_TOKENS = 900
_MAX_PRODUCTOS = 40


def _parsear_json(texto: str) -> dict | None:
    if not texto:
        return None
    limpio = re.sub(r"^```(?:json)?", "", texto.strip()).strip()
    limpio = re.sub(r"```$", "", limpio).strip()
    m = re.search(r"\{.*\}", limpio, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _entero(v, default: int, minimo: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = default
    return max(minimo, n)


def _dec_opt(v):
    if v in (None, "", "null"):
        return None
    try:
        d = Decimal(str(v)).quantize(Decimal("0.01"))
    except (TypeError, ValueError, InvalidOperation):
        return None
    return d if d >= 0 else None


def _resolver_catalogo(nombre: str):
    """Servicio del catálogo por nombre (exacto → contiene). None si es nuevo."""
    from apps.el_catalogo.models import Servicio
    nombre = (nombre or "").strip()
    if not nombre:
        return None
    return (
        Servicio.objects.filter(nombre__iexact=nombre, activo=True).first()
        or Servicio.objects.filter(nombre__icontains=nombre, activo=True).first()
    )


def interpretar_productos(*, proyecto, texto: str, usuario) -> dict:
    """Interpreta `texto` a líneas de producto para `proyecto`. Nunca lanza."""
    texto = (texto or "").strip()
    if not texto:
        return {"ok": False, "error": "Describe primero los productos.", "productos": []}

    from apps.el_catalogo.models import Servicio
    catalogo = list(
        Servicio.objects.filter(activo=True).order_by("nombre").values_list("nombre", flat=True)[:120]
    )
    lista_cat = "\n".join(f"- {n}" for n in catalogo) or "(catálogo vacío)"

    system = (
        "Eres El Chalán de Learning Center. El usuario describe los productos que "
        "lleva un proyecto y tú los conviertes a líneas concretas. Responde SOLO "
        "JSON estricto, sin texto fuera:\n"
        '{"productos": [{"nombre": "<producto>", "cantidad": <entero>=1>, '
        '"precio_unitario": <número|null>, "nota": "<texto corto|vacío>"}]}\n'
        "Reglas: usa el NOMBRE EXACTO del catálogo cuando el producto ya exista "
        "(lista abajo); si el usuario menciona uno que no está, ponlo con su "
        "nombre tal cual (se marcará como nuevo). No inventes precios: si el "
        "usuario no dio precio, usa null. cantidad entera >= 1 (default 1). "
        "No agregues productos que el usuario no mencionó."
    )
    user = f"CATÁLOGO DISPONIBLE:\n{lista_cat}\n\nDESCRIPCIÓN DEL USUARIO:\n{texto}"

    try:
        from chalanes.voz import preludio, reglas
        from lib.analistas import PresupuestoIAExcedido, analizar
        from lib.sanear import sanear_contexto
        prompt = preludio("dictado") + system + reglas() + "\n\n" + sanear_contexto(user, max_len=4000)
        try:
            res = analizar(estacion="dictado", prompt=prompt, max_tokens=_MAX_TOKENS,
                           temperatura=0.1, actor_id=getattr(usuario, "pk", None))
        except PresupuestoIAExcedido:
            return {"ok": False, "productos": [],
                    "error": "Se alcanzó el tope de gasto de IA del mes. Agrega los productos a mano."}
    except Exception as exc:  # noqa: BLE001 — nunca tumbar el flujo
        return {"ok": False, "productos": [], "error": f"El Chalán no respondió: {str(exc)[:200]}"}

    crudo = _parsear_json(getattr(res, "texto", "") or "")
    if not crudo or not isinstance(crudo.get("productos"), list):
        return {"ok": False, "productos": [],
                "error": "El Chalán no devolvió productos legibles. Intenta describirlos de otra forma."}

    productos = []
    for item in crudo["productos"][:_MAX_PRODUCTOS]:
        if not isinstance(item, dict):
            continue
        nombre = (item.get("nombre") or "").strip()[:150]
        if not nombre:
            continue
        srv = _resolver_catalogo(nombre)
        precio = _dec_opt(item.get("precio_unitario"))
        productos.append({
            "nombre": srv.nombre if srv else nombre,
            "cantidad": _entero(item.get("cantidad"), 1, 1),
            "precio_unitario": str(precio) if precio is not None else "",
            "nota": (item.get("nota") or "").strip()[:200],
            "servicio_id": srv.pk if srv else None,
            "es_nuevo": srv is None,
        })

    if not productos:
        return {"ok": False, "productos": [],
                "error": "El Chalán no identificó productos en la descripción."}
    return {"ok": True, "productos": productos, "error": ""}


def aplicar_productos(*, proyecto, lineas: list[dict], usuario) -> dict:
    """Crea las líneas `ProyectoProducto` seleccionadas. Re-valida permisos.

    Productos nuevos (sin `servicio_id`) requieren `catalogo.crear`; si el
    usuario no lo tiene, se omiten con aviso.
    """
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    from lib.permisos import puede_crear_catalogo, puede_editar_proyecto

    if not puede_editar_proyecto(usuario, proyecto):
        return {"agregados": 0, "omitidos": 0, "mensajes": ["Sin permiso para editar el proyecto."]}

    puede_crear = puede_crear_catalogo(usuario)
    agregados, omitidos, mensajes = 0, 0, []
    categoria_default = CategoriaServicio.objects.filter(activa=True).order_by("orden").first()

    for linea in lineas:
        nombre = (linea.get("nombre") or "").strip()[:150]
        if not nombre:
            continue
        cantidad = _entero(linea.get("cantidad"), 1, 1)
        precio = _dec_opt(linea.get("precio_unitario"))
        nota = (linea.get("nota") or "").strip()[:200]

        servicio = None
        sid = linea.get("servicio_id")
        if sid:
            servicio = Servicio.objects.filter(pk=sid, activo=True).first()
        if servicio is None:
            servicio = _resolver_catalogo(nombre)  # revalida por nombre
        if servicio is None:
            # Producto nuevo: crearlo en el catálogo si hay permiso.
            if not puede_crear:
                omitidos += 1
                mensajes.append(f"«{nombre}» es nuevo y no tienes permiso para crear productos.")
                continue
            if categoria_default is None:
                omitidos += 1
                mensajes.append("No hay categorías activas en el Catálogo para crear productos nuevos.")
                continue
            servicio = Servicio.objects.create(
                nombre=nombre, precio_base=(precio or Decimal("0.00")),
                categoria=categoria_default, creado_por=usuario,
            )
            _emitir_servicio_creado(servicio, usuario)

        ProyectoProducto.objects.create(
            proyecto=proyecto, servicio=servicio, cantidad=cantidad,
            precio_unitario=precio, nota=nota,
        )
        agregados += 1

    if agregados:
        proyecto.recalcular_monto_estimado()
    return {"agregados": agregados, "omitidos": omitidos, "mensajes": mensajes}


def _emitir_servicio_creado(servicio, usuario) -> None:
    import contextlib
    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="catalogo.servicio_creado",
            actor_id=getattr(usuario, "pk", None), actor_email=getattr(usuario, "email", None),
            payload={"servicio_id": servicio.pk, "nombre": servicio.nombre, "origen": "proyecto_quickcreate"},
        ))


__all__ = ["interpretar_productos", "aplicar_productos"]
