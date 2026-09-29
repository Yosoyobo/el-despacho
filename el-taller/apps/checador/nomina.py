"""Servicios de La Nómina interna (S-Checador-V2). Ver `models/nomina.py`.

**Reglas (decisiones de Oscar, 2026-09-29):**

- Sueldo FIJO por quincena. Las horas del Checador sólo informan.
- **Qué sueldo aplica a una quincena:** el vigente el ÚLTIMO día de la
  quincena (el de mayor `vigente_desde <= fecha_fin`). Si empezó a media
  quincena —un aumento, un alta— el recibo lo marca y guarda el sueldo
  anterior, para que quien cierra decida si ajusta los días con un concepto.
  Se eligió el último día y no el primero para que un alta a media quincena
  no deje a la persona fuera de su primera nómina.
- **Recalcular** (sólo antes de cerrar) refresca el sueldo y las horas y vuelve
  a proponer lo automático (abonos a préstamo, reembolsos) que NO esté ya en el
  recibo. Lo que se capturó o ajustó a mano se respeta; lo automático que se
  quitó a mano no regresa (queda en `ReciboNomina.quitados`).
- **Préstamos:** el abono se propone como deducción (editable); el saldo baja
  SÓLO al cerrar la quincena.
- **Reembolsos:** los pendientes de la persona en Tesorería entran como
  percepción. Al marcar PAGADO el recibo se saldan en Tesorería con
  `tesoreria.services.reembolsar_egreso` —el mismo del botón «Reembolsar»—, en
  la misma transacción. Uno que se pagó por otro lado: antes de cerrar se saca
  del recibo con aviso; después de cerrar, se avisa y NO se vuelve a saldar.
  Es la ÚNICA escritura en Tesorería: la nómina es sólo reporte.
- Cerrado es inmutable.
"""

from __future__ import annotations

import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from lib.fecha import ahora_mx

from .models import (
    ConceptoRecibo,
    Jornada,
    PeriodoNomina,
    PrestamoNomina,
    ReciboNomina,
    SueldoPersona,
)
from .models.nomina import CERO, TIPO_POR_CLASE, quincena_de

CENTAVO = Decimal("0.01")

METODOS_PAGO_NOMINA = (
    ("transferencia", "Transferencia"),
    ("efectivo", "Efectivo"),
    ("cheque", "Cheque"),
    ("otro", "Otro"),
)


def _q(valor) -> Decimal:
    return Decimal(valor or 0).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _emitir(tipo: str, *, actor, payload: dict) -> None:
    """Evento del Portavoz tras el commit. Best-effort (patrón del Checador)."""

    def _post():
        try:
            from lib.portavoz import emitir
            from lib.portavoz_eventos import EventoPortavoz
            emitir(EventoPortavoz(
                tipo=tipo, actor_id=getattr(actor, "id", None),
                actor_email=getattr(actor, "email", None), payload=payload,
            ))
        except Exception:  # noqa: BLE001 — un evento nunca tumba la nómina
            pass

    transaction.on_commit(_post)


# ───────────────────────── sueldos ─────────────────────────

def sueldo_vigente(usuario, fecha) -> SueldoPersona | None:
    """El renglón vigente para `fecha`: el de mayor `vigente_desde <= fecha`.

    Puede ser una BAJA (`en_nomina=False`): quien llama decide qué hacer."""
    return (
        SueldoPersona.objects.filter(usuario=usuario, vigente_desde__lte=fecha)
        .order_by("-vigente_desde").first()
    )


def sueldo_de_quincena(usuario, inicio, fin) -> tuple[SueldoPersona | None, SueldoPersona | None]:
    """(el que aplica, el que había antes si cambió dentro de la quincena)."""
    aplica = sueldo_vigente(usuario, fin)
    if aplica is None or not aplica.en_nomina:
        return None, None
    anterior = None
    if aplica.vigente_desde > inicio:
        anterior = sueldo_vigente(usuario, aplica.vigente_desde - datetime.timedelta(days=1))
    return aplica, anterior


