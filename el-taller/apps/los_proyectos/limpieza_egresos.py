"""Limpieza de los egresos que el sistema generaba solo (Oscar, 2026-10-14).

Hasta 2026-10-13 un signal creaba un Egreso «pendiente» por cada línea/proceso de
un proyecto al pasar a producción (ver el comentario en `apps.py`). Oscar los quiere
fuera: «wipear registro de egresos de proyectos EXCEPTO los que he registrado».

Qué hace este módulo (y NO se ejecuta solo: lo invoca el comando
`limpiar_egresos_automaticos`, que por default sólo simula):

**Anular, no borrar.** Cada egreso tiene su asiento `auto_egreso` en La Contaduría
(D gasto / H CxP). Borrar el egreso dejaría ese asiento huérfano y el balance
mentiría. Anularlo (`tesoreria.services.anular_egreso`) dispara el hook de
Contaduría, que crea el asiento REVERSO (`auto_anulacion_egreso`): el libro queda
cuadrado y con rastro. Además, al quedar anulado el egreso, la línea/proceso del
proyecto vuelve a salir en la sección amarilla de «pagos pendientes» (que es la
sugerencia correcta) y el proyecto ya no lo lista.

**Criterio de «automático» (exacto y conservador).** Sólo lo que la ruta automática
pudo crear y NADIE tocó. Un egreso es candidato si cumple TODO:

* `origen == "proyecto"`, `estado_pago == "pendiente"`, no anulado, con proyecto;
* `creado_por` vacío (todo egreso registrado por una persona lleva su nombre —
  `gastos._quien`— y queda a salvo);
* centro de costo `insumos-de-proyecto`, método `transferencia` (los defaults de
  la ruta automática) y descripción «Proyecto <código> · …» (su formato);
* sin pagador/solicitante, sin fecha de pago, sin comprobante ni datos de IA/OCR;
* **no editado**: `actualizado_en` a ≤ 60 s de `creado_en`;
* **sin vínculos ajenos**: ninguna relación inversa fuera de las dos que ponen las
  tarjetas del proyecto (`lineas_proyecto`, `procesos_proyecto`) — con eso quedan
  protegidos los ligados a CFDI de proveedor, nómina, log de OCR, etc., y los que
  se añadan en el futuro (se evalúa sobre `Egreso._meta.related_objects`);
* **asiento limpio**: su ÚNICO asiento es el `auto_egreso` original. Si hay uno de
  pago/reembolso/ajuste/anulación ligado, alguien ya operó el egreso.

Todo lo que no pasa alguna prueba se reporta como «protegido» con su razón.

Ambigüedad conocida: un egreso que alguien creó con los botones «Registrar» de
«Gastos no registrados» ANTES de 2026-10-14 es idéntico a uno automático (no
llevaba `creado_por`). Por eso el simulacro lista cada candidato con código y fecha,
y el comando acepta `--excluir` para librarlos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.db import transaction

CENTRO_SLUG = "insumos-de-proyecto"
METODO_AUTOMATICO = "transferencia"
VENTANA_SIN_TOCAR = timedelta(seconds=60)
# Relaciones inversas que SÍ ponen las tarjetas del proyecto al registrar/generar.
RELACIONES_DEL_PROYECTO = frozenset({"lineas_proyecto", "procesos_proyecto"})
MOTIVO_ANULACION = "Egreso automático de producción retirado (limpieza 2026-10-14)"


@dataclass
class Evaluacion:
    egreso: object
    razones: list[str] = field(default_factory=list)  # por qué NO es candidato

    @property
    def candidato(self) -> bool:
        return not self.razones


def _relaciones_ajenas(egreso) -> list[str]:
    """Nombres de las relaciones inversas (fuera de las del proyecto) con filas."""
    ajenas = []
    for rel in egreso._meta.related_objects:
        nombre = rel.get_accessor_name()
        if nombre in RELACIONES_DEL_PROYECTO:
            continue
        try:
            tiene = rel.related_model._default_manager.filter(
                **{rel.field.name: egreso}).exists()
        except Exception:  # noqa: BLE001 — ante la duda, protege
            tiene = True
        if tiene:
            ajenas.append(nombre)
    return ajenas


def _asientos_ajenos(egreso) -> list[str]:
    """Asientos ligados a este egreso que NO son el auto_egreso original (pago,
    reembolso, anulación, manuales…). Incluye los anulados."""
    from apps.contaduria.models import Asiento

    base = f"tesoreria.egreso:{egreso.pk}"
    ajenos = []
    qs = Asiento.objects.filter(
        referencia_externa__startswith="tesoreria.egreso",
        referencia_externa__endswith=f":{egreso.pk}",
    )
    for a in qs:
        if a.referencia_externa == base and a.origen == "auto_egreso":
            continue
        ajenos.append(f"{a.codigo} ({a.origen})")
    return ajenos


def evaluar(egreso) -> Evaluacion:
    """Aplica el criterio de arriba a UN egreso y dice por qué se protege."""
    ev = Evaluacion(egreso=egreso)
    r = ev.razones
    if egreso.origen != "proyecto":
        r.append("origen distinto de «proyecto»")
    if egreso.estado_pago != "pendiente":
        r.append(f"estado «{egreso.estado_pago}» (alguien lo pagó o reembolsó)")
    if egreso.anulado:
        r.append("ya está anulado")
    if egreso.proyecto_id is None:
        r.append("sin proyecto")
    if egreso.creado_por_id is not None:
        r.append("lo registró una persona")
    if not egreso.centro_de_costo or egreso.centro_de_costo.slug != CENTRO_SLUG:
        r.append("centro de costo distinto del automático")
    if egreso.metodo != METODO_AUTOMATICO:
        r.append(f"método «{egreso.metodo}»")
    cod = egreso.proyecto.codigo if egreso.proyecto_id else ""
    if not (egreso.descripcion or "").startswith(f"Proyecto {cod} · "):
        r.append("descripción escrita a mano")
    if egreso.pagado_por_id or egreso.solicitado_por_id or egreso.pagado_en:
        r.append("tiene pagador/solicitante/fecha de pago")
    if egreso.tiene_comprobante or egreso.drive_file_id or egreso.confianza_ia is not None:
        r.append("tiene comprobante o datos de OCR")
    if egreso.actualizado_en and egreso.creado_en and \
            egreso.actualizado_en - egreso.creado_en > VENTANA_SIN_TOCAR:
        r.append("fue editado después de crearse")
    ajenas = _relaciones_ajenas(egreso)
    if ajenas:
        r.append("ligado a: " + ", ".join(ajenas))
    asientos = _asientos_ajenos(egreso)
    if asientos:
        r.append("asientos ajenos: " + ", ".join(asientos))
    return ev


def candidatos(*, proyectos=None, excluir=None):
    """(candidatos, protegidos) entre los egresos `origen=proyecto` vigentes.

    `proyectos`: códigos a los que limitar. `excluir`: códigos de egreso a librar.
    Sólo mira egresos de origen «proyecto» no anulados: lo demás ni se considera."""
    from apps.tesoreria.models import Egreso

    qs = (
        Egreso.objects.filter(origen="proyecto", anulado=False)
        .select_related("proyecto", "centro_de_costo")
        .order_by("proyecto__codigo", "fecha", "pk")
    )
    if proyectos:
        qs = qs.filter(proyecto__codigo__in=list(proyectos))
    excluir = set(excluir or [])
    cands, prot = [], []
    for e in qs:
        ev = evaluar(e)
        if e.codigo in excluir:
            ev.razones.append("excluido con --excluir")
        (cands if ev.candidato else prot).append(ev)
    return cands, prot


def resumen_por_proyecto(evaluaciones) -> list[dict]:
    """[{proyecto, nombre, cantidad, monto, egresos}] ordenado por código."""
    grupos: dict[str, dict] = {}
    for ev in evaluaciones:
        e = ev.egreso
        cod = e.proyecto.codigo if e.proyecto_id else "—"
        g = grupos.setdefault(cod, {
            "proyecto": cod, "nombre": e.proyecto.nombre if e.proyecto_id else "",
            "cantidad": 0, "monto": Decimal("0.00"), "egresos": []})
        g["cantidad"] += 1
        g["monto"] += e.monto
        g["egresos"].append(e)
    return [grupos[k] for k in sorted(grupos)]


def anular_candidatos(cands) -> int:
    """Anula (con asiento reverso) cada candidato, RE-evaluándolo justo antes:
    si en el entretiempo alguien lo tocó, se salta. Una transacción por egreso."""
    from apps.tesoreria.models import Egreso
    from apps.tesoreria.services import anular_egreso

    hechos = 0
    for ev in cands:
        with transaction.atomic():
            e = Egreso.objects.select_for_update().select_related(
                "proyecto", "centro_de_costo").get(pk=ev.egreso.pk)
            if not evaluar(e).candidato:
                continue
            anular_egreso(e, None, MOTIVO_ANULACION)
            hechos += 1
    return hechos
