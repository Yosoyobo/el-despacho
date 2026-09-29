"""Los 8 comandos de la rama de julio, rehechos sobre el código de hoy
(sprint de pendientes, 2026-09-28).

El commit `36317d44` (rama `agent/mcp-despacho`, 2026-07-16) traía las Olas 2 y
3 del barrido CUI y nunca se mergeó: chocaba con todo lo que main cambió
después. Oscar decidió **rehacerlos sobre main**, no mergear la rama vieja.

Cierran lo que ya se hace con clicks pero todavía no por conversación:

* **Facturación** — facturar una cotización, cancelar, duplicar y ligar una
  factura a un proyecto.
* **Anular** del ciclo comercial-contable — cotización y movimiento contable.
* **Editar** del Catálogo — proveedor y variación (los `crear_*` ya existían).

Mismo contrato que `avanzados.py`/`cui_v1.py`: `(accion, usuario, contexto)`,
lanza `ValueError` si el payload es inválido, la entidad no existe o el usuario
no tiene permiso. El permiso se RE-CHEQUEA aquí aunque el catálogo ya filtre lo
que el Chalán puede proponer (defensa en profundidad, §4 #20), y con la MISMA
acción que pide la pantalla: lo que no se puede con clicks no se puede dictando.
Nada se aplica sin la confirmación humana de `services.aplicar` (§20).

Reglas de negocio que se conservan:

* Una factura con cobros NO se cancela por dictado (`cancelar_factura_cobrada`
  sigue prohibido): el error dice qué ingresos hay que anular primero.
* Borrar sigue fuera: anular y editar dejan rastro, borrar no.
* Editar el Catálogo es por lista blanca de campos, como `actualizar_servicio`
  (`modificar_catalogo` genérico sigue prohibido).
* Un movimiento contable que generó el sistema no se anula a mano: se corrige
  desde su documento de origen, o la contabilidad se descuadra en silencio (el
  reverso automático busca el asiento original VIGENTE y ya no lo encontraría).
"""

from __future__ import annotations

import contextlib
from decimal import Decimal, InvalidOperation

from . import _gate, registrar
from .avanzados import _cotizacion_por_codigo, _exigir, _factura_por_codigo
from .basicos import _limpiar_slug, _ref_anterior, _resolver_proyecto
from .catalogo import _emitir, _resolver_servicio

# ── Helpers ──────────────────────────────────────────────────────────────────

def _motivo(payload: dict, que: str) -> str:
    motivo = (payload.get("motivo") or "").strip()
    _exigir(bool(motivo), f"Dime el motivo para {que} (`motivo`).")
    return motivo


def _pesos(valor) -> str:
    from cuentas.templatetags.forms_helpers import dinero
    return dinero(valor)


def _decimal_no_negativo(valor, clave: str) -> Decimal:
    try:
        d = Decimal(str(valor)).quantize(Decimal("0.01"))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError(f"`{clave}` inválido: {valor}") from exc
    _exigir(d >= 0, f"`{clave}` no puede ser negativo.")
    return d


def _asiento_por_codigo(codigo):
    from apps.contaduria.models import Asiento
    codigo = (codigo or "").strip().upper()
    _exigir(bool(codigo), "Falta `codigo` del movimiento contable (AST-AAAA-NNNN).")
    asiento = Asiento.objects.filter(codigo__iexact=codigo).first()
    _exigir(asiento is not None, f"Movimiento contable `{codigo}` no encontrado.")
    return asiento