def personas_en_nomina(inicio, fin) -> list:
    """Usuarios activos con sueldo vigente (y en nómina) al cierre de la quincena."""
    from cuentas.models.usuario import Usuario

    ids = SueldoPersona.objects.filter(vigente_desde__lte=fin).values_list("usuario_id", flat=True).distinct()
    salida = []
    for u in Usuario.objects.filter(pk__in=list(ids), is_active=True).order_by("nombre_completo"):
        aplica, _ = sueldo_de_quincena(u, inicio, fin)
        if aplica is not None:
            salida.append(u)
    return salida


# ───────────────────────── horas (sólo informan) ─────────────────────────

def horas_informativas(usuario, inicio, fin, *, hoy=None) -> dict:
    """Lo que El Checador dice de la quincena. NO mueve el sueldo.

    - días laborales / horas esperadas: del horario de la persona (`horario_vigente`).
    - horas trabajadas: misma regla que el balance del tablero (jornada cerrada,
      o el tiempo de proyecto cuando no checó).
    - faltas: días laborales ya pasados sin jornada ni tiempo de proyecto. Los
      días de hoy en adelante no cuentan como falta.
    - retardos: jornadas con retardo, y sus minutos.

    El Checador no tiene vacaciones, permisos ni incapacidades por persona: un
    día así sale como falta y se ajusta a mano (el recibo sólo informa)."""
    from .services import _min_horario, _trabajado_min_dia, horario_vigente

    hoy = hoy or timezone.localdate()
    dias = esperadas = trabajadas = faltas = 0
    dia = inicio
    while dia <= fin:
        horario = horario_vigente(usuario, dia)
        trab, tipo = _trabajado_min_dia(usuario, dia)
        trabajadas += trab
        if horario is not None:
            dias += 1
            esperadas += _min_horario(horario)
            if dia < hoy and tipo == "vacio":
                faltas += 1
        dia += datetime.timedelta(days=1)
    con_retardo = Jornada.objects.filter(
        usuario=usuario, fecha__gte=inicio, fecha__lte=fin, retardo_min__gt=0,
    )
    return {
        "dias_laborales": dias,
        "horas_esperadas": _q(Decimal(esperadas) / 60),
        "horas_trabajadas": _q(Decimal(trabajadas) / 60),
        "faltas": faltas,
        "retardos": con_retardo.count(),
        "minutos_retardo": int(con_retardo.aggregate(s=Sum("retardo_min"))["s"] or 0),
    }


def horas_laborales_quincena(usuario, fecha) -> Decimal:
    """Horas que SU horario espera en la quincena de `fecha` (para el costeo)."""
    from .services import _min_horario, horario_vigente

    inicio, fin = quincena_de(fecha)
    minutos = 0
    dia = inicio
    while dia <= fin:
        horario = horario_vigente(usuario, dia)
        if horario is not None:
            minutos += _min_horario(horario)
        dia += datetime.timedelta(days=1)
    return Decimal(minutos) / 60


def costo_hora_por_sueldo(usuario, fecha) -> Decimal | None:
    """Sueldo quincenal ÷ horas laborales de su horario en esa quincena.

    None cuando no hay sueldo capturado (o es baja) o su horario no espera
    horas esa quincena: entonces `mano_obra` cae a la tarifa del rol."""
    inicio, fin = quincena_de(fecha)
    aplica, _ = sueldo_de_quincena(usuario, inicio, fin)
    if aplica is None:
        return None
    horas = horas_laborales_quincena(usuario, fecha)
    if horas <= 0:
        return None
    return _q(aplica.sueldo_quincenal / horas)


# ───────────────────────── periodos ─────────────────────────

def abrir_periodo(fecha, *, actor=None) -> PeriodoNomina:
    """La quincena que contiene `fecha`. Si ya existe, la devuelve tal cual."""
    inicio, fin = quincena_de(fecha)
    periodo, _ = PeriodoNomina.objects.get_or_create(
        fecha_inicio=inicio, defaults={"fecha_fin": fin, "creado_por": actor},
    )
    return periodo


