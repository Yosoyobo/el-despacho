"""Edición (sobreescritura) de documentos de dinero — ingresos, egresos y
facturas (LC 2026-07-25, pedido de Oscar: «El Chalán debe poder editar,
agregar y sobreescribir facturas, ingresos y egresos»).

Lo de **agregar** ya existía (`registrar_ingreso`, `registrar_egreso`,
`crear_factura`); esto cierra el **editar/sobreescribir**.

Mismo contrato que `basicos.py`/`avanzados.py`: `(accion, usuario, contexto)`,
lanza `ValueError` si el payload es inválido, la entidad no existe o el usuario
no tiene permiso (defensa en profundidad — el catálogo ya filtra el prompt por
rol, aquí se re-chequea antes de tocar la DB). Nada se aplica sin la
confirmación humana que garantiza `services.aplicar` (regla §20).

Reglas de negocio:

* Un ingreso/egreso **anulado** no se edita (se captura otro).
* **El MONTO de un ingreso/egreso NO se puede cambiar** (decisión Oscar
  2026-07-25). Los asientos automáticos de Contaduría se generan al CREAR y al
  ANULAR el movimiento; editar el importe después dejaría la contabilidad
  descuadrada en silencio. Si el monto está mal: se anula y se captura de nuevo
  (así el reverso contable queda registrado). El ejecutor rechaza el intento con
  ese mensaje, en vez de aceptarlo a medias.
* Una factura solo se edita en **borrador** (`es_editable`): ya emitida, el
  documento es testimonio de lo que se mandó. Ahí el `monto` SÍ se puede fijar
  —vía `services.fijar_linea_concepto`, que deja UNA línea-concepto (modo
  «monto» de LC 2026-07)— porque el asiento de la factura nace al **emitir**,
  no al capturarla.
"""

from __future__ import annotations

from datetime import date as _date

from . import _gate, registrar
from .avanzados import (
    _egreso_por_codigo,
    _exigir,
    _factura_por_codigo,
    _ingreso_por_codigo,
    _monto,
)
from .basicos import _resolver_cliente, _resolver_proyecto, _resolver_usuario


def _campos(payload: dict) -> dict:
    """El LLM manda los cambios como `campos: {...}` (igual que
    `actualizar_proyecto`), pero a veces los aplana en el payload. Aceptamos
    ambas formas."""
    campos = payload.get("campos")
    return campos if isinstance(campos, dict) and campos else payload


def _fecha_valida(valor, etiqueta: str):
    try:
        return _date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"`{etiqueta}` inválida: {valor}") from exc


def _texto(campos: dict, clave: str, limite: int):
    """Texto saneado y recortado, o None si no viene en el payload."""
    if clave not in campos:
        return None
    from lib.sanear import sanear_contexto
    return sanear_contexto(str(campos.get(clave) or "").strip())[:limite]


def _prohibir_monto(campos: dict, entidad: str, codigo: str) -> None:
    """El importe de un movimiento ya capturado no se toca (ver el módulo): su
    asiento contable no se reajusta, así que se anula y se captura de nuevo."""
    if campos.get("monto") not in (None, ""):
        raise ValueError(
            f"El monto de un {entidad} no se puede cambiar: su asiento contable "
            f"ya está registrado. Anula {codigo} y captura el movimiento con el "
            f"importe correcto."
        )


# ── Tesorería ────────────────────────────────────────────────────────────────

