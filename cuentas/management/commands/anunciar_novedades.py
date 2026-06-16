"""Notifica a TODOS los usuarios cuando hay novedades nuevas (S-Chalanes-UX #5).

Lee las novedades del manual (`lib.novedades`), detecta las que aún no se han
anunciado (`cuentas.NovedadAnunciada`) y manda UN push masivo con el conteo de
cambios nuevos (no uno por novedad — evita spam). Categoría `novedades`
(opt-out por usuario). El badge contador del sidebar se calcula por usuario y
se limpia cuando cada quien abre /ayuda/novedades/.

Idempotente: una novedad ya anunciada no se vuelve a anunciar.

PRIMERA CORRIDA (tabla vacía) = baseline: registra todas las novedades
actuales SIN notificar, para no inundar al equipo con el changelog histórico.
A partir de ahí, sólo las nuevas disparan push.

Uso (en cada deploy, tras migrate — ej. en mudanza.sh):
    python manage.py anunciar_novedades
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Notifica novedades nuevas del manual a todos los usuarios."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="No registra ni notifica — sólo reporta.")
        parser.add_argument("--forzar-baseline", action="store_true",
                            help="Registra todas sin notificar (re-sincroniza baseline).")

    def handle(self, *args, **opts):
        from cuentas.models import NovedadAnunciada
        from lib import novedades as nov

        dry = opts["dry_run"]
        actuales = nov.claves_actuales()
        if not actuales:
            self.stdout.write("No hay novedades en el manual.")
            return

        ya = set(NovedadAnunciada.objects.values_list("clave", flat=True))
        nuevas = [c for c in actuales if c not in ya]
        if not nuevas:
            self.stdout.write("Sin novedades nuevas.")
            return

        es_baseline = opts["forzar_baseline"] or not ya
        if dry:
            modo = "baseline (sin push)" if es_baseline else f"push masivo ({len(nuevas)})"
            self.stdout.write(f"[dry] {len(nuevas)} novedad(es) nueva(s) → {modo}")
            return

        # Registrar las nuevas como anunciadas (idempotente por unique).
        NovedadAnunciada.objects.bulk_create(
            [NovedadAnunciada(clave=c) for c in nuevas], ignore_conflicts=True)

        if es_baseline:
            # `--forzar-baseline` re-sincroniza en silencio. La PRIMERA corrida
            # natural (tabla vacía) sí anuncia la novedad MÁS RECIENTE — así el
            # equipo se entera de lo último aunque el resto del changelog quede
            # como histórico silencioso (decisión Oscar: una novedad en Ayuda
            # debe disparar push).
            mas_reciente = actuales[0] if actuales else None
            if not opts["forzar_baseline"] and mas_reciente and mas_reciente in nuevas:
                self._notificar_a_todos(1)
                self.stdout.write(
                    f"Baseline: {len(nuevas)} registradas; anunciada la más reciente al equipo.")
                return
            self.stdout.write(f"Baseline: {len(nuevas)} novedad(es) registradas sin notificar.")
            return

        self._notificar_a_todos(len(nuevas))
        self.stdout.write(f"Notificadas {len(nuevas)} novedad(es) a todos los usuarios.")

    def _notificar_a_todos(self, cuantas: int):
        import contextlib
        from collections import Counter

        from cuentas.models.usuario import Usuario
        from interfono.models import InterfonoEntrega
        from lib.interfono import InterfonoConfig, enviar_a_usuario

        # Pista #1: si VAPID no está configurado, NINGÚN push sale (queda como
        # entrega "no_configurado"). Lo decimos arriba para no diagnosticar a ciegas.
        if not InterfonoConfig.esta_configurado():
            self.stdout.write(self.style.WARNING(
                "VAPID NO configurado en Los Ajustes → las novedades se registran "
                "pero no se envía push. Configura las llaves VAPID en /ajustes/."))

        plural = "novedades" if cuantas != 1 else "novedad"
        titulo = f"🔔 {cuantas} {plural} en El Despacho"
        cuerpo = "Toca para ver qué hay de nuevo."
        ids = []
        for u in Usuario.objects.filter(is_active=True):
            # Un push roto no aborta el resto.
            with contextlib.suppress(Exception):
                res = enviar_a_usuario(
                    u, titulo=titulo, cuerpo=cuerpo, url="/ayuda/novedades/",
                    tag="novedades", categoria="novedades",
                    origen_modulo="ayuda", origen_id=0,
                )
                if res and res.get("entrega_id"):
                    ids.append(res["entrega_id"])

        # Desglose por motivo: así el log de mudanza dice exactamente por qué
        # llegó o no llegó (entregada / silenciada_categoria / sin_suscripciones
        # / no_configurado / fallida). Sin esto el diagnóstico era a ciegas.
        if ids:
            conteo = Counter(
                InterfonoEntrega.objects.filter(pk__in=ids)
                .values_list("estado_despacho", flat=True))
            desglose = " · ".join(f"{estado}={n}" for estado, n in sorted(conteo.items()))
            self.stdout.write(f"Push novedades — desglose: {desglose}")
