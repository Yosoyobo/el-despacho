"""Helpers del wizard "+ Nuevo movimiento".

Wraps `services.crear_asiento` con dos flows simples (traspaso y
ajuste) en lenguaje no-contable. La validación de partida doble se
delega al service base; aquí sólo armamos las partidas correctas
según la naturaleza de cada cuenta.
"""

from __future__ import annotations

from datetime import date as _date
from decimal import Decimal

from .models import CuentaContable
from .services import crear_asiento

CODIGO_AJUSTE_CAPTURA = "6.0.01"


def _obtener_o_crear_cuenta_ajuste() -> CuentaContable:
    """Devuelve la cuenta 6.0.01 Ajustes de captura. La migración 0005
    la siembra; este helper es defensa por si la migración no corrió o
    alguien la desactivó."""
    obj, _ = CuentaContable.objects.get_or_create(
        codigo=CODIGO_AJUSTE_CAPTURA,
        defaults={
            "nombre": "Ajustes de captura",
            "tipo": "capital",
            "naturaleza": "acreedora",
            "slot": "ajuste_captura",
            "descripcion": "Contrapartida de ajustes de saldo capturados por wizard.",
            "activa": True,
        },
    )
    if not obj.activa:
        obj.activa = True
        obj.save(update_fields=["activa"])
    return obj


def cuentas_traspasables():
    """Cuentas elegibles como origen/destino de un traspaso.

    Activos (caja, bancos) y pasivos (proveedores, reembolsos por
    pagar). NO ingresos/egresos/capital — esos son cuentas de
    resultado o patrimoniales que no representan dinero líquido.
    """
    return CuentaContable.activas.filter(
        tipo__in=["activo", "pasivo"]
    ).order_by("codigo")


def cuentas_ajustables():
    """Cuentas elegibles para ajuste de saldo: activos y pasivos."""
    return CuentaContable.activas.filter(
        tipo__in=["activo", "pasivo"]
    ).order_by("codigo")


def registrar_traspaso(
    *,
    cuenta_origen: CuentaContable,
    cuenta_destino: CuentaContable,
    monto: Decimal,
    descripcion: str,
    fecha: _date | None = None,
    creado_por=None,
):
    """Traspaso entre cuentas: D destino / H origen por el monto.

    Funciona para cualquier combinación de naturalezas. El service
    base valida que cargos == abonos (es 1 partida vs 1 partida).
    """
    monto = Decimal(str(monto)).quantize(Decimal("0.01"))
    if monto <= 0:
        from .services import AsientoInvalido
        raise AsientoInvalido("El monto del traspaso debe ser mayor a cero.")
    if cuenta_origen.pk == cuenta_destino.pk:
        from .services import AsientoInvalido
        raise AsientoInvalido("La cuenta origen y destino deben ser distintas.")
    return crear_asiento(
        descripcion=f"Traspaso · {descripcion}".strip(" ·"),
        fecha=fecha or _date.today(),
        origen="manual",
        referencia_externa="",
        partidas=[
            {"cuenta": cuenta_destino, "cargo": monto, "orden": 0,
             "descripcion": "Destino del traspaso"},
            {"cuenta": cuenta_origen, "abono": monto, "orden": 1,
             "descripcion": "Origen del traspaso"},
        ],
        creado_por=creado_por,
        idempotente=False,
    )


def registrar_ajuste(
    *,
    cuenta_objetivo: CuentaContable,
    direccion: str,  # 'sube' | 'baja'
    monto: Decimal,
    motivo: str,
    fecha: _date | None = None,
    creado_por=None,
):
    """Ajuste de saldo contra cuenta 6.0.01 Ajustes de captura.

    Reglas (donde cuenta_objetivo es la que se ajusta y ajuste_captura
    es acreedora):

    - Si "sube" + objetivo deudora: D objetivo / H ajustes.
    - Si "sube" + objetivo acreedora: H objetivo / D ajustes.
    - Si "baja" + objetivo deudora: H objetivo / D ajustes.
    - Si "baja" + objetivo acreedora: D objetivo / H ajustes.
    """
    from .services import AsientoInvalido

    monto = Decimal(str(monto)).quantize(Decimal("0.01"))
    if monto <= 0:
        raise AsientoInvalido("El monto del ajuste debe ser mayor a cero.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise AsientoInvalido("El ajuste requiere una razón.")
    if direccion not in ("sube", "baja"):
        raise AsientoInvalido("La dirección del ajuste debe ser 'sube' o 'baja'.")

    cuenta_ajuste = _obtener_o_crear_cuenta_ajuste()

    sube_saldo = direccion == "sube"
    objetivo_deudora = cuenta_objetivo.naturaleza == "deudora"
    # Cargo a la objetivo si (sube y deudora) o (baja y acreedora).
    cargo_a_objetivo = (sube_saldo and objetivo_deudora) or (not sube_saldo and not objetivo_deudora)

    if cargo_a_objetivo:
        partidas = [
            {"cuenta": cuenta_objetivo, "cargo": monto, "orden": 0,
             "descripcion": "Ajuste de saldo"},
            {"cuenta": cuenta_ajuste, "abono": monto, "orden": 1,
             "descripcion": "Contrapartida del ajuste"},
        ]
    else:
        partidas = [
            {"cuenta": cuenta_ajuste, "cargo": monto, "orden": 0,
             "descripcion": "Contrapartida del ajuste"},
            {"cuenta": cuenta_objetivo, "abono": monto, "orden": 1,
             "descripcion": "Ajuste de saldo"},
        ]

    return crear_asiento(
        descripcion=f"Ajuste · {motivo}",
        fecha=fecha or _date.today(),
        origen="ajuste",
        referencia_externa="",
        partidas=partidas,
        creado_por=creado_por,
        idempotente=False,
    )
