"""Reconciliación bancaria (S3 resto) — services.

Cotejo del estado de cuenta del banco contra los movimientos del libro
en la cuenta (`banco`/`caja`/`stripe_saldo`/...). V1:

1. `crear_conciliacion` — abre el cotejo para un rango y cuenta.
2. `importar_csv` — parsea el estado de cuenta (CSV flexible) en `LineaBancaria`.
3. `automatch` — casa cada línea pendiente con una partida del libro por
   monto (firmado) + fecha cercana.
4. `match_manual` / `desmatch` — cotejo manual de una línea ↔ partida.
5. `resumen` — saldo banco vs saldo libros + pendientes de ambos lados.

El `monto` de la línea es firmado: + entra al banco, − sale. La partida del
libro en una cuenta deudora aporta `cargo − abono` (cargo = entra).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

from .models import ConciliacionBancaria, CuentaContable, LineaBancaria, Partida

CERO = Decimal("0.00")

# Slots/condiciones de cuentas que tiene sentido conciliar (representan
# dinero líquido en una institución externa, naturaleza deudora).
SLOTS_CONCILIABLES = {"banco", "caja", "stripe_saldo", "mp_saldo"}


def cuentas_conciliables():
    """Cuentas activas, deudoras, que representan dinero líquido."""
    from django.db.models import Q
    return CuentaContable.objects.filter(
        activa=True, naturaleza="deudora",
    ).filter(Q(slot__in=SLOTS_CONCILIABLES) | Q(tipo="activo")).order_by("codigo")


def partida_firmada(p: Partida) -> Decimal:
    """Aporte firmado de una partida en cuenta deudora: cargo − abono."""
    return ((p.cargo or CERO) - (p.abono or CERO)).quantize(Decimal("0.01"))


def crear_conciliacion(*, cuenta, desde, hasta, saldo_estado_cuenta=CERO, actor=None):
    conc = ConciliacionBancaria.objects.create(
        cuenta=cuenta, desde=desde, hasta=hasta,
        saldo_estado_cuenta=Decimal(str(saldo_estado_cuenta or 0)).quantize(Decimal("0.01")),
        creada_por=actor if getattr(actor, "is_authenticated", False) else None,
    )
    emitir(EventoPortavoz(
        tipo="contaduria.conciliacion_creada",
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        payload={"conciliacion_id": conc.id, "cuenta": cuenta.codigo,
                 "desde": desde.isoformat(), "hasta": hasta.isoformat()},
    ))
    return conc


def _parsear_fecha(valor: str):
    valor = (valor or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(valor, fmt).date()
        except ValueError:
            continue
    return None


def _parsear_monto(valor: str) -> Decimal | None:
    valor = (valor or "").strip().replace("$", "").replace(",", "").replace(" ", "")
    if not valor:
        return None
    try:
        return Decimal(valor).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def importar_csv(conc: ConciliacionBancaria, *, contenido: str) -> dict:
    """Parsea un CSV del estado de cuenta y crea `LineaBancaria`. Devuelve
    `{creadas, ignoradas, error}`. Columnas flexibles (encabezado obligatorio):

    - fecha:        fecha / date
    - descripcion:  descripcion / concepto / description
    - monto:        monto / importe / amount  (FIRMADO: + entra, − sale)
                    o el par deposito/retiro (o abono/cargo).
    - referencia:   referencia / folio (opcional)
    """
    contenido = contenido or ""
    # Detectar delimitador entre coma y punto y coma.
    muestra = contenido[:2048]
    delim = ";" if muestra.count(";") > muestra.count(",") else ","
    reader = csv.DictReader(io.StringIO(contenido), delimiter=delim)
    if not reader.fieldnames:
        return {"creadas": 0, "ignoradas": 0, "error": "El archivo está vacío o no tiene encabezado."}

    norm = {(h or "").strip().lower(): (h or "") for h in reader.fieldnames}

    def col(*candidatos):
        for c in candidatos:
            if c in norm:
                return norm[c]
        return None

    col_fecha = col("fecha", "date", "f. operación", "f. operacion")
    col_desc = col("descripcion", "descripción", "concepto", "description", "detalle")
    col_monto = col("monto", "importe", "amount", "cantidad")
    col_dep = col("deposito", "depósito", "abono", "abonos", "ingreso")
    col_ret = col("retiro", "retiros", "cargo", "cargos", "egreso")
    col_ref = col("referencia", "folio", "ref", "reference")

    if not col_fecha or (not col_monto and not (col_dep or col_ret)):
        return {"creadas": 0, "ignoradas": 0,
                "error": "Faltan columnas: se requiere 'fecha' y 'monto' (o 'deposito'/'retiro')."}

    creadas = 0
    ignoradas = 0
    orden = conc.lineas.count()
    lineas_nuevas = []
    for row in reader:
        fecha = _parsear_fecha(row.get(col_fecha, ""))
        if fecha is None:
            ignoradas += 1
            continue
        if col_monto:
            monto = _parsear_monto(row.get(col_monto, ""))
        else:
            dep = _parsear_monto(row.get(col_dep, "")) if col_dep else None
            ret = _parsear_monto(row.get(col_ret, "")) if col_ret else None
            monto = (dep or CERO) - (ret or CERO)
        if monto is None or monto == CERO:
            ignoradas += 1
            continue
        lineas_nuevas.append(LineaBancaria(
            conciliacion=conc, fecha=fecha,
            descripcion=(row.get(col_desc, "") or "").strip()[:300] if col_desc else "",
            referencia=(row.get(col_ref, "") or "").strip()[:80] if col_ref else "",
            monto=monto, orden=orden + creadas,
        ))
        creadas += 1

    if lineas_nuevas:
        LineaBancaria.objects.bulk_create(lineas_nuevas)
    return {"creadas": creadas, "ignoradas": ignoradas, "error": ""}


def _partidas_libro(conc: ConciliacionBancaria):
    """Partidas del libro en la cuenta, dentro del rango, no anuladas."""
    return Partida.objects.filter(
        cuenta=conc.cuenta, asiento__anulado=False,
        asiento__fecha__gte=conc.desde, asiento__fecha__lte=conc.hasta,
    ).select_related("asiento").order_by("asiento__fecha", "pk")


def _partidas_ya_conciliadas_ids():
    return set(
        LineaBancaria.objects.filter(conciliada=True, partida__isnull=False)
        .values_list("partida_id", flat=True)
    )


def automatch(conc: ConciliacionBancaria, *, dias_tolerancia: int = 3) -> int:
    """Casa líneas pendientes con partidas del libro por monto firmado +
    fecha cercana. Devuelve cuántas casó."""

    ocupadas = _partidas_ya_conciliadas_ids()
    candidatas = [p for p in _partidas_libro(conc) if p.id not in ocupadas]
    # index por monto firmado para match rápido
    casadas = 0
    for linea in conc.lineas.filter(conciliada=False).order_by("fecha", "orden"):
        mejor = None
        mejor_dist = None
        for p in candidatas:
            if p.id in ocupadas:
                continue
            if partida_firmada(p) != linea.monto:
                continue
            dist = abs((p.asiento.fecha - linea.fecha).days)
            if dist > dias_tolerancia:
                continue
            if mejor is None or dist < mejor_dist:
                mejor, mejor_dist = p, dist
        if mejor is not None:
            linea.partida = mejor
            linea.conciliada = True
            linea.save(update_fields=["partida", "conciliada"])
            ocupadas.add(mejor.id)
            casadas += 1
    if casadas:
        conc.actualizada_en = timezone.now()
        conc.save(update_fields=["actualizada_en"])
    return casadas


def match_manual(linea: LineaBancaria, partida: Partida) -> None:
    linea.partida = partida
    linea.conciliada = True
    linea.save(update_fields=["partida", "conciliada"])


def desmatch(linea: LineaBancaria) -> None:
    linea.partida = None
    linea.conciliada = False
    linea.save(update_fields=["partida", "conciliada"])


def resumen(conc: ConciliacionBancaria) -> dict:
    """Saldo banco vs saldo libros + pendientes de ambos lados."""
    from . import services

    saldo_libros = services.saldo_cuenta(conc.cuenta, hasta=conc.hasta)
    lineas = list(conc.lineas.all())
    conciliadas = [ln for ln in lineas if ln.conciliada]
    pendientes_banco = [ln for ln in lineas if not ln.conciliada]
    monto_pendiente_banco = sum((ln.monto for ln in pendientes_banco), CERO)

    ocupadas = {ln.partida_id for ln in conciliadas if ln.partida_id}
    partidas = list(_partidas_libro(conc))
    pendientes_libro = [p for p in partidas if p.id not in ocupadas]
    monto_pendiente_libro = sum((partida_firmada(p) for p in pendientes_libro), CERO)

    return {
        "saldo_libros": saldo_libros,
        "saldo_estado_cuenta": conc.saldo_estado_cuenta,
        "diferencia": (conc.saldo_estado_cuenta - saldo_libros).quantize(Decimal("0.01")),
        "total_lineas": len(lineas),
        "conciliadas": len(conciliadas),
        "pendientes_banco": pendientes_banco,
        "monto_pendiente_banco": monto_pendiente_banco.quantize(Decimal("0.01")),
        "pendientes_libro": pendientes_libro,
        "monto_pendiente_libro": monto_pendiente_libro.quantize(Decimal("0.01")),
        "cuadrada": (conc.saldo_estado_cuenta - saldo_libros).quantize(Decimal("0.01")) == CERO,
    }
