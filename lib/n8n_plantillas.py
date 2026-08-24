"""Recetas de las que puede partir El Chalán para armar una automatización.

**El problema que resuelven.** Un flujo de n8n es un grafo de nodos con su
forma exacta: cada nodo lleva un `type` que tiene que existir, una
`typeVersion` que tiene que ser compatible, unos `parameters` con los nombres
que ese nodo espera, y unas conexiones que se referencian **por el nombre** de
los nodos. Pedirle a un modelo que invente todo eso produce, casi siempre, un
flujo que se ve bien y no corre — y lo peor: n8n **acepta** un nodo con un
`type` inexistente y lo guarda tan campante, así que «se creó correctamente»
no significa nada.

Aquí están las tres formas que el repo de verdad necesita, con su estructura
verificada, para que armarlas sea rellenar huecos y no adivinar. El Chalán
puede además inventar un grafo libre —Oscar quiso probarlo— pero eso pasa por
`revisar()`, que avisa de lo que no reconoce.

**Los tres guardrails que hacen esto seguro de intentar:**

1. **Nace apagado, siempre** (`n8n.crear`). Un flujo activo le manda correos a
   clientes; uno apagado es un borrador que no toca nada.
2. **Nada se crea sin que un humano confirme** (§20): El Chalán propone, la
   pantalla muestra qué va a hacer, y hasta entonces no existe.
3. **Se revisa y se dice la verdad.** Si usó un nodo que no conocemos, el
   resumen lo dice en vez de reportar éxito.

Con eso, el peor caso de un flujo inventado es un borrador apagado y roto que
alguien borra en dos clics. Verificado contra n8n **1.70.1** (el del NUC).
"""

from __future__ import annotations

#: Nodos que sabemos que existen en n8n base, con la versión que trae el 1.70.
#: No es exhaustivo: es la lista de lo que este repo usa y puede prometer. Un
#: tipo fuera de aquí no se rechaza —n8n puede tenerlo— pero se avisa.
TIPOS_CONOCIDOS: dict[str, tuple[float, str]] = {
    "n8n-nodes-base.scheduleTrigger": (1.2, "Arranca solo a una hora"),
    "n8n-nodes-base.emailReadImap": (2, "Lee un buzón de correo"),
    "n8n-nodes-base.webhook": (2, "Espera a que alguien lo llame"),
    "n8n-nodes-base.httpRequest": (4.2, "Llama a una dirección"),
    "n8n-nodes-base.if": (2.2, "Se parte en dos caminos según una condición"),
    "n8n-nodes-base.set": (3.4, "Arma o cambia los datos que pasan"),
    "n8n-nodes-base.code": (2, "Corre un pedazo de JavaScript"),
    "n8n-nodes-base.noOp": (1, "No hace nada (cierra una rama)"),
    "n8n-nodes-base.emailSend": (2.1, "Manda un correo"),
    "n8n-nodes-base.merge": (3, "Junta dos caminos"),
    "n8n-nodes-base.splitInBatches": (3, "Procesa de a poco"),
}

#: A dónde le habla n8n cuando llama a El Despacho: por la red interna de
#: Docker, con el nombre del servicio. NO la del tailnet — desde dentro del
#: contenedor esa dirección da la vuelta por la red para volver al mismo lugar.
DESTINO_TALLER = "http://el-taller:8000"


def _nodo(nombre: str, tipo: str, parametros: dict, x: int, y: int = 300) -> dict:
    """Un nodo con la forma que espera n8n. La `typeVersion` sale del catálogo.

    Se toma de `TIPOS_CONOCIDOS` y no del modelo a propósito: una versión más
    alta que la instalada deja el nodo roto en el editor, y ése es justo el
    error que nadie nota hasta que el flujo no corre.
    """
    version = TIPOS_CONOCIDOS.get(tipo, (1, ""))[0]
    return {
        "name": nombre,
        "type": tipo,
        "typeVersion": version,
        "position": [x, y],
        "parameters": parametros,
    }