def _prestamo_comprometido(prestamo, *, excluir_recibo=None) -> Decimal:
    """Lo que ya está apartado para abonos en quincenas AÚN NO cerradas."""
    qs = ConceptoRecibo.objects.filter(prestamo=prestamo).exclude(recibo__periodo__estado="cerrado")
    if excluir_recibo is not None:
        qs = qs.exclude(recibo=excluir_recibo)
    return _q(qs.aggregate(s=Sum("monto"))["s"])


def saldo_disponible(prestamo, *, excluir_recibo=None) -> Decimal:
    """Saldo menos lo apartado en otras quincenas abiertas."""
    return max(CERO, _q(prestamo.saldo) - _prestamo_comprometido(prestamo, excluir_recibo=excluir_recibo))


def reembolsos_pendientes_de(usuario, *, excluir_recibo=None):
    """Egresos de Tesorería que se le deben a la persona y que ningún OTRO
    recibo trae ya (para no pagarlos en dos quincenas)."""
    from apps.tesoreria.models import Egreso

    qs = Egreso.vigentes.filter(estado_pago="por_reembolsar", pagado_por=usuario)
    ocupados = ConceptoRecibo.objects.filter(egreso__isnull=False)
    if excluir_recibo is not None:
        ocupados = ocupados.exclude(recibo=excluir_recibo)
    return qs.exclude(pk__in=ocupados.values("egreso_id")).order_by("fecha", "pk")


def reembolso_vigente(concepto) -> bool:
    """¿El reembolso del concepto sigue pendiente en Tesorería?"""
    eg = concepto.egreso
    return bool(eg is not None and not eg.anulado and eg.estado_pago == "por_reembolsar")


def reembolsos_pagados_aparte(recibo) -> list[ConceptoRecibo]:
    """Los reembolsos del recibo que ya se saldaron (o anularon) por otro lado."""
    return [
        c for c in recibo.conceptos.select_related("egreso").filter(clase="reembolso")
        if not reembolso_vigente(c)
    ]


def recomputar_totales(recibo, *, guardar: bool = True) -> ReciboNomina:
    agg = {c: CERO for c in ("percepcion", "deduccion")}
    for tipo, monto in recibo.conceptos.values_list("tipo", "monto"):
        agg[tipo] = agg.get(tipo, CERO) + _q(monto)
    recibo.percepciones = _q(agg["percepcion"])
    recibo.deducciones = _q(agg["deduccion"])
    recibo.neto = _q(_q(recibo.sueldo_aplicado) + recibo.percepciones - recibo.deducciones)
    if guardar:
        recibo.save(update_fields=["percepciones", "deducciones", "neto", "actualizado_en"])
    return recibo


def _proponer_automaticos(recibo) -> list[str]:
    """Agrega los abonos y reembolsos que falten. Devuelve avisos."""
    avisos: list[str] = []
    quitados = set(recibo.quitados or [])
    ya = {c.clave_automatica for c in recibo.conceptos.all() if c.clave_automatica}
    fin = recibo.periodo.fecha_fin

    for p in PrestamoNomina.objects.filter(usuario=recibo.usuario, saldo__gt=0, fecha__lte=fin).order_by("fecha", "pk"):
        clave = f"prestamo:{p.pk}"
        if clave in ya or clave in quitados:
            continue
        abono = min(_q(p.cuota), saldo_disponible(p, excluir_recibo=recibo))
        if abono <= 0:
            continue
        ConceptoRecibo.objects.create(
            recibo=recibo, tipo="deduccion", clase="prestamo", prestamo=p,
            descripcion=f"Abono a {p.concepto or 'préstamo'}", monto=abono,
            automatico=True, orden=50,
        )

    for eg in reembolsos_pendientes_de(recibo.usuario, excluir_recibo=recibo):
        clave = f"egreso:{eg.pk}"
        if clave in ya or clave in quitados:
            continue
        ConceptoRecibo.objects.create(
            recibo=recibo, tipo="percepcion", clase="reembolso", egreso=eg,
            descripcion=f"Reembolso {eg.codigo} · {eg.descripcion}"[:200], monto=_q(eg.monto),
            automatico=True, orden=40,
        )
    return avisos


