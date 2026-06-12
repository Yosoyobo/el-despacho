"""Services de La Contaduría.

`crear_asiento` valida partida doble (sum cargos == sum abonos) y crea
asiento + partidas atómicamente. Idempotente por `referencia_externa`
para hookpoints automáticos: si ya existe un asiento vigente para la
misma referencia, devuelve ese sin duplicar.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import Asiento, CuentaContable, Partida

CERO = Decimal("0.00")


class AsientoInvalido(ValueError):
    pass


def cuenta_por_slot(slot: str) -> CuentaContable | None:
    return CuentaContable.objects.filter(slot=slot, activa=True).first()


def cuenta_por_codigo(codigo: str) -> CuentaContable | None:
    return CuentaContable.objects.filter(codigo=codigo, activa=True).first()


def crear_asiento(
    *,
    descripcion: str,
    partidas: list[dict],
    fecha: date | None = None,
    origen: str = "manual",
    referencia_externa: str = "",
    creado_por=None,
    idempotente: bool = True,
) -> Asiento:
    """Crea asiento contable con sus partidas, validando partida doble.

    `partidas`: lista de dicts `{cuenta, cargo, abono, descripcion?, orden?}`.
    `cuenta` puede ser instance de `CuentaContable` o un código `str`.
    Cada partida debe tener exactamente uno de `cargo`/`abono` > 0.

    Si `idempotente=True` y `referencia_externa` ya existe en un asiento
    vigente, devuelve ese asiento sin crear duplicado.
    """
    if not partidas:
        raise AsientoInvalido("Un asiento requiere al menos 2 partidas.")
    if len(partidas) < 2:
        raise AsientoInvalido("Partida doble requiere ≥ 2 partidas.")

    if idempotente and referencia_externa:
        existente = Asiento.vigentes.filter(referencia_externa=referencia_externa).first()
        if existente:
            return existente

    fecha = fecha or date.today()

    # Resolver cuentas + validar montos por partida
    resueltas = []
    suma_cargos = CERO
    suma_abonos = CERO
    for i, p in enumerate(partidas):
        cuenta = p["cuenta"]
        if isinstance(cuenta, str):
            obj = cuenta_por_codigo(cuenta)
            if obj is None:
                raise AsientoInvalido(f"Cuenta inexistente o inactiva: {cuenta!r}")
            cuenta = obj
        cargo = Decimal(str(p.get("cargo") or 0)).quantize(Decimal("0.01"))
        abono = Decimal(str(p.get("abono") or 0)).quantize(Decimal("0.01"))
        if cargo < 0 or abono < 0:
            raise AsientoInvalido(f"Partida {i}: cargo/abono no pueden ser negativos.")
        if cargo > 0 and abono > 0:
            raise AsientoInvalido(f"Partida {i}: no puede tener cargo y abono simultáneamente.")
        if cargo == 0 and abono == 0:
            raise AsientoInvalido(f"Partida {i}: debe tener cargo o abono > 0.")
        suma_cargos += cargo
        suma_abonos += abono
        resueltas.append({
            "cuenta": cuenta,
            "cargo": cargo,
            "abono": abono,
            "descripcion": p.get("descripcion", "") or "",
            "orden": p.get("orden", i),
        })

    if suma_cargos != suma_abonos:
        raise AsientoInvalido(
            f"Partida doble desbalanceada: cargos={suma_cargos} ≠ abonos={suma_abonos}"
        )

    with transaction.atomic():
        asiento = Asiento.objects.create(
            descripcion=descripcion[:300],
            fecha=fecha,
            origen=origen,
            referencia_externa=referencia_externa,
            creado_por=creado_por if getattr(creado_por, "is_authenticated", False) else None,
        )
        for p in resueltas:
            Partida.objects.create(
                asiento=asiento,
                cuenta=p["cuenta"],
                cargo=p["cargo"],
                abono=p["abono"],
                descripcion=p["descripcion"][:200],
                orden=p["orden"],
            )

    emitir(EventoPortavoz(
        tipo="contaduria.asiento_creado",
        actor_id=getattr(creado_por, "id", None),
        actor_email=getattr(creado_por, "email", None),
        payload={
            "asiento_id": asiento.id,
            "codigo": asiento.codigo,
            "origen": origen,
            "total": float(suma_cargos),
            "referencia_externa": referencia_externa,
        },
    ))
    return asiento


def anular_asiento(asiento: Asiento, *, actor, motivo: str) -> Asiento:
    if asiento.anulado:
        raise AsientoInvalido("El asiento ya está anulado.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise AsientoInvalido("Debe registrarse el motivo de anulación.")
    with transaction.atomic():
        asiento.anulado = True
        asiento.anulado_en = timezone.now()
        asiento.anulado_por = actor if getattr(actor, "is_authenticated", False) else None
        asiento.motivo_anulacion = motivo[:300]
        asiento.save(update_fields=[
            "anulado", "anulado_en", "anulado_por", "motivo_anulacion", "actualizado_en",
        ])
    emitir(EventoPortavoz(
        tipo="contaduria.asiento_anulado",
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload={"asiento_id": asiento.id, "codigo": asiento.codigo, "motivo": motivo[:200]},
    ))
    return asiento


# ── Saldos y libro mayor ────────────────────────────────────────────────

def saldo_cuenta(
    cuenta: CuentaContable,
    *,
    desde: date | None = None,
    hasta: date | None = None,
) -> Decimal:
    """Saldo según naturaleza: deudora=cargos-abonos, acreedora=abonos-cargos.

    Si `desde`/`hasta` se pasan, suma sólo asientos vigentes en el rango
    inclusivo. Sin `desde` es saldo acumulado histórico hasta `hasta`
    (o hasta hoy si tampoco hay `hasta`).
    """
    from django.db.models import Sum
    qs = Partida.objects.filter(cuenta=cuenta, asiento__anulado=False)
    if desde is not None:
        qs = qs.filter(asiento__fecha__gte=desde)
    if hasta is not None:
        qs = qs.filter(asiento__fecha__lte=hasta)
    totales = qs.aggregate(c=Sum("cargo"), a=Sum("abono"))
    cargos = totales["c"] or CERO
    abonos = totales["a"] or CERO
    if cuenta.naturaleza == "deudora":
        return (cargos - abonos).quantize(Decimal("0.01"))
    return (abonos - cargos).quantize(Decimal("0.01"))


def balance_de_comprobacion(
    *, desde: date | None = None, hasta: date | None = None
) -> list[dict]:
    """Lista de cuentas con cargos, abonos y saldo. Filtra cuentas con
    movimiento; el resto se omite para no inflar la tabla."""
    from django.db.models import Sum
    qs = Partida.objects.filter(asiento__anulado=False).select_related("cuenta")
    if desde is not None:
        qs = qs.filter(asiento__fecha__gte=desde)
    if hasta is not None:
        qs = qs.filter(asiento__fecha__lte=hasta)
    agregado = (
        qs.values("cuenta_id")
        .annotate(c=Sum("cargo"), a=Sum("abono"))
        .order_by("cuenta__codigo")
    )
    salida = []
    cache = {c.id: c for c in CuentaContable.objects.filter(
        id__in=[r["cuenta_id"] for r in agregado]
    )}
    for r in agregado:
        cuenta = cache.get(r["cuenta_id"])
        if cuenta is None:
            continue
        cargos = r["c"] or CERO
        abonos = r["a"] or CERO
        saldo = (cargos - abonos) if cuenta.naturaleza == "deudora" else (abonos - cargos)
        salida.append({
            "cuenta": cuenta,
            "cargos": cargos.quantize(Decimal("0.01")),
            "abonos": abonos.quantize(Decimal("0.01")),
            "saldo": saldo.quantize(Decimal("0.01")),
        })
    return salida


def kpis_landing() -> dict:
    """KPIs del header de La Contaduría."""
    from datetime import date as _d
    hoy = _d.today()
    inicio_mes = hoy.replace(day=1)
    asientos_mes = Asiento.vigentes.filter(fecha__gte=inicio_mes).count()
    caja = cuenta_por_slot("caja")
    banco = cuenta_por_slot("banco")
    cxc = cuenta_por_slot("cxc")
    saldo_caja = saldo_cuenta(caja) if caja else CERO
    saldo_banco = saldo_cuenta(banco) if banco else CERO
    saldo_cxc = saldo_cuenta(cxc) if cxc else CERO
    return {
        "asientos_mes": asientos_mes,
        "saldo_caja": saldo_caja,
        "saldo_banco": saldo_banco,
        "saldo_cxc": saldo_cxc,
    }


# ── Cierre de periodo (S3 resto) ─────────────────────────────────────────

CODIGO_UTILIDAD_EJERCICIO = "3.2.02"


class CierreInvalido(ValueError):
    pass


def cerrar_periodo(*, desde: date, hasta: date, actor=None):
    """Cancela ingresos (4.x) y egresos (5.x) del rango contra
    `3.2.02 Utilidad del ejercicio` con un asiento de cierre.

    El asiento lleva, por cada cuenta de resultado con saldo en el rango,
    una partida que la deja en cero (la del lado opuesto a su naturaleza),
    y una partida balance a la cuenta de utilidad por la diferencia (=
    utilidad o pérdida del periodo). Devuelve el `CierrePeriodo`.

    Idempotente: si ya hay un cierre VIGENTE para el mismo rango, lo
    devuelve sin duplicar.
    """
    from .models import CierrePeriodo

    if hasta < desde:
        raise CierreInvalido("El rango es inválido (la fecha final es anterior a la inicial).")

    existente = CierrePeriodo.vigentes.filter(desde=desde, hasta=hasta).first()
    if existente:
        return existente

    cuenta_utilidad = cuenta_por_codigo(CODIGO_UTILIDAD_EJERCICIO)
    if cuenta_utilidad is None:
        raise CierreInvalido(
            f"Falta la cuenta {CODIGO_UTILIDAD_EJERCICIO} (Utilidad del ejercicio) en el catálogo."
        )

    nominales = CuentaContable.objects.filter(
        tipo__in=["ingreso", "egreso"], activa=True
    ).order_by("codigo")

    partidas: list[dict] = []
    suma_cargos = CERO
    suma_abonos = CERO
    for cuenta in nominales:
        s = saldo_cuenta(cuenta, desde=desde, hasta=hasta)
        if s == CERO:
            continue
        # Dejar la cuenta en cero: postear del lado contrario a su naturaleza.
        if cuenta.naturaleza == "acreedora":
            if s > 0:
                partidas.append({"cuenta": cuenta, "cargo": s, "descripcion": "Cierre de periodo"})
                suma_cargos += s
            else:
                partidas.append({"cuenta": cuenta, "abono": -s, "descripcion": "Cierre de periodo"})
                suma_abonos += -s
        else:  # deudora
            if s > 0:
                partidas.append({"cuenta": cuenta, "abono": s, "descripcion": "Cierre de periodo"})
                suma_abonos += s
            else:
                partidas.append({"cuenta": cuenta, "cargo": -s, "descripcion": "Cierre de periodo"})
                suma_cargos += -s

    if not partidas:
        raise CierreInvalido("No hay movimientos de ingresos ni egresos que cerrar en el periodo.")

    # Partida balance a Utilidad del ejercicio. dif = cargos − abonos de las
    # cuentas de resultado == utilidad (positiva) o pérdida (negativa).
    utilidad = (suma_cargos - suma_abonos).quantize(Decimal("0.01"))
    if utilidad > 0:
        partidas.append({
            "cuenta": cuenta_utilidad, "abono": utilidad,
            "descripcion": "Utilidad del ejercicio",
        })
    elif utilidad < 0:
        partidas.append({
            "cuenta": cuenta_utilidad, "cargo": -utilidad,
            "descripcion": "Pérdida del ejercicio",
        })

    if len(partidas) < 2:
        raise CierreInvalido("El cierre no genera partida doble (un solo movimiento).")

    asiento = crear_asiento(
        descripcion=f"Cierre de periodo {desde.isoformat()} → {hasta.isoformat()}",
        partidas=partidas,
        fecha=hasta,
        origen="cierre",
        referencia_externa=CierrePeriodo.referencia_para(desde, hasta),
        creado_por=actor,
        idempotente=True,
    )
    cierre = CierrePeriodo.objects.create(
        desde=desde, hasta=hasta, asiento=asiento, utilidad=utilidad,
        creado_por=actor if getattr(actor, "is_authenticated", False) else None,
    )
    emitir(EventoPortavoz(
        tipo="contaduria.periodo_cerrado",
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload={
            "cierre_id": cierre.id,
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
            "utilidad": float(utilidad),
            "asiento_codigo": asiento.codigo,
        },
    ))
    return cierre


def reabrir_periodo(cierre, *, actor, motivo: str):
    """Revierte un cierre: anula el asiento de cierre y marca el periodo
    como reabierto (queda la traza). No borra el `CierrePeriodo`."""
    if cierre.reabierto:
        raise CierreInvalido("El periodo ya estaba reabierto.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise CierreInvalido("Debe registrarse el motivo de reapertura.")
    with transaction.atomic():
        if cierre.asiento and not cierre.asiento.anulado:
            anular_asiento(
                cierre.asiento, actor=actor,
                motivo=f"Reapertura de periodo: {motivo}"[:300],
            )
        cierre.reabierto = True
        cierre.reabierto_en = timezone.now()
        cierre.reabierto_por = actor if getattr(actor, "is_authenticated", False) else None
        cierre.motivo_reapertura = motivo[:300]
        cierre.save(update_fields=[
            "reabierto", "reabierto_en", "reabierto_por", "motivo_reapertura",
        ])
    emitir(EventoPortavoz(
        tipo="contaduria.periodo_reabierto",
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload={"cierre_id": cierre.id, "motivo": motivo[:200]},
    ))
    return cierre
