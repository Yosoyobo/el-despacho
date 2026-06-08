"""Evalúa los presupuestos de IA por usuario y avisa de los rebasados.

S-Directorio-Panel-V1. Para AMBAS políticas (`alertar` y `topar`): si el gasto
del mes alcanzó el tope y aún no se avisó este mes, emite `presupuesto_ia.rebasado`
por Portavoz + push a super_admin/dueño, y marca `alerta_mes` para no repetir.

El gate que BLOQUEA la IA (política `topar`) vive en `lib.analistas.analizar` —
este cron solo avisa. Idempotente: una vez por mes por usuario.

Uso (cron diario, ej. 06:10):
    python manage.py evaluar_presupuestos_ia
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from cuentas.models.presupuesto_ia import PresupuestoIA
from cuentas.models.usuario import Usuario
from lib.analistas.stats import gasto_mes_usuario
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz


class Command(BaseCommand):
    help = "Avisa de usuarios que rebasaron su presupuesto de IA del mes."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo reporta.")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        mes = timezone.now().strftime("%Y-%m")
        n = 0
        for p in PresupuestoIA.objects.filter(activo=True, tope_usd__gt=0).select_related("usuario"):
            gastado = gasto_mes_usuario(p.usuario_id)
            if gastado < p.tope_usd:
                continue
            if p.alerta_mes == mes:
                continue  # ya avisado este mes
            n += 1
            if dry:
                self.stdout.write(
                    f"[dry] {p.usuario.email}: ${gastado}/${p.tope_usd} ({p.politica})"
                )
                continue
            p.alerta_mes = mes
            p.save(update_fields=["alerta_mes", "actualizado_en"])
            emitir(EventoPortavoz(
                tipo="presupuesto_ia.rebasado",
                actor_id=None, actor_email=None,
                payload={
                    "usuario_id": p.usuario_id,
                    "email": p.usuario.email,
                    "tope_usd": float(p.tope_usd),
                    "gastado_usd": float(gastado),
                    "politica": p.politica,
                },
            ))
            self._avisar_admins(p, gastado)
        self.stdout.write(self.style.SUCCESS(f"Presupuestos rebasados avisados: {n}"))

    def _avisar_admins(self, p, gastado):
        import contextlib

        from lib.interfono import enviar_a_usuario
        accion = "se topó la IA" if p.politica == PresupuestoIA.POLITICA_TOPAR else "solo alerta"
        for admin in Usuario.objects.filter(is_active=True, rol__in=("super_admin", "dueno")):
            # Un push roto (sin VAPID/Redis) no debe romper el cron.
            with contextlib.suppress(Exception):
                enviar_a_usuario(
                    admin,
                    titulo="💸 Presupuesto de IA rebasado",
                    cuerpo=f"{p.usuario.email} gastó ${gastado} de ${p.tope_usd} este mes ({accion}).",
                    url="/directorio/",
                    tag=f"presupuesto-ia-{p.usuario_id}",
                    categoria="presupuesto_ia",
                    origen_modulo="directorio",
                    origen_id=p.usuario_id,
                )