def _sacar_reembolsos_pagados(recibo) -> list[str]:
    avisos = []
    for c in reembolsos_pagados_aparte(recibo):
        codigo = getattr(c.egreso, "codigo", "") or "sin egreso"
        avisos.append(
            f"{_nombre(recibo.usuario)}: el reembolso {codigo} (${_q(c.monto)}) ya se pagó "
            "por otro lado en Tesorería; se sacó del recibo para no pagarlo dos veces."
        )
        c.delete()
    return avisos


def _nombre(usuario) -> str:
    return (getattr(usuario, "nombre_completo", "") or "").strip() or getattr(usuario, "email", "")


def calcular_periodo(periodo, *, actor=None, hoy=None) -> list[str]:
    """Calcula (o recalcula) la quincena. Sólo antes de cerrar. Devuelve avisos."""
    avisos: list[str] = []
    with transaction.atomic():
        periodo = PeriodoNomina.objects.select_for_update().get(pk=periodo.pk)
        if periodo.cerrado:
            raise ValueError("Esta quincena ya está cerrada: no se puede recalcular.")
        inicio, fin = periodo.fecha_inicio, periodo.fecha_fin
        personas = personas_en_nomina(inicio, fin)
        ids = {u.pk for u in personas}

        # Quien ya no está en nómina (baja, sin sueldo): su recibo sale, salvo
        # que traiga algo capturado a mano — eso no se tira sin avisar.
        for r in periodo.recibos.select_related("usuario").exclude(usuario_id__in=ids):
            if r.conceptos.filter(automatico=False).exists():
                r.sueldo_aplicado = CERO
                r.save(update_fields=["sueldo_aplicado", "actualizado_en"])
                recomputar_totales(r)
                avisos.append(f"{_nombre(r.usuario)} ya no tiene sueldo en esta quincena; su recibo "
                              "queda en $0 porque trae conceptos a mano. Revísalo.")
            else:
                r.delete()

        for u in personas:
            aplica, anterior = sueldo_de_quincena(u, inicio, fin)
            recibo, _ = ReciboNomina.objects.get_or_create(periodo=periodo, usuario=u)
            recibo.sueldo_aplicado = _q(aplica.sueldo_quincenal)
            recibo.sueldo_vigente_desde = aplica.vigente_desde
            recibo.sueldo_anterior = (
                _q(anterior.sueldo_quincenal) if anterior is not None and anterior.en_nomina else None
            )
            for campo, valor in horas_informativas(u, inicio, fin, hoy=hoy).items():
                setattr(recibo, campo, valor)
            recibo.save()
            # Lo automático que nadie tocó se rehace; lo tocado a mano se respeta.
            recibo.conceptos.filter(automatico=True).delete()
            avisos += _sacar_reembolsos_pagados(recibo)
            avisos += _proponer_automaticos(recibo)
            recomputar_totales(recibo)
            if recibo.cambio_sueldo_en_periodo:
                antes = f"${recibo.sueldo_anterior}" if recibo.sueldo_anterior is not None else "sin sueldo"
                avisos.append(
                    f"{_nombre(u)}: su sueldo cambió el {aplica.vigente_desde:%d/%m} (antes {antes}). "
                    "La quincena se paga con el nuevo; si corresponde, ajusta los días con un concepto."
                )

        periodo.estado = "calculado"
        periodo.calculado_por = actor if getattr(actor, "is_authenticated", False) else None
        periodo.calculado_en = ahora_mx()
        periodo.save(update_fields=["estado", "calculado_por", "calculado_en", "actualizado_en"])
    if not personas:
        avisos.append("Nadie tiene sueldo capturado para esta quincena. Captura los sueldos primero.")
    return avisos


