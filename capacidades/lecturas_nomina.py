"""Lecturas de La Nómina para El Chalán (S-Checador-V2).

- `nomina_quincena` — totales y por persona de una quincena. Gating `nomina`
  (`nomina.ver`): enseña el sueldo de cada quien.
- `mi_recibo` — lo SUYO y sólo de quincenas cerradas. Abierto a cualquiera: la
  función filtra por el usuario que pregunta, nunca por un argumento.

Calcular, cerrar y marcar pagado NO se hacen por chat: son botones de la
pantalla Nómina (decisión de diseño: mueven dinero y cierran periodos). Por eso
aquí no hay propuestas, y `lib.dictado_catalogo` lo declara.
"""

from __future__ import annotations

import datetime

from .registro import Capacidad, registrar


def _fecha(args: dict):
    crudo = (args.get("fecha") or "").strip()
    if not crudo:
        return None
    try:
        return datetime.date.fromisoformat(crudo[:10])
    except ValueError:
        return None


def _nombre(u) -> str:
    return (getattr(u, "nombre_completo", "") or "").strip() or getattr(u, "email", "")


def _h_nomina_quincena(args: dict, usuario) -> dict:
    from apps.checador import nomina as svc
    from apps.checador.models import PeriodoNomina
    from apps.checador.models.nomina import quincena_de

    from lib.fecha import ahora_mx

    fecha = _fecha(args)
    periodo = None
    if fecha is not None:
        periodo = PeriodoNomina.objects.filter(fecha_inicio=quincena_de(fecha)[0]).first()
    else:
        periodo = (PeriodoNomina.objects.filter(fecha_inicio=quincena_de(ahora_mx().date())[0]).first()
                   or PeriodoNomina.objects.order_by("-fecha_inicio").first())
    if periodo is None:
        return {"quincena": None, "mensaje": "No hay quincena abierta para esa fecha. Se abre en la pantalla Nómina."}
    t = svc.totales_periodo(periodo)
    personas = [
        {
            "persona": _nombre(r.usuario), "sueldo": float(r.sueldo_aplicado),
            "percepciones": float(r.percepciones), "deducciones": float(r.deducciones),
            "neto": float(r.neto), "pago": r.get_estado_display() if periodo.cerrado else "al cerrar",
            "faltas": r.faltas, "retardos": r.retardos,
        }
        for r in periodo.recibos.select_related("usuario").order_by("-neto")
    ]
    return {
        "quincena": periodo.etiqueta, "desde": periodo.fecha_inicio.isoformat(),
        "hasta": periodo.fecha_fin.isoformat(), "estado": periodo.get_estado_display(),
        "neto_total": float(t["neto"]), "sueldos": float(t["sueldos"]),
        "percepciones": float(t["percepciones"]), "deducciones": float(t["deducciones"]),
        "recibos": t["recibos"], "pagados": t["pagados"], "por_pagar": float(t["por_pagar"]),
        "personas": personas,
        "nota": "Calcular, cerrar y marcar pagado se hacen con los botones de Nómina, no por chat.",
    }


def _h_mi_recibo(args: dict, usuario) -> dict:
    from apps.checador import nomina as svc
    from apps.checador.models.nomina import quincena_de

    qs = svc.mis_recibos(usuario)
    fecha = _fecha(args)
    if fecha is not None:
        qs = qs.filter(periodo__fecha_inicio=quincena_de(fecha)[0])
    r = qs.first()
    if r is None:
        return {"recibo": None, "mensaje": "No tienes recibos de quincenas cerradas (para esa fecha)."}
    return {
        "quincena": r.periodo.etiqueta, "sueldo": float(r.sueldo_aplicado),
        "conceptos": [
            {"que": c.descripcion, "tipo": c.get_tipo_display(), "monto": float(c.monto)}
            for c in r.conceptos.all()
        ],
        "neto": float(r.neto), "estado": r.get_estado_display(),
        "depositado_el": r.pagado_en.isoformat() if r.pagado_en else None,
        "pdf": f"/nomina/recibo/{r.pk}/pdf",
        "otros_recibos": max(0, qs.count() - 1),
    }


_LECTURAS = {
    "nomina_quincena": Capacidad(
        nombre="nomina_quincena",
        descripcion=(
            "La Nómina de una quincena (1–15 o 16–fin de mes): estado (abierta, "
            "calculada, cerrada), total a pagar, sueldos, percepciones, deducciones, "
            "cuántos recibos van pagados, y por persona su neto, faltas y retardos. "
            "Arg opcional: fecha (AAAA-MM-DD, cualquier día de la quincena; por "
            "default la de hoy). Calcular, cerrar o pagar NO se hace por chat."
        ),
        args_schema={"fecha": {"tipo": "str", "requerido": False}},
        gating="nomina", fn=_h_nomina_quincena,
    ),
    "mi_recibo": Capacidad(
        nombre="mi_recibo",
        descripcion=(
            "Tu recibo de nómina de una quincena YA CERRADA: sueldo, conceptos "
            "(bonos, abonos a préstamo, reembolsos, deducciones), neto y si ya se "
            "depositó, con el enlace al PDF. Sólo el tuyo. Arg opcional: fecha "
            "(AAAA-MM-DD); por default el último."
        ),
        args_schema={"fecha": {"tipo": "str", "requerido": False}},
        gating="abierto", fn=_h_mi_recibo,
    ),
}

for _cap in _LECTURAS.values():
    registrar(_cap)
