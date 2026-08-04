"""Cómo se VE una acción de El Chalán en el chat (LC 2026-08-04).

Oscar: «las respuestas deben de ser más cortas, visuales, intuitivas, claras»
y «al hacer una acción, la respuesta debe regresar también un botón a la página
más probable de visitar tras hacerla».

En vez de pedirle al LLM que redacte bonito (y esperar que obedezca), la tarjeta
de la acción se arma **con datos**: una pastilla con el nombre de la acción y sus
campos como pares `Etiqueta: valor`. Sale igual siempre, en el idioma correcto y
sin gastar tokens. El botón de destino sale de `DictadoAccion.entidad_tipo/
entidad_id`, que los ejecutores ya escriben al aplicar — así que no hace falta
ningún campo nuevo (cero migración).

Todo es defensivo: un payload raro o un urlconf que no expone una ruta nunca
tumban el chat, simplemente muestran menos.
"""

from __future__ import annotations

from lib.dictado_catalogo import COMANDOS_DICTADO

# ── Pastilla (badge) ──────────────────────────────────────────────────────────
# El título humano de cada acción ya vive en el catálogo (fuente única).
_TITULOS: dict[str, str] = {c["tipo"]: c.get("titulo") or c["tipo"] for c in COMANDOS_DICTADO}


def titulo_accion(tipo: str) -> str:
    """«crear_proyecto» → «Crear proyecto». Si el tipo no está en el catálogo,
    se humaniza el slug para no mostrar guiones bajos."""
    tipo = (tipo or "").strip()
    if tipo in _TITULOS:
        return _TITULOS[tipo]
    return tipo.replace("_", " ").capitalize() if tipo else "Acción"


# ── Campos del payload ───────────────────────────────────────────────────────
# Etiquetas en español de las llaves que vale la pena mostrar. Lo que no está
# aquí no se pinta: el payload trae llaves internas que al usuario no le dicen
# nada (y algunas son largas).
_ETIQUETAS: dict[str, str] = {
    "nombre": "Nombre",
    "titulo": "Título",
    "cliente_slug": "Cliente",
    "proyecto_slug": "Proyecto",
    "razon_social": "Razón social",
    "razon_social_fiscal": "Razón social (CFDI)",
    "rfc": "RFC",
    "nombre_contacto": "Contacto",
    "email_contacto": "Correo",
    "telefono": "Teléfono",
    "direccion": "Dirección",
    "usuario_slug": "Persona",
    "asignado_slug": "Responsable",
    "rol_en_proyecto": "Rol",
    "destinatarios_slugs": "Para",
    "fecha_compromiso": "Fecha de entrega",
    "fecha_emision": "Emisión",
    "fecha_vencimiento": "Vencimiento",
    "fecha": "Fecha",
    "hora": "Hora",
    "estado": "Estado",
    "prioridad": "Prioridad",
    "tipo": "Tipo",
    "lugar": "Lugar",
    "servicio": "Producto",
    "producto": "Producto",
    "proveedor": "Proveedor",
    "cantidad": "Cantidad",
    "merma": "Merma",
    "precio_unitario": "Precio unitario",
    "costo_unitario": "Costo unitario",
    "concepto": "Concepto",
    "folio": "Folio",
    "monto": "Monto",
    "monto_total": "Total a pagar",
    "monto_base": "Subtotal",
    "monto_estimado": "Monto estimado",
    "monto_cotizado": "Cotizado",
    "centro_de_costo_slug": "Centro de costo",
    "metodo": "Método",
    "estado_pago": "Pago",
    "pagado_por_slug": "Pagó",
    "asunto": "Asunto",
    "cuerpo": "Mensaje",
    "descripcion": "Descripción",
    "nota": "Nota",
    "notas": "Notas",
    "motivo": "Motivo",
}