def cerrar_periodo(periodo, *, actor=None) -> list[str]:
    """Cierra la quincena: los recibos quedan inmutables y el saldo de los
    préstamos baja por sus abonos. Devuelve avisos."""
    avisos: list[str] = []
    with transaction.atomic():
        periodo = PeriodoNomina.objects.select_for_update().get(pk=periodo.pk)
        if periodo.cerrado:
            raise ValueError("Esta quincena ya está cerrada.")
        if periodo.estado != "calculado":
            raise ValueError("Primero calcula la quincena.")
        recibos = list(periodo.recibos.select_related("usuario"))
        for r in recibos:
            avisos += _sacar_reembolsos_pagados(r)
            recomputar_totales(r)
            if r.neto < 0:
                raise ValueError(f"El recibo de {_nombre(r.usuario)} queda negativo (${r.neto}). Ajústalo antes de cerrar.")
        abonos = (ConceptoRecibo.objects.filter(recibo__periodo=periodo, prestamo__isnull=False)
                  .select_related("recibo__usuario"))
        for c in abonos:
            p = PrestamoNomina.objects.select_for_update().get(pk=c.prestamo_id)
            if _q(c.monto) > _q(p.saldo):
                raise ValueError(
                    f"El abono de {_nombre(c.recibo.usuario)} (${_q(c.monto)}) es mayor que el saldo "
                    f"del préstamo (${_q(p.saldo)}). Ajústalo antes de cerrar."
                )
            p.saldo = _q(p.saldo) - _q(c.monto)
            p.save(update_fields=["saldo", "actualizado_en"])
        periodo.estado = "cerrado"
        periodo.cerrado_por = actor if getattr(actor, "is_authenticated", False) else None
        periodo.cerrado_en = ahora_mx()
        periodo.save(update_fields=["estado", "cerrado_por", "cerrado_en", "actualizado_en"])
    tot = totales_periodo(periodo)
    _emitir("nomina.periodo_cerrado", actor=actor, payload={
        "periodo_id": periodo.pk, "etiqueta": periodo.etiqueta,
        "desde": periodo.fecha_inicio.isoformat(), "hasta": periodo.fecha_fin.isoformat(),
        "recibos": tot["recibos"], "neto_total": float(tot["neto"]),
    })
    return avisos


def marcar_pagado(recibo, *, fecha, metodo: str = "transferencia", banco_o_caja: str = "banco",
                  actor=None) -> list[str]:
    """El recibo se depositó. Salda en Tesorería los reembolsos que incluyó (una
    sola transacción). Uno que ya se pagó por otro lado se avisa y NO se vuelve
    a saldar. Devuelve avisos."""
    from apps.tesoreria.models import Egreso
    from apps.tesoreria.services import reembolsar_egreso

    if fecha is None:
        raise ValueError("Indica la fecha real del depósito.")
    if metodo not in dict(METODOS_PAGO_NOMINA):
        raise ValueError("Método de pago inválido.")
    if banco_o_caja not in ("banco", "caja"):
        raise ValueError("La cuenta de salida debe ser banco o caja.")
    avisos: list[str] = []
    saldados: list[str] = []
    with transaction.atomic():
        recibo = ReciboNomina.objects.select_for_update().select_related("periodo", "usuario").get(pk=recibo.pk)
        if not recibo.periodo.cerrado:
            raise ValueError("Cierra la quincena antes de marcar pagos.")
        if recibo.pagado:
            raise ValueError("Este recibo ya está marcado como pagado.")
        # El método del egreso de Tesorería: efectivo sale de caja; lo demás, transferencia.
        metodo_teso = "efectivo" if metodo == "efectivo" else ("cheque" if metodo == "cheque" else "transferencia")
        for c in recibo.conceptos.filter(clase="reembolso").order_by("pk"):
            eg = Egreso.objects.select_for_update().filter(pk=c.egreso_id).first() if c.egreso_id else None
            if eg is None or eg.anulado or eg.estado_pago != "por_reembolsar":
                codigo = getattr(eg, "codigo", "") or "sin egreso"
                avisos.append(
                    f"El reembolso {codigo} (${_q(c.monto)}) ya se había pagado por otro lado: "
                    "no se volvió a saldar en Tesorería. El recibo lo incluía; descuéntalo del depósito."
                )
                continue
            reembolsar_egreso(eg, metodo=metodo_teso, banco_o_caja=banco_o_caja, fecha=fecha, actor=actor)
            saldados.append(eg.codigo)
            if not getattr(eg, "_reembolso_asiento_creado", True):
                avisos.append(
                    f"El reembolso {eg.codigo} quedó saldado pero sin movimiento contable: "
                    f"{getattr(eg, '_reembolso_motivo_no_asiento', '')}"
                )
        recibo.estado = "pagado"
        recibo.pagado_en = fecha
        recibo.metodo_pago = metodo
        recibo.pagado_por = actor if getattr(actor, "is_authenticated", False) else None
        recibo.pago_registrado_en = ahora_mx()
        recibo.save(update_fields=["estado", "pagado_en", "metodo_pago", "pagado_por",
                                   "pago_registrado_en", "actualizado_en"])
    _emitir("nomina.recibo_pagado", actor=actor, payload={
        "recibo_id": recibo.pk, "periodo_id": recibo.periodo_id, "usuario_id": recibo.usuario_id,
        "neto": float(recibo.neto), "fecha": fecha.isoformat(), "reembolsos_saldados": saldados,
    })
    return avisos


