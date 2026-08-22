"""La lectura diaria de El Análisis + los avisos de lo que se movió feo.

Hace dos cosas, y sólo la primera cuesta:

1. **Una llamada al Chalán** para que interprete los nueve temas del negocio.
   La lectura queda guardada y es la que se ve en la pantalla El Análisis.
2. **Revisa los umbrales** (margen sano, silencio del cliente, mora…) y avisa
   por El Interfón a quien tenga permiso del tema. Esto no usa IA, así que
   puede correr todos los días sin costo.

    python manage.py chalan_analisis_diario [--solo-alertas] [--dry-run]

Va en el crontab (§10). Si en Gerencia se apaga "leer los números cada mañana",
el paso 1 se salta y sólo quedan los avisos.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

CATEGORIA_PUSH = "chalan_analisis"


class Command(BaseCommand):
    help = "Genera la lectura diaria de El Análisis y avisa de lo que cruzó un umbral."

    def add_arguments(self, parser):
        parser.add_argument("--solo-alertas", action="store_true",
                            help="No llama a la IA; sólo revisa umbrales y avisa.")
        parser.add_argument("--dry-run", action="store_true",
                            help="No guarda ni notifica: muestra lo que haría.")

    def handle(self, *args, **opts):
        from apps.taller_home.analisis import alertas, generar_lectura

        from ajustes.models import ConfiguracionAnalisis

        dry = opts["dry_run"]
        prefijo = "[dry] " if dry else ""
        cfg = ConfiguracionAnalisis.obtener()

        # 1) La lectura del Chalán.
        if opts["solo_alertas"]:
            self.stdout.write("Sin lectura: se pidió sólo revisar umbrales.")
        elif not cfg.analisis_diario_activo:
            self.stdout.write("Sin lectura: la lectura diaria está apagada en Gerencia.")
        else:
            res = generar_lectura(dry_run=dry)
            if res.get("ok"):
                self.stdout.write(self.style.SUCCESS(
                    f"{prefijo}El Chalán leyó {res.get('creadas', 0)} temas "
                    f"({', '.join(res.get('temas') or []) or 'ninguno'})."
                ))
                if not dry:
                    self._emitir("analisis.lectura_generada",
                                 {"temas": res.get("temas") or [],
                                  "creadas": res.get("creadas", 0)})
            else:
                self.stdout.write(self.style.WARNING(
                    f"{prefijo}Sin lectura: {res.get('error')}"))

        # 2) Los avisos (deterministas, sin costo).
        pendientes = alertas()
        if not pendientes:
            self.stdout.write("Nada cruzó un umbral hoy.")
            return

        for a in pendientes:
            self.stdout.write(f"{prefijo}{a['nivel'].upper()}: {a['titulo']}")
        if dry:
            return

        enviados = self._avisar(pendientes)
        self.stdout.write(self.style.SUCCESS(
            f"{len(pendientes)} avisos → {enviados} notificaciones enviadas."))

    # ── Reparto de avisos ────────────────────────────────────────────────

    def _avisar(self, pendientes: list[dict]) -> int:
        """Avisa por El Interfón a quien pueda ver el tema. Nunca lanza."""
        from apps.taller_home.analisis import alertas as alertas_de

        from cuentas.models.usuario import Usuario

        enviados = 0
        for usuario in Usuario.objects.filter(is_active=True):
            try:
                suyas = alertas_de(usuario)
            except Exception:  # noqa: BLE001
                continue
            rojas = [a for a in suyas if a["nivel"] == "rojo"]
            if not rojas:
                continue  # sólo se molesta a alguien por lo rojo
            titulo = (
                rojas[0]["titulo"] if len(rojas) == 1
                else f"{len(rojas)} cosas del negocio necesitan tu atención"
            )
            cuerpo = "; ".join(a["titulo"] for a in rojas[:3])
            if self._push(usuario, titulo, cuerpo):
                enviados += 1
        return enviados

    def _push(self, usuario, titulo: str, cuerpo: str) -> bool:
        try:
            from lib.interfono import enviar_a_usuario

            enviar_a_usuario(
                usuario, titulo=titulo, cuerpo=cuerpo,
                url="/analisis/", categoria=CATEGORIA_PUSH,
            )
            return True
        except Exception:  # noqa: BLE001
            self.stderr.write(f"No se pudo avisar a {usuario.email}")
            return False

    def _emitir(self, tipo: str, payload: dict) -> None:
        try:
            from lib.portavoz import emitir
            from lib.portavoz_eventos import EventoPortavoz

            emitir(EventoPortavoz(tipo=tipo, actor_id=None, actor_email="", payload=payload))
        except Exception:  # noqa: BLE001
            pass
