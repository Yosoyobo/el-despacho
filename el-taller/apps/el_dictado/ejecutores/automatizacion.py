"""Prender, apagar y quitar automatizaciones (n8n), por conversación.

Oscar quería que El Chalán pudiera «hacer y deshacer flujos», y desde el
principio con *muchos guardrails*. Aquí están los tres que se pueden hacer sin
riesgo de inventar nada:

- **prender** una automatización que ya existe,
- **apagarla**,
- **quitarla** cuando ya no sirve.

Cada uno pasa por el camino de siempre: El Chalán propone, aparece en la
pantalla con lo que va a hacer, y **nada ocurre hasta que un humano confirma**
(§20). Y al aplicarse se vuelve a comprobar el permiso, aunque el prompt ya
haya filtrado por rol — el prompt es una sugerencia, esto es la puerta.

**Por qué prender no es una acción cualquiera.** Una automatización activa le
manda correos a clientes. Que un modelo pueda encenderla sin que nadie la mire
sería regalarle la voz del despacho a un programa.

**Lo que NO está aquí, a propósito: crear un flujo desde cero.** Un flujo de
n8n es un grafo de nodos con su forma exacta; pedirle a un modelo que lo invente
produce, casi siempre, un flujo que se ve bien y no corre. Crear se hace en n8n,
donde se puede probar antes de prenderlo; El Chalán ayuda a operarlos, no a
adivinarlos. El cliente ya tiene `n8n.crear()` para el día que existan
plantillas de las que partir.
"""

from __future__ import annotations

from . import _gate, registrar


def _exigir_llave():
    from lib import n8n

    if not n8n.esta_configurado():
        raise ValueError(
            "Las automatizaciones no están conectadas: falta pegar la llave de n8n "
            "en Gerencia → Los Ajustes."
        )
    return n8n


def _flujo(accion) -> tuple[str, str]:
    """(id, nombre) del flujo que pide la acción. Lanza si no existe.

    Se resuelve por id o por nombre, porque quien habla dice «el de las
    facturas», no un identificador. Un nombre ambiguo NO se adivina: se pide
    que lo precisen, que es lo mismo que hace el resto del repo con clientes y
    proyectos.
    """
    n8n = _exigir_llave()
    payload = accion.payload if hasattr(accion, "payload") else (accion or {})
    pedido = str(payload.get("flujo_id") or payload.get("nombre") or "").strip()
    if not pedido:
        raise ValueError("Falta decir cuál automatización.")

    flujos = n8n.listar_flujos()
    if flujos is None:
        raise ValueError("n8n no contestó; no se puede saber qué automatizaciones hay.")

    porid = [f for f in flujos if f["id"] == pedido]
    if porid:
        return porid[0]["id"], porid[0]["nombre"]

    bajo = pedido.lower()
    exactos = [f for f in flujos if f["nombre"].lower() == bajo]
    if len(exactos) == 1:
        return exactos[0]["id"], exactos[0]["nombre"]

    parciales = [f for f in flujos if bajo in f["nombre"].lower()]
    if len(parciales) == 1:
        return parciales[0]["id"], parciales[0]["nombre"]
    if len(parciales) > 1:
        nombres = ", ".join(f"«{f['nombre']}»" for f in parciales[:5])
        raise ValueError(f"Hay varias que coinciden ({nombres}). ¿Cuál de ellas?")

    raise ValueError(f"No hay ninguna automatización que se llame «{pedido}».")


@registrar("activar_automatizacion")
def activar_automatizacion(accion, usuario, contexto=None):
    """Prende una automatización que ya existe."""
    _gate(usuario, "puede_acceder_ajustes", "prender automatizaciones")
    n8n = _exigir_llave()
    fid, nombre = _flujo(accion)
    if not n8n.activar(fid):
        raise ValueError(f"n8n no pudo prender «{nombre}».")
    return {"entidad_tipo": "automatizacion", "entidad_id": fid,
            "resumen": f"Automatización «{nombre}» prendida."}


@registrar("desactivar_automatizacion")
def desactivar_automatizacion(accion, usuario, contexto=None):
    """Apaga una automatización. No la borra: se puede volver a prender."""
    _gate(usuario, "puede_acceder_ajustes", "apagar automatizaciones")
    n8n = _exigir_llave()
    fid, nombre = _flujo(accion)
    if not n8n.desactivar(fid):
        raise ValueError(f"n8n no pudo apagar «{nombre}».")
    return {"entidad_tipo": "automatizacion", "entidad_id": fid,
            "resumen": f"Automatización «{nombre}» apagada."}


@registrar("borrar_automatizacion")
def borrar_automatizacion(accion, usuario, contexto=None):
    """Quita una automatización de n8n. Esto SÍ es permanente.

    Se apaga antes de borrar: si algo falla a media operación, queda apagada y
    no a medio camino ejecutándose.
    """
    _gate(usuario, "puede_acceder_ajustes", "quitar automatizaciones")
    n8n = _exigir_llave()
    fid, nombre = _flujo(accion)
    n8n.desactivar(fid)
    if not n8n.borrar(fid):
        raise ValueError(f"n8n no pudo quitar «{nombre}» (quedó apagada).")
    return {"entidad_tipo": "automatizacion", "entidad_id": fid,
            "resumen": f"Automatización «{nombre}» quitada."}