# ───────────────────────── lectura ─────────────────────────

def totales_periodo(periodo) -> dict:
    agg = periodo.recibos.aggregate(
        sueldos=Sum("sueldo_aplicado"), percepciones=Sum("percepciones"),
        deducciones=Sum("deducciones"), neto=Sum("neto"),
    )
    pagado = periodo.recibos.filter(estado="pagado").aggregate(s=Sum("neto"))["s"]
    return {
        "recibos": periodo.recibos.count(),
        "pagados": periodo.recibos.filter(estado="pagado").count(),
        "sueldos": _q(agg["sueldos"]), "percepciones": _q(agg["percepciones"]),
        "deducciones": _q(agg["deducciones"]), "neto": _q(agg["neto"]),
        "pagado": _q(pagado), "por_pagar": _q(_q(agg["neto"]) - _q(pagado)),
    }


def mis_recibos(usuario):
    """Los recibos CERRADOS de la persona — lo único que ve sin permiso de nómina."""
    return (ReciboNomina.objects.filter(usuario=usuario, periodo__estado="cerrado")
            .select_related("periodo").prefetch_related("conceptos")
            .order_by("-periodo__fecha_inicio"))


def historial_prestamo(prestamo) -> list[dict]:
    """Abonos del préstamo, con su quincena y si ya se aplicó al saldo."""
    filas = []
    for c in (prestamo.abonos.select_related("recibo__periodo").order_by("recibo__periodo__fecha_inicio")):
        filas.append({
            "periodo": c.recibo.periodo, "monto": _q(c.monto),
            "aplicado": c.recibo.periodo.cerrado, "recibo": c.recibo,
        })
    return filas


def tipo_para_clase(clase: str, tipo: str) -> str:
    """El ajuste va del lado que se elija; las demás clases mandan su tipo."""
    return TIPO_POR_CLASE.get(clase, tipo if tipo in ("percepcion", "deduccion") else "percepcion")


__all__ = [
    "METODOS_PAGO_NOMINA", "sueldo_vigente", "sueldo_de_quincena", "personas_en_nomina",
    "horas_informativas", "horas_laborales_quincena", "costo_hora_por_sueldo",
    "abrir_periodo", "calcular_periodo", "cerrar_periodo", "marcar_pagado",
    "saldo_disponible", "reembolsos_pendientes_de", "reembolsos_pagados_aparte",
    "recomputar_totales", "totales_periodo", "mis_recibos", "historial_prestamo",
    "tipo_para_clase",
]