@registrar("actualizar_ingreso")
def actualizar_ingreso(accion, usuario, contexto=None):
    """Payload: codigo, campos: {descripcion?, fecha?, metodo?, cliente_slug?,
    proyecto_slug?}. El **monto NO se puede cambiar** (ver el módulo)."""
    _gate(usuario, "puede_ver_finanzas", "editar ingresos")
    from apps.tesoreria.models import METODOS_INGRESO

    payload = accion.payload or {}
    ingreso = _ingreso_por_codigo(payload.get("codigo"))
    _exigir(not ingreso.anulado,
            f"El ingreso {ingreso.codigo} está anulado; captura uno nuevo.")

    campos = _campos(payload)
    _prohibir_monto(campos, "ingreso", ingreso.codigo)
    cambios: list[str] = []

    if (desc := _texto(campos, "descripcion", 300)) is not None:
        ingreso.descripcion = desc
        cambios.append("descripcion")
    if campos.get("fecha"):
        ingreso.fecha = _fecha_valida(campos["fecha"], "fecha")
        cambios.append("fecha")
    if campos.get("metodo"):
        metodo = str(campos["metodo"]).lower()
        _exigir(metodo in dict(METODOS_INGRESO), f"Método `{metodo}` no válido.")
        ingreso.metodo = metodo
        cambios.append("metodo")
    if campos.get("cliente_slug"):
        ingreso.cliente = _resolver_cliente(str(campos["cliente_slug"]).lower(), contexto)
        cambios.append("cliente")
    if campos.get("proyecto_slug"):
        ingreso.proyecto = _resolver_proyecto(campos["proyecto_slug"], contexto)
        cambios.append("proyecto")

    _exigir(bool(cambios), "No mandaste ningún campo a cambiar del ingreso.")
    ingreso.save()
    accion.entidad_tipo = "ingreso"
    accion.entidad_id = ingreso.pk


@registrar("actualizar_egreso")
def actualizar_egreso(accion, usuario, contexto=None):
    """Payload: codigo, campos: {descripcion?, fecha?, metodo?, estado_pago?,
    centro_de_costo_slug?, proveedor?, proyecto_slug?, solicitado_por_slug?}.
    El **monto NO se puede cambiar** (ver el módulo)."""
    _gate(usuario, "puede_ver_finanzas", "editar egresos")
    from apps.tesoreria.models import METODOS_EGRESO, CentroDeCosto

    payload = accion.payload or {}
    egreso = _egreso_por_codigo(payload.get("codigo"))
    _exigir(not egreso.anulado,
            f"El egreso {egreso.codigo} está anulado; captura uno nuevo.")

    campos = _campos(payload)
    _prohibir_monto(campos, "egreso", egreso.codigo)
    cambios: list[str] = []

    if (desc := _texto(campos, "descripcion", 300)) is not None:
        egreso.descripcion = desc
        cambios.append("descripcion")
    if campos.get("fecha"):
        egreso.fecha = _fecha_valida(campos["fecha"], "fecha")
        cambios.append("fecha")
    if campos.get("metodo"):
        metodo = str(campos["metodo"]).lower()
        _exigir(metodo in dict(METODOS_EGRESO), f"Método `{metodo}` no válido.")
        egreso.metodo = metodo
        cambios.append("metodo")
    if campos.get("estado_pago"):
        estado = str(campos["estado_pago"]).lower()
        _exigir(estado in {"pagado", "por_reembolsar", "pendiente"},
                "`estado_pago` debe ser pagado, por_reembolsar o pendiente.")
        egreso.estado_pago = estado
        cambios.append("estado_pago")
    if campos.get("centro_de_costo_slug"):
        slug = str(campos["centro_de_costo_slug"]).lower()
        centro = CentroDeCosto.objects.filter(slug=slug, activo=True).first()
        _exigir(centro is not None, f"Centro de costo `{slug}` no encontrado.")
        egreso.centro_de_costo = centro
        cambios.append("centro_de_costo")
    if campos.get("proveedor"):
        from .checador import _resolver_proveedor
        proveedor = _resolver_proveedor(str(campos["proveedor"]))
        egreso.proveedor = proveedor
        egreso.proveedor_nombre = proveedor.razon_social[:200]
        cambios.append("proveedor")
    if campos.get("proyecto_slug"):
        egreso.proyecto = _resolver_proyecto(campos["proyecto_slug"], contexto)
        cambios.append("proyecto")
    if campos.get("solicitado_por_slug"):
        egreso.solicitado_por = _resolver_usuario(
            str(campos["solicitado_por_slug"]).lower(), contexto)
        cambios.append("solicitado_por")

    _exigir(bool(cambios), "No mandaste ningún campo a cambiar del egreso.")
    egreso.save()
    accion.entidad_tipo = "egreso"
    accion.entidad_id = egreso.pk