def _en_cadena(nodos: list[dict]) -> dict:
    """Conecta los nodos en fila, cada uno con el siguiente.

    Las conexiones de n8n se refieren a los nodos **por su nombre**, así que
    renombrar un nodo sin tocar esto rompe el flujo en silencio. Armarlas aquí
    a partir de la propia lista evita que se desincronicen.
    """
    conexiones: dict = {}
    for actual, siguiente in zip(nodos, nodos[1:], strict=False):
        conexiones[actual["name"]] = {
            "main": [[{"node": siguiente["name"], "type": "main", "index": 0}]]
        }
    return conexiones


# ── Las recetas ─────────────────────────────────────────────────────────────


def _buzon_a_despacho(p: dict) -> tuple[list[dict], dict]:
    """Lee un buzón y empuja cada adjunto a El Despacho.

    Es el patrón de la receta de CFDI, y el mismo sirve para el papeleo: sólo
    cambian la ruta y el token. Las credenciales del correo NO van aquí — se
    eligen en n8n, que es donde viven cifradas.
    """
    ruta = str(p.get("ruta") or "/papeleo/entra").strip()
    cabecera = str(p.get("cabecera_token") or "x-papeleo-token").strip()
    token = str(p.get("token") or "").strip()

    leer = _nodo("Leer el buzón", "n8n-nodes-base.emailReadImap", {
        "format": "resolved",
        "options": {"customEmailConfig": '["UNSEEN"]'},
    }, x=0)
    empujar = _nodo("Mandar a El Despacho", "n8n-nodes-base.httpRequest", {
        "method": "POST",
        "url": f"{DESTINO_TALLER}{ruta}",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": cabecera, "value": token or "PEGA-AQUÍ-EL-TOKEN"},
        ]},
        "sendBody": True,
        "contentType": "multipart-form-data",
        "bodyParameters": {"parameters": [
            {"parameterType": "formBinaryData", "name": "archivo",
             "inputDataFieldName": "attachment_0"},
        ]},
        "options": {},
    }, x=240)
    nodos = [leer, empujar]
    return nodos, _en_cadena(nodos)


def _programado_a_despacho(p: dict) -> tuple[list[dict], dict]:
    """A una hora fija, llama a una dirección de El Despacho."""
    hora = int(p.get("hora") or 7)
    minuto = int(p.get("minuto") or 0)
    ruta = str(p.get("ruta") or "/").strip()

    reloj = _nodo("Cada día", "n8n-nodes-base.scheduleTrigger", {
        "rule": {"interval": [{"field": "days", "triggerAtHour": hora,
                               "triggerAtMinute": minuto}]},
    }, x=0)
    llamar = _nodo("Llamar a El Despacho", "n8n-nodes-base.httpRequest", {
        "method": "GET",
        "url": f"{DESTINO_TALLER}{ruta}",
        "options": {},
    }, x=240)
    nodos = [reloj, llamar]
    return nodos, _en_cadena(nodos)


def _webhook_a_despacho(p: dict) -> tuple[list[dict], dict]:
    """Recibe una llamada de afuera y la reenvía a El Despacho."""
    camino = str(p.get("camino") or "entrada").strip().strip("/")
    ruta = str(p.get("ruta") or "/").strip()

    entrada = _nodo("Cuando llamen", "n8n-nodes-base.webhook", {
        "httpMethod": "POST",
        "path": camino,
        "options": {},
    }, x=0)
    reenviar = _nodo("Pasar a El Despacho", "n8n-nodes-base.httpRequest", {
        "method": "POST",
        "url": f"{DESTINO_TALLER}{ruta}",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify($json) }}",
        "options": {},
    }, x=240)
    nodos = [entrada, reenviar]
    return nodos, _en_cadena(nodos)


