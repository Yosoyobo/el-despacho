"""Anula los egresos de proyecto que el sistema generaba solo (Oscar, 2026-10-14).

    python manage.py limpiar_egresos_automaticos              # SIMULACRO (default)
    python manage.py limpiar_egresos_automaticos --detalle    # + lista cada egreso
    python manage.py limpiar_egresos_automaticos --proyecto LC-0044 --excluir EGR-2026-0123
    python manage.py limpiar_egresos_automaticos --aplicar    # anula de verdad

SIN `--aplicar` NO escribe NADA (ni siquiera con `--dry-run`, que se acepta por
claridad). El criterio de «automático» y por qué se ANULA en vez de borrar viven en
`apps.los_proyectos.limpieza_egresos`. No hay cron ni signal que lo invoque: lo corre
una persona, a mano, primero en simulacro.
"""

from __future__ import annotations

from apps.los_proyectos import limpieza_egresos as limp
from django.core.management.base import BaseCommand


def _dinero(x) -> str:
    return f"${x:,.2f}"


class Command(BaseCommand):
    help = ("Anula (con asiento reverso) los egresos de proyecto generados "
            "automáticamente. Simulacro por default; --aplicar para ejecutar.")

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true",
                            help="Anula de verdad. Sin esto sólo se simula.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Simulacro (ya es el default; se acepta por claridad).")
        parser.add_argument("--detalle", action="store_true",
                            help="Lista cada egreso candidato (y por qué se protege el resto).")
        parser.add_argument("--proyecto", action="append", default=[], metavar="CODIGO",
                            help="Limita a ese proyecto (repetible), p.ej. LC-0044.")
        parser.add_argument("--excluir", action="append", default=[], metavar="EGR-AAAA-NNNN",
                            help="Libra ese egreso de la limpieza (repetible).")

    def handle(self, *args, **opts):
        aplicar = bool(opts["aplicar"]) and not opts["dry_run"]
        cands, prot = limp.candidatos(proyectos=opts["proyecto"], excluir=opts["excluir"])
        grupos = limp.resumen_por_proyecto(cands)
        total = sum((g["monto"] for g in grupos), 0)

        self.stdout.write(self.style.MIGRATE_HEADING(
            "Limpieza de egresos automáticos de proyectos — "
            + ("APLICANDO" if aplicar else "SIMULACRO (no se escribe nada)")))
        if not cands:
            self.stdout.write(self.style.SUCCESS("No hay egresos automáticos que anular."))
        for g in grupos:
            self.stdout.write(f"  {g['proyecto']:<10} {g['cantidad']:>3} egreso(s)  "
                              f"{_dinero(g['monto']):>14}  {g['nombre'][:50]}")
            if opts["detalle"]:
                for e in g["egresos"]:
                    self.stdout.write(f"      - {e.codigo}  {e.fecha:%d/%m/%Y}  "
                                      f"{_dinero(e.monto):>12}  {e.proveedor_nombre[:30]}")
        self.stdout.write(f"Se anularían {len(cands)} egreso(s) por {_dinero(total)} "
                          f"en {len(grupos)} proyecto(s).")
        self.stdout.write(f"Se CONSERVAN {len(prot)} egreso(s) de proyecto "
                          "(registrados a mano, pagados, editados o ligados a algo).")
        if opts["detalle"]:
            for ev in prot:
                e = ev.egreso
                self.stdout.write(f"      = {e.codigo} {e.proyecto.codigo if e.proyecto_id else '—'} "
                                  f"{_dinero(e.monto)}: {'; '.join(ev.razones)}")

        if not aplicar:
            if cands:
                self.stdout.write(self.style.WARNING(
                    "Simulacro: nada cambió. Para ejecutar de verdad agrega --aplicar."))
            return
        hechos = limp.anular_candidatos(cands)
        self.stdout.write(self.style.SUCCESS(
            f"Listo: {hechos} egreso(s) anulados (cada uno con su asiento reverso en "
            "La Contaduría). Lo que faltaba pagar vuelve a la sección amarilla."))
        if hechos != len(cands):
            self.stdout.write(self.style.WARNING(
                f"{len(cands) - hechos} se saltaron porque cambiaron durante la corrida."))