# ── Facturación ──────────────────────────────────────────────────────────────

@registrar("actualizar_factura")
def actualizar_factura(accion, usuario, contexto=None):
    """Payload: codigo (FAC-… o folio), campos: {concepto?, monto? |
    monto_base?, fecha_emision?, fecha_vencimiento?, porcentaje_a_facturar?,
    descuento_global_porcentaje?, notas?, terminos?, cliente_slug?,
    proyecto_slug?}.

    Solo en borrador. Cualquiera de los dos montos REEMPLAZA las líneas por una
    línea-concepto (modo «monto» del form, decisión Oscar LC 2026-07):
    `monto` es el importe FINAL con impuestos (se despeja la base) y
    `monto_base` el importe antes de impuestos.
    """
    _gate(usuario, "puede_editar_facturacion", "editar facturas")
    from decimal import Decimal, InvalidOperation

    from apps.facturacion import services as fac_services

    payload = accion.payload or {}
    factura = _factura_por_codigo(payload.get("codigo"))
    _exigir(factura.es_editable,
            f"La factura {factura.folio_display} ya no es editable "
            f"(está en «{factura.get_estado_display()}»).")

    campos = _campos(payload)
    cambios: list[str] = []

    if (concepto := _texto(campos, "concepto", 200)) is not None:
        factura.concepto = concepto
        cambios.append("concepto")
    if campos.get("fecha_emision"):
        factura.fecha_emision = _fecha_valida(campos["fecha_emision"], "fecha_emision")
        cambios.append("fecha_emision")
    if campos.get("fecha_vencimiento"):
        factura.fecha_vencimiento = _fecha_valida(
            campos["fecha_vencimiento"], "fecha_vencimiento")
        cambios.append("fecha_vencimiento")
    for clave in ("porcentaje_a_facturar", "descuento_global_porcentaje"):
        if campos.get(clave) in (None, ""):
            continue
        try:
            valor = Decimal(str(campos[clave])).quantize(Decimal("0.01"))
        except (TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"`{clave}` inválido: {campos[clave]}") from exc
        _exigir(Decimal("0") <= valor <= Decimal("100"),
                f"`{clave}` debe estar entre 0 y 100.")
        setattr(factura, clave, valor)
        cambios.append(clave)
    if (notas := _texto(campos, "notas", 2000)) is not None:
        factura.notas = notas
        cambios.append("notas")
    if (terminos := _texto(campos, "terminos", 2000)) is not None:
        factura.terminos = terminos
        cambios.append("terminos")
    if campos.get("cliente_slug"):
        factura.cliente = _resolver_cliente(str(campos["cliente_slug"]).lower(), contexto)
        cambios.append("cliente")
    if campos.get("proyecto_slug"):
        factura.proyecto = _resolver_proyecto(campos["proyecto_slug"], contexto)
        cambios.append("proyecto")

    # Una sola cifra dictada = importe FINAL de pago; solo `monto_base` es la
    # base a la que se le suman los impuestos (Oscar 2026-07-25).
    total = campos.get("monto_total")
    if total in (None, ""):
        total = campos.get("monto")
    base = campos.get("monto_base")
    if base not in (None, ""):
        factura.save()  # el monto se resuelve contra la factura ya actualizada
        fac_services.fijar_linea_concepto(factura, monto=_monto({"monto": base}))
        cambios.append("monto")
    elif total not in (None, ""):
        factura.save()
        fac_services.fijar_total_con_impuestos(factura, _monto({"monto": total}))
        cambios.append("monto")
    else:
        _exigir(bool(cambios), "No mandaste ningún campo a cambiar de la factura.")
        factura.save()

    accion.entidad_tipo = "factura"
    accion.entidad_id = factura.pk