# Orden de lectura: lo que identifica a la entidad primero, el dinero al final.
_ORDEN = (
    "nombre", "titulo", "concepto", "asunto", "razon_social", "razon_social_fiscal",
    "servicio", "producto", "cliente_slug", "proyecto_slug", "proveedor",
    "usuario_slug", "asignado_slug", "destinatarios_slugs", "rol_en_proyecto",
    "cantidad", "merma", "tipo", "estado", "estado_pago", "prioridad", "lugar",
    "fecha_compromiso", "fecha", "hora", "fecha_emision", "fecha_vencimiento",
    "folio", "precio_unitario", "costo_unitario", "monto", "monto_base",
    "monto_total", "monto_estimado", "monto_cotizado", "centro_de_costo_slug",
    "metodo", "pagado_por_slug", "rfc", "nombre_contacto", "email_contacto",
    "telefono", "direccion", "descripcion", "cuerpo", "nota", "notas", "motivo",
)

_MAX_CAMPOS = 8          # una tarjeta no es un formulario
_MAX_VALOR = 120         # un cuerpo de recado no se lee completo en la pastilla

_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio",
          "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def _fecha_legible(valor: str) -> str:
    """«2026-08-03» → «3 de agosto de 2026». Si no parsea, se devuelve igual."""
    from datetime import date
    try:
        d = date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return str(valor)
    return f"{d.day} de {_MESES[d.month - 1]} de {d.year}"


def _valor_legible(clave: str, valor) -> str:
    """Un valor del payload como lo leería una persona."""
    if valor is None or valor == "" or valor == []:
        return ""
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, list | tuple):
        partes = [_valor_legible(clave, v) for v in valor]
        return ", ".join(p for p in partes if p)[:_MAX_VALOR]
    texto = str(valor).strip()
    if clave.startswith("fecha"):
        texto = _fecha_legible(texto)
    # Los slugs vienen con el prefijo de referencia; en la tarjeta estorba.
    while texto[:1] in ("$", "#", "@") and not texto.startswith("@accion_"):
        texto = texto[1:]
    texto = texto.replace("\n", " · ")
    return texto[:_MAX_VALOR]


def campos_accion(tipo: str, payload: dict | None) -> list[dict]:
    """`[{etiqueta, valor}]` de una acción, en orden de lectura.

    Acepta que el LLM anide los cambios en `campos` (como hacen los
    `actualizar_*`) o que los ponga al nivel superior: se aplanan ambos.
    """
    plano: dict = {}
    for clave, valor in (payload or {}).items():
        if clave == "campos" and isinstance(valor, dict):
            plano.update(valor)
        else:
            plano.setdefault(clave, valor)
    # `campos` gana sobre el nivel superior cuando la misma llave viene en los dos.
    if isinstance((payload or {}).get("campos"), dict):
        plano.update(payload["campos"])

    filas: list[dict] = []
    vistos: set[str] = set()
    for clave in _ORDEN:
        if clave in plano and clave in _ETIQUETAS:
            texto = _valor_legible(clave, plano[clave])
            if texto:
                filas.append({"etiqueta": _ETIQUETAS[clave], "valor": texto})
                vistos.add(clave)
    for clave, valor in plano.items():
        if clave in vistos or clave not in _ETIQUETAS:
            continue
        texto = _valor_legible(clave, valor)
        if texto:
            filas.append({"etiqueta": _ETIQUETAS[clave], "valor": texto})
    return filas[:_MAX_CAMPOS]