PLANTILLAS: dict[str, dict] = {
    "buzon_a_despacho": {
        "titulo": "Buzón de correo → El Despacho",
        "para_que": (
            "Vigila un buzón y manda cada adjunto a El Despacho. Es como entran "
            "los CFDI de facturas y el papeleo (contratos, remisiones)."
        ),
        "parametros": {
            "ruta": "A dónde se manda dentro de El Despacho. Default /papeleo/entra.",
            "cabecera_token": "Nombre de la cabecera del token. Default x-papeleo-token.",
            "token": "El token de entrada. Si se omite queda un hueco para pegarlo en n8n.",
        },
        "armar": _buzon_a_despacho,
        "falta_a_mano": "Elegir la cuenta de correo (las credenciales viven en n8n).",
    },
    "programado_a_despacho": {
        "titulo": "A una hora fija → El Despacho",
        "para_que": "Llama a una dirección de El Despacho todos los días a una hora.",
        "parametros": {
            "hora": "Hora del día, 0-23. Default 7.",
            "minuto": "Minuto. Default 0.",
            "ruta": "Qué dirección de El Despacho llamar.",
        },
        "armar": _programado_a_despacho,
        "falta_a_mano": "",
    },
    "webhook_a_despacho": {
        "titulo": "Alguien llama a n8n → El Despacho",
        "para_que": (
            "Da una dirección pública a la que otro sistema puede llamar, y lo "
            "que llegue se reenvía a El Despacho."
        ),
        "parametros": {
            "camino": "El pedazo final de la dirección que queda escuchando.",
            "ruta": "Qué dirección de El Despacho recibe lo que llegue.",
        },
        "armar": _webhook_a_despacho,
        "falta_a_mano": "",
    },
}


def catalogo() -> list[dict]:
    """Las recetas, para enseñárselas al Chalán o pintarlas en una pantalla."""
    return [{"plantilla": k, "titulo": v["titulo"], "para_que": v["para_que"],
             "parametros": v["parametros"], "falta_a_mano": v["falta_a_mano"]}
            for k, v in PLANTILLAS.items()]


def armar(plantilla: str, parametros: dict | None = None) -> tuple[list[dict], dict]:
    """(nodos, conexiones) de una receta. Lanza si la receta no existe."""
    receta = PLANTILLAS.get(str(plantilla or "").strip())
    if receta is None:
        conocidas = ", ".join(sorted(PLANTILLAS))
        raise ValueError(
            f"No hay una receta llamada «{plantilla}». Las que hay: {conocidas}."
        )
    return receta["armar"](parametros or {})


def revisar(nodos: list, conexiones: dict | None = None) -> list[str]:
    """Qué tiene de sospechoso un grafo. Lista vacía = se ve bien.

    Existe porque n8n **guarda sin quejarse** un nodo cuyo `type` no existe: se
    crea «con éxito» y aparece roto en el editor. Revisar aquí es la diferencia
    entre avisar y mentir.
    """
    avisos: list[str] = []
    if not isinstance(nodos, list) or not nodos:
        return ["El flujo no tiene nodos: así no hace nada."]

    nombres = []
    for i, n in enumerate(nodos, 1):
        if not isinstance(n, dict):
            avisos.append(f"El paso {i} no tiene forma de nodo.")
            continue
        nombre = str(n.get("name") or "").strip()
        tipo = str(n.get("type") or "").strip()
        if not nombre:
            avisos.append(f"El paso {i} no tiene nombre, y las conexiones se "
                          "hacen por nombre.")
        if nombre in nombres:
            avisos.append(f"Hay dos pasos llamados «{nombre}»; n8n los va a "
                          "confundir al conectarlos.")
        nombres.append(nombre)
        if not tipo:
            avisos.append(f"«{nombre or i}» no dice qué clase de paso es.")
        elif tipo not in TIPOS_CONOCIDOS:
            avisos.append(f"«{nombre or i}» usa un paso que no conozco "
                          f"({tipo}); revísalo en n8n antes de prenderlo.")

    # Un flujo sin disparador no arranca nunca: se queda esperando a que alguien
    # lo corra a mano, que casi nunca es lo que se pidió.
    disparadores = ("scheduleTrigger", "webhook", "emailReadImap")
    if not any(any(d in str(n.get("type", "")) for d in disparadores)
               for n in nodos if isinstance(n, dict)):
        avisos.append("Ningún paso lo hace arrancar solo: va a quedarse "
                      "esperando a que alguien lo corra a mano.")

    if len(nodos) > 1 and not conexiones:
        avisos.append("Los pasos no están conectados entre sí, así que sólo "
                      "correría el primero.")

    return avisos


__all__ = [
    "DESTINO_TALLER",
    "PLANTILLAS",
    "TIPOS_CONOCIDOS",
    "armar",
    "catalogo",
    "revisar",
]
