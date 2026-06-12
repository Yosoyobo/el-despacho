"""Estados financieros — V2 + S3 resto.

Estado de resultados (P&L): movimiento del periodo de ingresos y
egresos, agrupados en subgrupos legibles. La utilidad operativa es la
base; sobre ella se calcula una **estimación** de ISR y PTU (S3 resto)
con tasas estándar de México, claramente etiquetada como estimación —
NO sustituye el cálculo del contador externo (regla §16).

Balance general: saldos acumulados a fecha de corte, agrupado por
tipo (activo / pasivo / capital). La utilidad del ejercicio se
calcula on-the-fly (ingresos − egresos del año a la fecha) hasta
que exista un asiento de cierre que la mueva a `3.2.02`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Sum

from .models import CuentaContable, Partida

CERO = Decimal("0.00")

# Tasas estándar México para la ESTIMACIÓN de impuestos en el P&L. No son
# el cálculo fiscal real (eso lo hace el contador externo, regla §16); sirven
# para que LC vea un aproximado de la utilidad después de impuestos. Si LC
# necesita tasas distintas, hoy se editan aquí; un sprint futuro puede moverlas
# a una ConfiguracionFiscal editable.
ISR_TASA = Decimal("30")   # % sobre la utilidad antes de impuestos
PTU_TASA = Decimal("10")   # % de participación de los trabajadores en las utilidades

# slot → (clave_subgrupo, etiqueta_subgrupo, orden)
SLOT_A_SUBGRUPO_INGRESO = {
    "ingreso_ventas": ("ingresos_ventas", "Ingresos por servicios", 1),
    "ingreso_otros": ("ingresos_otros", "Otros ingresos", 9),
}

SLOT_A_SUBGRUPO_EGRESO = {
    "egreso_insumos": ("costo_ventas", "Costo de ventas", 1),
    "egreso_externos": ("costo_ventas", "Costo de ventas", 1),
    "egreso_operativo": ("gastos_operativos", "Gastos operativos", 2),
    "egreso_renta": ("gastos_operativos", "Gastos operativos", 2),
    "egreso_servicios": ("gastos_operativos", "Gastos operativos", 2),
    "egreso_nomina": ("gastos_operativos", "Gastos operativos", 2),
    "egreso_honorarios": ("gastos_operativos", "Gastos operativos", 2),
    "egreso_software": ("gastos_operativos", "Gastos operativos", 2),
    "egreso_viaticos": ("gastos_operativos", "Gastos operativos", 2),
    "egreso_otros": ("gastos_operativos", "Gastos operativos", 2),
}


def _movimiento_neto(cuenta: CuentaContable, cargos: Decimal, abonos: Decimal) -> Decimal:
    if cuenta.naturaleza == "deudora":
        return (cargos - abonos).quantize(Decimal("0.01"))
    return (abonos - cargos).quantize(Decimal("0.01"))


def _agregado_por_cuenta(desde: date | None, hasta: date | None, tipos: list[str]):
    qs = Partida.objects.filter(
        asiento__anulado=False, cuenta__tipo__in=tipos
    ).select_related("cuenta")
    if desde is not None:
        qs = qs.filter(asiento__fecha__gte=desde)
    if hasta is not None:
        qs = qs.filter(asiento__fecha__lte=hasta)
    return (
        qs.values("cuenta_id")
        .annotate(c=Sum("cargo"), a=Sum("abono"))
        .order_by("cuenta__codigo")
    )


def _cuentas_dict(ids):
    return {c.id: c for c in CuentaContable.objects.filter(id__in=list(ids))}


def estado_resultados(
    *, desde: date | None = None, hasta: date | None = None
) -> dict:
    """Calcula P&L para el rango. Retorna estructura agrupada lista
    para renderizar:

        {
            "desde": <date|None>, "hasta": <date|None>,
            "ingresos": {
                "subgrupos": [{"clave","etiqueta","total","cuentas":[{cuenta,monto},...]}],
                "total": Decimal,
            },
            "egresos": { ... mismo shape ... },
            "utilidad_bruta": Decimal,   # ingresos − costo_ventas
            "utilidad_operativa": Decimal,  # utilidad_bruta − gastos_operativos
            "utilidad_neta": Decimal,    # == operativa en V2
        }
    """
    hoy = date.today()
    hasta = hasta or hoy
    if desde is None:
        desde = hasta.replace(day=1)

    ingresos = _construir_seccion("ingreso", desde, hasta, SLOT_A_SUBGRUPO_INGRESO,
                                   subgrupo_default=("ingresos_otros", "Otros ingresos", 9))
    egresos = _construir_seccion("egreso", desde, hasta, SLOT_A_SUBGRUPO_EGRESO,
                                  subgrupo_default=("gastos_operativos", "Gastos operativos", 2))

    total_ingresos = ingresos["total"]
    total_costo = next(
        (sg["total"] for sg in egresos["subgrupos"] if sg["clave"] == "costo_ventas"),
        CERO,
    )
    total_gastos = next(
        (sg["total"] for sg in egresos["subgrupos"] if sg["clave"] == "gastos_operativos"),
        CERO,
    )
    utilidad_bruta = (total_ingresos - total_costo).quantize(Decimal("0.01"))
    utilidad_operativa = (utilidad_bruta - total_gastos).quantize(Decimal("0.01"))
    # `utilidad_neta` se mantiene == operativa para compatibilidad con
    # `balance_general` y los KPIs (que NO deben restar impuestos estimados
    # de los saldos contables reales). La estimación ISR/PTU es informativa.
    utilidad_neta = utilidad_operativa

    # Estimación de impuestos (S3 resto). Solo sobre utilidad positiva.
    base_impuestos_estimados = utilidad_operativa if utilidad_operativa > CERO else CERO
    isr_estimado = (base_impuestos_estimados * ISR_TASA / Decimal("100")).quantize(Decimal("0.01"))
    ptu_estimado = (base_impuestos_estimados * PTU_TASA / Decimal("100")).quantize(Decimal("0.01"))
    utilidad_despues_impuestos = (
        utilidad_operativa - isr_estimado - ptu_estimado
    ).quantize(Decimal("0.01"))

    return {
        "desde": desde,
        "hasta": hasta,
        "ingresos": ingresos,
        "egresos": egresos,
        "total_costo_ventas": total_costo,
        "total_gastos_operativos": total_gastos,
        "utilidad_bruta": utilidad_bruta,
        "utilidad_operativa": utilidad_operativa,
        "utilidad_neta": utilidad_neta,
        # Estimación informativa de impuestos (no es cálculo fiscal real).
        "isr_tasa": ISR_TASA,
        "ptu_tasa": PTU_TASA,
        "isr_estimado": isr_estimado,
        "ptu_estimado": ptu_estimado,
        "utilidad_antes_impuestos": utilidad_operativa,
        "utilidad_despues_impuestos": utilidad_despues_impuestos,
    }


def _construir_seccion(tipo, desde, hasta, mapa, subgrupo_default):
    """Construye una sección (ingresos o egresos) agrupando por subgrupo."""
    agregado = list(_agregado_por_cuenta(desde, hasta, [tipo]))
    cuentas = _cuentas_dict(r["cuenta_id"] for r in agregado)

    subgrupos: dict[str, dict] = {}
    total_seccion = CERO

    for r in agregado:
        cuenta = cuentas.get(r["cuenta_id"])
        if cuenta is None:
            continue
        cargos = r["c"] or CERO
        abonos = r["a"] or CERO
        monto = _movimiento_neto(cuenta, cargos, abonos)
        if monto == CERO:
            continue
        clave, etiqueta, orden = mapa.get(cuenta.slot, subgrupo_default)
        sg = subgrupos.setdefault(
            clave,
            {"clave": clave, "etiqueta": etiqueta, "orden": orden, "total": CERO, "cuentas": []},
        )
        sg["cuentas"].append({"cuenta": cuenta, "monto": monto})
        sg["total"] = (sg["total"] + monto).quantize(Decimal("0.01"))
        total_seccion = (total_seccion + monto).quantize(Decimal("0.01"))

    lista = sorted(subgrupos.values(), key=lambda sg: (sg["orden"], sg["etiqueta"]))
    return {"subgrupos": lista, "total": total_seccion}


def balance_general(*, hasta: date | None = None) -> dict:
    """Saldos acumulados a fecha. Calcula utilidad del periodo
    on-the-fly (movimiento neto de ingresos − egresos desde el 1 de
    enero del año de `hasta` hasta `hasta`). Verifica ecuación
    contable A = P + C + Utilidad.
    """
    hoy = date.today()
    hasta = hasta or hoy

    # Saldos acumulados de balance (activo/pasivo/capital)
    secciones = {}
    for tipo in ("activo", "pasivo", "capital"):
        agregado = list(_agregado_por_cuenta(None, hasta, [tipo]))
        cuentas = _cuentas_dict(r["cuenta_id"] for r in agregado)
        filas = []
        total = CERO
        for r in agregado:
            cuenta = cuentas.get(r["cuenta_id"])
            if cuenta is None:
                continue
            cargos = r["c"] or CERO
            abonos = r["a"] or CERO
            saldo = _movimiento_neto(cuenta, cargos, abonos)
            if saldo == CERO:
                continue
            filas.append({"cuenta": cuenta, "saldo": saldo})
            total = (total + saldo).quantize(Decimal("0.01"))
        filas.sort(key=lambda f: f["cuenta"].codigo)
        secciones[tipo] = {"filas": filas, "total": total}

    # Utilidad del periodo on-the-fly: movimientos del año hasta `hasta`
    inicio_anio = hasta.replace(month=1, day=1)
    pl = estado_resultados(desde=inicio_anio, hasta=hasta)
    utilidad_periodo = pl["utilidad_neta"]

    total_activo = secciones["activo"]["total"]
    total_pasivo = secciones["pasivo"]["total"]
    total_capital = secciones["capital"]["total"]
    suma_pasivo_capital = (total_pasivo + total_capital + utilidad_periodo).quantize(Decimal("0.01"))
    descuadre = (total_activo - suma_pasivo_capital).quantize(Decimal("0.01"))

    return {
        "hasta": hasta,
        "activo": secciones["activo"],
        "pasivo": secciones["pasivo"],
        "capital": secciones["capital"],
        "utilidad_periodo": utilidad_periodo,
        "total_activo": total_activo,
        "total_pasivo": total_pasivo,
        "total_capital": total_capital,
        "total_pasivo_mas_capital": suma_pasivo_capital,
        "descuadre": descuadre,
        "cuadrado": descuadre == CERO,
    }