def _documento_de_origen(asiento) -> str:
    """«el ingreso ING-2026-0012» a partir de `referencia_externa`
    (`tesoreria.ingreso:42`, `tesoreria.egreso.reembolso:17`,
    `facturacion.factura:5`…). Vacío si no se puede saber."""
    ref = (asiento.referencia_externa or "").strip()
    if ":" not in ref:
        return ""
    prefijo, _, pk = ref.partition(":")
    partes = prefijo.split(".")
    if len(partes) < 2 or not pk.isdigit():
        return ""
    app, modelo = partes[0], partes[1]
    with contextlib.suppress(Exception):
        if (app, modelo) == ("tesoreria", "ingreso"):
            from apps.tesoreria.models import Ingreso
            obj = Ingreso.objects.filter(pk=int(pk)).only("codigo").first()
            return f"el ingreso {obj.codigo}" if obj else ""
        if (app, modelo) == ("tesoreria", "egreso"):
            from apps.tesoreria.models import Egreso
            obj = Egreso.objects.filter(pk=int(pk)).only("codigo").first()
            return f"el egreso {obj.codigo}" if obj else ""
        if (app, modelo) == ("facturacion", "factura"):
            from apps.facturacion.models import Factura
            obj = Factura.objects.filter(pk=int(pk)).first()
            return f"la factura {obj.folio_display}" if obj else ""
    return ""


def _proveedor(clave, contexto=None):
    """Proveedor por `@accion_N` (creado en el mismo dictado), id, razón social
    exacta o parte INEQUÍVOCA de ella. Dos candidatos no se adivinan."""
    from apps.el_catalogo.models import Proveedor
    clave = _limpiar_slug(str(clave or "").strip())
    _exigir(bool(clave), "Falta el proveedor (`proveedor`: su nombre).")
    ref_id = _ref_anterior(clave, contexto, "proveedor")
    if ref_id:
        prov = Proveedor.objects.filter(pk=ref_id).first()
        if prov:
            return prov
    if clave.isdigit():
        prov = Proveedor.objects.filter(pk=int(clave)).first()
        if prov:
            return prov
    exacto = Proveedor.objects.filter(razon_social__iexact=clave)
    prov = exacto.filter(activo=True).first() or exacto.first()
    if prov:
        return prov
    parecidos = list(
        Proveedor.objects.filter(activo=True, razon_social__icontains=clave)[:4]
    )
    _exigir(bool(parecidos), f"Proveedor `{clave}` no encontrado.")
    _exigir(
        len(parecidos) == 1,
        f"Varios proveedores coinciden con `{clave}` "
        f"({', '.join(p.razon_social for p in parecidos)}). Dime cuál.",
    )
    return parecidos[0]


def _variacion(payload: dict, contexto=None):
    """Variación por `variacion_id`, o por `servicio` + nombre de la variación
    (exacto primero, parcial sólo si es inequívoco)."""
    from apps.el_catalogo.models import Variacion
    vid = payload.get("variacion_id")
    if vid not in (None, ""):
        var = None
        with contextlib.suppress(TypeError, ValueError):
            var = Variacion.objects.filter(pk=int(vid)).first()
        _exigir(var is not None, f"Variación `{vid}` no encontrada.")
        return var
    servicio = _resolver_servicio(payload.get("servicio") or "", contexto)
    nombre = _limpiar_slug(str(payload.get("variacion") or "").strip())
    _exigir(bool(nombre), "Indica `variacion_id` o el producto (`servicio`) y la `variacion`.")
    qs = Variacion.objects.filter(servicio=servicio)
    var = qs.filter(nombre__iexact=nombre).first()
    if var:
        return var
    parecidas = list(qs.filter(nombre__icontains=nombre)[:4])
    _exigir(bool(parecidas), f"«{servicio.nombre}» no tiene la variación `{nombre}`.")
    _exigir(
        len(parecidas) == 1,
        f"Varias variaciones de «{servicio.nombre}» coinciden con `{nombre}` "
        f"({', '.join(v.nombre for v in parecidas)}). Dime cuál.",
    )
    return parecidas[0]


# ── Facturación ──────────────────────────────────────────────────────────────

