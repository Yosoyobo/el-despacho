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

**Crear un flujo desde cero** se abrió el 2026-08-24, a pedido de Oscar («a ver
qué puede hacer con los guardrails que pusimos»). La objeción que lo tenía
cerrado sigue siendo cierta —un modelo inventando un grafo produce, casi
siempre, algo que se ve bien y no corre— así que no se abrió a pelo:

- hay **recetas** de las que partir (`lib/n8n_plantillas.py`), con la forma de
  los nodos ya verificada, para que armar un flujo sea rellenar huecos;
- el grafo libre se permite, pero **se revisa y se dice la verdad**: n8n guarda
  sin chistar un nodo cuyo tipo no existe, así que «creado con éxito» no
  significa nada por sí solo;
- y **nace apagado**, siempre. Un flujo apagado es un borrador que no toca
  nada; el peor caso de una invención es algo que alguien borra en dos clics.
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


@registrar("crear_automatizacion")
def crear_automatizacion(accion, usuario, contexto=None):  # noqa: ARG001
    """Crea una automatización NUEVA, siempre apagada.

    Dos caminos, y el primero es el que sirve:

    - **Con receta** (`plantilla`): la forma de los nodos ya está verificada y
      sólo se rellenan los huecos. Es lo que hay que preferir.
    - **Libre** (`nodos`): el grafo que armó El Chalán. Se crea, se revisa y el
      resumen dice qué no se reconoció — porque n8n acepta un nodo inexistente
      sin quejarse, y reportar éxito a secas sería mentir.

    En los dos casos queda **apagada**: prenderla es otra acción, que también
    pasa por confirmación humana.
    """
    from lib import n8n_plantillas

    _gate(usuario, "puede_acceder_ajustes", "crear automatizaciones")
    n8n = _exigir_llave()

    payload = accion.payload if hasattr(accion, "payload") else (accion or {})
    nombre = str(payload.get("nombre") or "").strip()
    if not nombre:
        raise ValueError("Falta el nombre de la automatización.")

    plantilla = str(payload.get("plantilla") or "").strip()
    if plantilla:
        nodos, conexiones = n8n_plantillas.armar(plantilla,
                                                 payload.get("params") or {})
        receta = n8n_plantillas.PLANTILLAS[plantilla]
        pendiente = receta["falta_a_mano"]
    else:
        nodos = payload.get("nodos") or []
        conexiones = payload.get("conexiones") or {}
        if not isinstance(nodos, list) or not nodos:
            recetas = ", ".join(sorted(n8n_plantillas.PLANTILLAS))
            raise ValueError(
                "Para crear una automatización hace falta una receta "
                f"({recetas}) o la lista de pasos."
            )
        pendiente = ""

    avisos = n8n_plantillas.revisar(nodos, conexiones)

    creado = n8n.crear(nombre, nodos, conexiones)
    if not creado:
        raise ValueError(f"n8n no pudo crear «{nombre}».")

    # Se lee de vuelta para contar lo que REALMENTE quedó guardado, no lo que
    # se mandó. Si n8n se comió un nodo, el resumen lo dice.
    guardado = n8n.detalle_flujo(creado["id"]) or creado
    partes = [f"Automatización «{nombre}» creada con {guardado.get('pasos', len(nodos))} "
              f"paso(s), y queda APAGADA."]
    if pendiente:
        partes.append(f"Falta a mano en n8n: {pendiente}")
    if avisos:
        partes.append("Ojo: " + " ".join(avisos))
    partes.append("Revísala en n8n y préndela desde ahí (o pídemelo).")

    return {"entidad_tipo": "automatizacion", "entidad_id": creado["id"],
            "resumen": " ".join(partes)}
