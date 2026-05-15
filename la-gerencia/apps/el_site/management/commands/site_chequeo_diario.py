"""Corre la batería de chequeos externos y los persiste en `site_chequeo`
con `origen='diario'`. Emite `site.integracion_fallo` por cada falla.

Cron en La Sede (3:30 AM, después de archivo.sh):
    30 3 * * * cd /opt/el-despacho && \\
        docker compose -f docker-compose.yml -f docker-compose.prod.yml \\
        exec -T la-gerencia python manage.py site_chequeo_diario \\
        >> /var/log/site_chequeo.log 2>&1
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz
from lib.site import almacen
from lib.site.registry import PLATAFORMAS, chequear


class Command(BaseCommand):
    help = "Chequeo diario de integraciones externas. Idempotente, se puede correr ad-hoc."

    def handle(self, *args, **opts):
        ok = 0
        errores: list[str] = []
        no_configuradas: list[str] = []
        for plat in PLATAFORMAS:
            res = chequear(plat)
            estado = res.get("estado", "error")
            almacen.guardar(
                plataforma=plat,
                estado=estado,
                latencia_ms=res.get("latencia_ms"),
                mensaje_error=res.get("mensaje_error"),
                origen="diario",
                actor_email=None,
            )
            if estado == "ok":
                ok += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ {plat} OK ({res.get('latencia_ms')}ms)"))
            elif estado == "no_configurada":
                no_configuradas.append(plat)
                self.stdout.write(f"  — {plat} no configurada")
            else:
                errores.append(plat)
                self.stdout.write(self.style.ERROR(f"  ✗ {plat}: {res.get('mensaje_error')}"))
                try:
                    emitir(EventoPortavoz(
                        tipo="site.integracion_fallo",
                        actor_id=None,
                        actor_email=None,
                        payload={
                            "plataforma": plat,
                            "estado": "error",
                            "mensaje_error": (res.get("mensaje_error") or "")[:500],
                            "latencia_ms": res.get("latencia_ms"),
                            "origen": "diario",
                            "actor_email": None,
                        },
                    ))
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(self.style.WARNING(f"    (no se pudo emitir Portavoz: {exc})"))

        resumen = f"OK={ok} errores={len(errores)} no_configuradas={len(no_configuradas)}"
        if errores:
            self.stdout.write(self.style.WARNING(f"\n{resumen}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n{resumen}"))