@registrar("crear_factura_desde_cotizacion")
def crear_factura_desde_cotizacion(accion, usuario, contexto=None):
    """Payload: codigo (de la cotización, COT-AAAA-NNNN). Clona sus líneas e
    impuestos en una factura BORRADOR — no la emite y NO es un CFDI (§16)."""
    _gate(usuario, "puede_crear_facturacion", "crear facturas")
    from apps.facturacion.services import crear_desde_cotizacion

    cot = _cotizacion_por_codigo((accion.payload or {}).get("codigo"))
    _exigir(cot.estado != "anulada",
            f"La cotización {cot.codigo} está anulada; no se factura.")
    fac = crear_desde_cotizacion(cot, usuario)
    accion.entidad_tipo = "factura"
    accion.entidad_id = fac.pk


@registrar("cancelar_factura")
def cancelar_factura(accion, usuario, contexto=None):
    """Payload: codigo (FAC-… o folio F-###), motivo.

    Una factura con cobros vigentes NO se cancela por dictado
    (`cancelar_factura_cobrada` sigue prohibido): el error nombra los ingresos
    que hay que anular primero. La cancelación en cascada (anular los cobros y
    cancelar de un jalón) vive sólo en la pantalla de la factura."""
    _gate(usuario, "puede_cancelar_facturacion", "cancelar facturas")
    from apps.facturacion.services import cancelar
    from apps.tesoreria.models import Ingreso

    payload = accion.payload or {}
    fac = _factura_por_codigo(payload.get("codigo"))
    motivo = _motivo(payload, "cancelar la factura")
    cobros = list(Ingreso.vigentes.filter(factura=fac).order_by("fecha", "pk"))
    if cobros:
        lista = ", ".join(f"{c.codigo} ({_pesos(c.monto)})" for c in cobros[:5])
        extra = f" y {len(cobros) - 5} más" if len(cobros) > 5 else ""
        raise ValueError(
            f"La factura {fac.folio_display} tiene cobros registrados: {lista}{extra}. "
            "Una factura cobrada no se cancela por dictado. Primero anula esos "
            f"ingresos (pídemelo: «anula el ingreso {cobros[0].codigo}») o "
            "cancélala en cascada desde la pantalla de la factura."
        )
    cancelar(fac, usuario, motivo)
    accion.entidad_tipo = "factura"
    accion.entidad_id = fac.pk


@registrar("duplicar_factura")
def duplicar_factura(accion, usuario, contexto=None):
    """Payload: codigo (FAC-… o folio F-###). Copia en borrador con las mismas
    líneas e impuestos."""
    _gate(usuario, "puede_crear_facturacion", "duplicar facturas")
    from apps.facturacion.services import duplicar

    fac = _factura_por_codigo((accion.payload or {}).get("codigo"))
    nueva = duplicar(fac, usuario)
    accion.entidad_tipo = "factura"
    accion.entidad_id = nueva.pk


@registrar("ligar_factura_proyecto")
def ligar_factura_proyecto(accion, usuario, contexto=None):
    """Payload: codigo (FAC-… o folio F-###), proyecto_slug (slug, código
    LC-NNNN o `@accion_N`). Mismo permiso que el botón «Ligar» del proyecto."""
    _gate(usuario, "puede_crear_facturacion", "ligar facturas a proyectos")
    from apps.facturacion.services import ligar_a_proyecto

    payload = accion.payload or {}
    fac = _factura_por_codigo(payload.get("codigo"))
    proyecto = _resolver_proyecto(payload.get("proyecto_slug"), contexto)
    ligar_a_proyecto(fac, proyecto, usuario)
    accion.entidad_tipo = "factura"
    accion.entidad_id = fac.pk


# ── Anular (ciclo comercial-contable) ────────────────────────────────────────

