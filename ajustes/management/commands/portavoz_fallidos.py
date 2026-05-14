"""Inspecciona y administra la dead-letter queue del Portavoz.

Uso:
    python manage.py portavoz_fallidos --listar
    python manage.py portavoz_fallidos --reencolar <indice>     # vuelve a la cola principal
    python manage.py portavoz_fallidos --descartar <indice>     # elimina definitivamente
    python manage.py portavoz_fallidos --vaciar                 # purga toda la DLQ (pide confirmación)

`<indice>` es el offset 0-based de la lista al momento de `--listar`.
"""

import json
import os

import redis
from django.core.management.base import BaseCommand, CommandError

DLQ = "portavoz:fallidos"
COLA = "portavoz:cola"


class Command(BaseCommand):
    help = "Inspecciona o procesa la dead-letter queue del Portavoz."

    def add_arguments(self, parser):
        grupo = parser.add_mutually_exclusive_group(required=True)
        grupo.add_argument("--listar", action="store_true", help="Lista eventos en la DLQ.")
        grupo.add_argument("--reencolar", type=int, metavar="INDICE", help="Reencola el evento INDICE en la cola principal.")
        grupo.add_argument("--descartar", type=int, metavar="INDICE", help="Elimina definitivamente el evento INDICE.")
        grupo.add_argument("--vaciar", action="store_true", help="Vacía toda la DLQ.")
        parser.add_argument("--si", action="store_true", help="Confirma --vaciar sin preguntar.")

    def _redis(self):
        url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        return redis.Redis.from_url(url, decode_responses=True)

    def handle(self, *args, **opts):
        r = self._redis()
        total = r.llen(DLQ)

        if opts["listar"]:
            self.stdout.write(self.style.NOTICE(f"DLQ {DLQ}: {total} evento(s)"))
            if total == 0:
                return
            items = r.lrange(DLQ, 0, -1)
            for idx, raw in enumerate(items):
                try:
                    evt = json.loads(raw)
                    tipo = evt.get("tipo", "?")
                    intentos = evt.get("_intentos", "?")
                    emitido = evt.get("emitido_en", "?")
                    actor = evt.get("actor_email", "?")
                    self.stdout.write(f"  [{idx}] {tipo} · intentos={intentos} · {emitido} · {actor}")
                except json.JSONDecodeError:
                    self.stdout.write(self.style.ERROR(f"  [{idx}] JSON corrupto: {raw[:80]}…"))
            return

        if opts["reencolar"] is not None:
            idx = opts["reencolar"]
            raw = r.lindex(DLQ, idx)
            if raw is None:
                raise CommandError(f"Índice {idx} fuera de rango (DLQ tiene {total}).")
            try:
                evt = json.loads(raw)
                evt["_intentos"] = 0  # reset contador para darle otra oportunidad
                raw_nuevo = json.dumps(evt, ensure_ascii=False)
            except json.JSONDecodeError:
                raw_nuevo = raw
            # LREM con count=1 borra solo la primera ocurrencia exacta.
            r.lrem(DLQ, 1, raw)
            r.rpush(COLA, raw_nuevo)
            self.stdout.write(self.style.SUCCESS(f"Reencolado [{idx}] a {COLA} con _intentos reseteado."))
            return

        if opts["descartar"] is not None:
            idx = opts["descartar"]
            raw = r.lindex(DLQ, idx)
            if raw is None:
                raise CommandError(f"Índice {idx} fuera de rango.")
            r.lrem(DLQ, 1, raw)
            self.stdout.write(self.style.SUCCESS(f"Descartado [{idx}]."))
            return

        if opts["vaciar"]:
            if not opts["si"]:
                resp = input(f"¿Vaciar {total} evento(s) de {DLQ}? [escribe SI]: ").strip()
                if resp != "SI":
                    self.stdout.write(self.style.WARNING("Cancelado."))
                    return
            r.delete(DLQ)
            self.stdout.write(self.style.SUCCESS(f"DLQ vaciada ({total} evento(s) borrado(s))."))
            return