# ── Botón de destino ─────────────────────────────────────────────────────────
# `entidad_tipo` → (url_name, etiqueta, lleva_pk). Los ejecutores ya escriben
# `entidad_tipo`/`entidad_id` al aplicar, así que esto es puro mapeo.
_DESTINOS: dict[str, tuple[str, str, bool]] = {
    "proyecto": ("proyectos-detalle", "Ir al proyecto", True),
    # `asignar_usuario_proyecto` guarda el pk del PROYECTO (no de la asignación).
    "asignacion": ("proyectos-detalle", "Ir al proyecto", True),
    "cliente": ("cartera-detalle", "Ir al cliente", True),
    "tarea": ("pizarron-detalle-tarea", "Ir a la tarea", True),
    "cotizacion": ("cotizaciones:detalle", "Ir a la cotización", True),
    "factura": ("facturacion:detalle", "Ir a la factura", True),
    "ingreso": ("tesoreria:ingreso-detalle", "Ir al ingreso", True),
    "egreso": ("tesoreria:egreso-detalle", "Ir al egreso", True),
    "asiento": ("contaduria:asiento-detalle", "Ir al movimiento", True),
    "servicio": ("catalogo-editar", "Ir al producto", True),
    "proveedor": ("catalogo-proveedor-detalle", "Ir al proveedor", True),
    "buzon": ("recados:buzon_detalle", "Ir al buzón", True),
    "recado": ("recados:bandeja", "Ir a Mensajes", False),
    "jornada": ("checador:jornada_detalle", "Ir a la jornada", True),
    "visita": ("checador:visita_detalle", "Ir a la visita", True),
    "sesion_proyecto": ("checador:sesion_detalle", "Ir al registro de tiempo", True),
    "solicitud_correccion": ("checador:correcciones", "Ir a las correcciones", False),
}


def _url_de(entidad_tipo: str, entidad_id) -> tuple[str, str] | None:
    """`(url, etiqueta)` del destino de una entidad creada, o None."""
    from django.urls import NoReverseMatch, reverse
    destino = _DESTINOS.get((entidad_tipo or "").strip())
    if not destino:
        return None
    nombre, etiqueta, lleva_pk = destino
    try:
        return (reverse(nombre, args=[entidad_id]) if lleva_pk else reverse(nombre)), etiqueta
    except (NoReverseMatch, ValueError, TypeError):
        return None


def _url_indirecta(entidad_tipo: str, entidad_id) -> tuple[str, str] | None:
    """Entidades cuyo pk no tiene página propia y se llevan a su «padre».

    - `producto`: es un `ProyectoProducto` (una línea) → el PROYECTO.
    - `variacion`: no hay CRUD de variaciones desde S-Fiscal-Estructura → el
      producto del catálogo al que pertenece.
    """
    tipo = (entidad_tipo or "").strip()
    if tipo == "producto":
        from apps.los_proyectos.models import ProyectoProducto
        pp = ProyectoProducto.objects.filter(pk=entidad_id).only("proyecto_id").first()
        return _url_de("proyecto", pp.proyecto_id) if pp else None
    if tipo == "variacion":
        from apps.el_catalogo.models import Variacion
        var = Variacion.objects.filter(pk=entidad_id).only("servicio_id").first()
        return _url_de("servicio", var.servicio_id) if var else None
    return None


def enlaces_de_dictado(dictado) -> list[dict]:
    """`[{url, etiqueta}]` — un botón por entidad creada/tocada al aplicar.

    Sin repetidos (dos acciones sobre el mismo proyecto dejan un solo botón) y
    en el orden en que se aplicaron. Nunca lanza: si algo falla, la respuesta
    simplemente sale sin botones.
    """
    enlaces: list[dict] = []
    try:
        acciones = list(dictado.acciones.filter(aplicada=True).order_by("orden"))
    except Exception:  # noqa: BLE001 — sin DB no hay botones, no hay crash
        return []
    for accion in acciones:
        if not (accion.entidad_tipo and accion.entidad_id):
            continue
        try:
            par = _url_de(accion.entidad_tipo, accion.entidad_id) or \
                _url_indirecta(accion.entidad_tipo, accion.entidad_id)
        except Exception:  # noqa: BLE001 — un destino roto no tumba el chat
            par = None
        if not par:
            continue
        url, etiqueta = par
        if any(e["url"] == url for e in enlaces):
            continue
        enlaces.append({"url": url, "etiqueta": etiqueta})
    return enlaces


__all__ = ["titulo_accion", "campos_accion", "enlaces_de_dictado"]