@registrar("anular_cotizacion")
def anular_cotizacion(accion, usuario, contexto=None):
    """Payload: codigo (COT-AAAA-NNNN), motivo."""
    _gate(usuario, "puede_anular_cotizaciones", "anular cotizaciones")
    from apps.cotizaciones.services import marcar_anulada

    payload = accion.payload or {}
    cot = _cotizacion_por_codigo(payload.get("codigo"))
    marcar_anulada(cot, usuario, _motivo(payload, "anular la cotización"))
    accion.entidad_tipo = "cotizacion"
    accion.entidad_id = cot.pk


@registrar("anular_asiento")
def anular_asiento(accion, usuario, contexto=None):
    """Payload: codigo (AST-AAAA-NNNN), motivo.

    Sólo movimientos capturados a mano (manuales y ajustes). Anular NO crea un
    reverso: es para corregir capturas; para neutralizar contablemente se
    captura un ajuste. Los automáticos y los cierres se corrigen en su origen."""
    _gate(usuario, "puede_anular_contaduria", "anular movimientos contables")
    from apps.contaduria.services import anular_asiento as svc

    payload = accion.payload or {}
    asiento = _asiento_por_codigo(payload.get("codigo"))
    motivo = _motivo(payload, "anular el movimiento contable")
    if asiento.origen == "cierre":
        raise ValueError(
            f"{asiento.codigo} es el cierre de un periodo; no se anula por dictado. "
            "Si hay que reabrir el periodo, hazlo en Contaduría → Cierre de periodo."
        )
    if asiento.origen.startswith("auto_"):
        doc = _documento_de_origen(asiento)
        de_donde = f" por {doc}" if doc else ""
        raise ValueError(
            f"{asiento.codigo} lo generó el sistema{de_donde} "
            f"({asiento.get_origen_display()}). No se anula por dictado: se "
            "corrige desde el documento que lo originó (anula el ingreso o el "
            "egreso, o cancela la factura) y la contabilidad se ajusta sola."
        )
    svc(asiento, actor=usuario, motivo=motivo)
    accion.entidad_tipo = "asiento"
    accion.entidad_id = asiento.pk


# ── Editar el Catálogo (contrapartes de crear_proveedor / crear_variacion) ───

_TEXTO_PROVEEDOR = {
    "razon_social": 200, "nombre_contacto": 120, "email_contacto": 254,
    "telefono": 40, "rfc": 20,
}


