"""Sugerencia de proveedores con IA basada en el historial (S-Chalanes-UX hotfix).

Dado el nombre/descripción de un producto, El Chalán propone qué proveedores
(de los ya registrados) podrían surtirlo, usando como pista qué productos surte
hoy cada proveedor (historial real de la M2M Servicio↔Proveedor).

Defensivo: nunca lanza — devuelve {ok, sugeridos:[{id, razon_social, motivo}], error}.
"""

from __future__ import annotations

import json
import re

_SYSTEM = """\
Eres El Chalán de Learning Center (despacho de diseño y maquila). Te doy un
PRODUCTO nuevo y una lista de PROVEEDORES con los productos que ya surten.
Devuelve SOLO un arreglo JSON con los proveedores que más probablemente puedan
surtir el producto nuevo, así:
[{"id": 12, "motivo": "ya surte playeras y bordado"}]
Reglas: usa SOLO ids de la lista; máximo 5; si ninguno encaja, devuelve [].
Sin texto fuera del JSON, sin ```.
"""

_RE_JSON = re.compile(r"\[.*\]", re.DOTALL)


def sugerir_proveedores(*, nombre: str, descripcion: str = "", usuario=None) -> dict:
    nombre = (nombre or "").strip()
    if not nombre:
        return {"ok": False, "sugeridos": [], "error": "Escribe primero el nombre del producto."}

    from .models import Proveedor
    proveedores = list(
        Proveedor.objects.filter(activo=True).prefetch_related("servicios")[:60])
    if not proveedores:
        return {"ok": False, "sugeridos": [], "error": "Aún no hay proveedores registrados."}

    lineas = []
    for p in proveedores:
        prods = ", ".join(s.nombre for s in p.servicios.all()[:8]) or "(sin historial)"
        lineas.append(f"id={p.pk} · {p.razon_social} · surte: {prods}")
    user_prompt = (
        f"PRODUCTO NUEVO:\n{nombre}\n{descripcion}\n\n"
        f"PROVEEDORES DISPONIBLES:\n" + "\n".join(lineas)
    )

    try:
        from chalanes.voz import preludio
        from lib.analistas import analizar
        from lib.sanear import sanear_contexto
        prompt = preludio("redaccion_asistida") + _SYSTEM + "\n\n" + sanear_contexto(user_prompt, max_len=6000)
        res = analizar(estacion="redaccion_asistida", prompt=prompt,
                       max_tokens=400, temperatura=0.2,
                       actor_id=getattr(usuario, "pk", None))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "sugeridos": [], "error": f"El Chalán no respondió: {exc}"}

    m = _RE_JSON.search(res.texto or "")
    if not m:
        return {"ok": False, "sugeridos": [], "error": "El Chalán no devolvió sugerencias."}
    try:
        crudo = json.loads(m.group(0))
    except (ValueError, TypeError):
        return {"ok": False, "sugeridos": [], "error": "Respuesta de El Chalán ilegible."}

    validos = {p.pk: p for p in proveedores}
    sugeridos = []
    for item in crudo if isinstance(crudo, list) else []:
        try:
            pid = int(item.get("id"))
        except (TypeError, ValueError, AttributeError):
            continue
        if pid in validos:
            sugeridos.append({
                "id": pid,
                "razon_social": validos[pid].razon_social,
                "motivo": str(item.get("motivo") or "")[:120],
            })
    return {"ok": True, "sugeridos": sugeridos, "error": ""}
