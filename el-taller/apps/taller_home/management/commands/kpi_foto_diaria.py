"""La foto diaria de los indicadores — la memoria del sistema.

Cada mañana guarda cuánto vale cada KPI. Es lo que después permite decir «subió
20% contra el mes pasado», dibujar la tendencia, detectar que algo se salió de
lo normal y proponer metas basadas en lo que de verdad se ha hecho.

Sin esta corrida diaria, el resto del análisis sólo sabe hablar del presente.

    python manage.py kpi_foto_diaria [--dry-run]

Idempotente: correrlo dos veces el mismo día actualiza la foto, no la duplica.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Guarda el valor de cada indicador para poder compararlo después."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Calcula y muestra, pero no guarda nada.")

    def handle(self, *args, **opts):
        from apps.taller_home import series
        from apps.taller_home.kpis import KPIS

        from cuentas.models.usuario import Usuario
        from lib.permisos import usuarios_con_rol

        dry = opts["dry_run"]
        # Los indicadores se calculan con la mirada más amplia que exista: son
        # el número del DESPACHO, no el de una persona. Si no hay super admin,
        # se usa cualquier cuenta activa antes que no medir nada.
        actor = usuarios_con_rol("super_admin").first() or Usuario.objects.filter(
            is_active=True,
        ).first()
        if actor is None:
            self.stdout.write(self.style.WARNING("No hay usuarios; nada que medir."))
            return

        guardados = fallidos = 0
        for kpi in KPIS:
            # Los KPIs personales ("mis tareas") no tienen sentido como número
            # del despacho: dependen de quién pregunta.
            if kpi.slug.startswith("mis-"):
                continue
            try:
                r = kpi.calcular(actor)
                valor = r.get("valor")
                if isinstance(valor, str):   # "—" y demás: no es medible
                    continue
                if dry:
                    self.stdout.write(f"  {kpi.slug} = {valor}")
                    guardados += 1
                    continue
                if series.guardar(kpi.slug, valor, nota=(r.get("nota") or "")):
                    guardados += 1
                else:
                    fallidos += 1
            except Exception as e:  # noqa: BLE001 — un KPI roto no detiene al resto
                fallidos += 1
                self.stderr.write(f"  {kpi.slug}: {e}")

        prefijo = "[dry] " if dry else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefijo}{guardados} indicadores anotados"
            + (f", {fallidos} fallaron" if fallidos else "") + "."
        ))