@registrar("actualizar_proveedor")
def actualizar_proveedor(accion, usuario, contexto=None):
    """Payload: proveedor (su nombre actual, o @accion_N), y SÓLO lo que
    cambia: razon_social_nueva? (renombrar), nombre_contacto?, email_contacto?,
    telefono?, rfc?, direccion?, direccion_fiscal?, notas?.

    Mismo permiso que editar la ficha del proveedor en pantalla. Lista blanca
    de campos: no archiva, no borra ni toca qué surte. El pin del mapa no se
    mueve solo al cambiar la dirección: se ajusta en la ficha."""
    _gate(usuario, "puede_editar_proveedores", "editar proveedores del Catálogo")
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    from lib.sanear import sanear_contexto

    payload = accion.payload or {}
    # Como en `actualizar_factura`: los cambios pueden venir anidados en
    # `campos: {...}` o aplanados junto al `proveedor` que identifica.
    anidado = isinstance(payload.get("campos"), dict)
    campos = dict(payload["campos"]) if anidado else dict(payload)
    identificador = payload.get("proveedor") or payload.get("razon_social_actual")
    if not identificador and payload.get("razon_social"):
        # Como en `crear_proveedor`, el LLM a veces nombra al proveedor con
        # `razon_social`. Sin otro identificador, ESE es a quién se edita —
        # no un nombre nuevo (renombrar se pide con `razon_social_nueva`, o
        # con `razon_social` dentro de `campos`).
        identificador = payload["razon_social"]
        if not anidado:
            campos.pop("razon_social", None)
    if campos.get("razon_social_nueva"):
        campos["razon_social"] = campos["razon_social_nueva"]
    prov = _proveedor(identificador, contexto)

    cambios: list[str] = []
    for campo, largo in _TEXTO_PROVEEDOR.items():
        valor = campos.get(campo)
        if valor in (None, ""):
            continue
        texto = sanear_contexto(str(valor).strip())[:largo]
        if campo == "email_contacto":
            try:
                validate_email(texto)
            except ValidationError as exc:
                raise ValueError(f"`email_contacto` no es un correo válido: {texto}") from exc
        if campo == "rfc":
            texto = texto.upper()
        setattr(prov, campo, texto)
        cambios.append(campo)
    if "direccion" in campos:
        prov.direccion = sanear_contexto(str(campos.get("direccion") or "").strip())
        cambios.append("direccion")
        if prov.fiscal_igual:
            prov.direccion_fiscal = prov.direccion
            cambios.append("direccion_fiscal")
    if "direccion_fiscal" in campos and "direccion_fiscal" not in cambios:
        prov.direccion_fiscal = sanear_contexto(str(campos.get("direccion_fiscal") or "").strip())
        prov.fiscal_igual = prov.direccion_fiscal == prov.direccion
        cambios += ["direccion_fiscal", "fiscal_igual"]
    if "notas" in campos:
        prov.notas = sanear_contexto(str(campos.get("notas") or ""))
        cambios.append("notas")

    _exigir(bool(cambios), "No me dijiste qué cambiar del proveedor (teléfono, correo, dirección…).")
    prov.save(update_fields=[*dict.fromkeys(cambios), "actualizado_en"])
    accion.entidad_tipo = "proveedor"
    accion.entidad_id = prov.pk
    _emitir("proveedor.actualizado", usuario,
            {"proveedor_id": prov.pk, "cambios": list(dict.fromkeys(cambios)), "origen": "chalan"})


@registrar("actualizar_variacion")
def actualizar_variacion(accion, usuario, contexto=None):
    """Payload: variacion_id | (servicio + variacion), y SÓLO lo que cambia:
    nombre_nuevo?, costo?, impresion_activa?, impresion_costo?,
    impresion_descripcion?, descripcion?, disponible?.

    Mismo permiso que editar el producto (`catalogo.editar`). Lista blanca de
    campos; `disponible: false` la oculta, no la borra."""
    _gate(usuario, "puede_editar_catalogo", "editar variaciones del Catálogo")
    payload = accion.payload or {}
    var = _variacion(payload, contexto)

    cambios: list[str] = []
    if payload.get("nombre_nuevo"):
        var.nombre = str(payload["nombre_nuevo"]).strip()[:150]
        cambios.append("nombre")
    if payload.get("costo") not in (None, ""):
        var.costo = _decimal_no_negativo(payload["costo"], "costo")
        cambios.append("costo")
    if "impresion_activa" in payload:
        var.impresion_activa = bool(payload["impresion_activa"])
        cambios.append("impresion_activa")
    if payload.get("impresion_costo") not in (None, ""):
        var.impresion_costo = _decimal_no_negativo(payload["impresion_costo"], "impresion_costo")
        cambios.append("impresion_costo")
    if "impresion_descripcion" in payload:
        var.impresion_descripcion = str(payload.get("impresion_descripcion") or "")[:250]
        cambios.append("impresion_descripcion")
    if "descripcion" in payload:
        var.descripcion = str(payload.get("descripcion") or "")[:500]
        cambios.append("descripcion")
    if "disponible" in payload:
        var.disponible = bool(payload["disponible"])
        cambios.append("disponible")

    _exigir(bool(cambios), "No me dijiste qué cambiar de la variación (costo, nombre…).")
    var.save(update_fields=[*cambios, "actualizado_en"])
    accion.entidad_tipo = "variacion"
    accion.entidad_id = var.pk
    _emitir("catalogo.variacion_actualizada", usuario,
            {"variacion_id": var.pk, "servicio_id": var.servicio_id, "cambios": cambios})
