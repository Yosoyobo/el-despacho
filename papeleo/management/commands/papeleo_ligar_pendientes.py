"""Liga solo el papeleo que entró hace poco y sigue sin dueño.

**Por qué es un cron y no un paso de la entrada.** Cuando el buzón deja un
documento, Paperless contesta con el id de la TAREA de consumo, no del
documento: su lector de texto corre después y tarda unos minutos. Al momento de
entrar no hay texto que leer ni id que guardar, así que el ligado no puede
correr ahí. Este repaso lo hace cuando el texto ya existe.

**Qué repasa.** Sólo lo que llegó al archivo en las últimas 48 horas
(`--horas`) y **todavía no tiene dueño** en nuestra base. Lo viejo no se toca:
si alguien lo dejó sin ligar, fue a propósito o ya lo va a ligar a mano, y
repasarlo cada 15 minutos para siempre sería trabajo sin fin.

**Mismo criterio cobarde que el resto** (`papeleo.ligado.decidir`): si el texto
menciona a dos clientes, no elige — lo deja sin ligar y dice por qué. Un
documento sin ligar se arregla en diez segundos; uno ligado a quien no es manda
el contrato de alguien a la ficha de otro.

Idempotente: lo que ya quedó ligado sale del repaso siguiente, y ligar dos
veces lo mismo no duplica (lo garantizan los constraints de la tabla).

Uso (cron cada 15 minutos):
    python manage.py papeleo_ligar_pendientes
    python manage.py papeleo_ligar_pendientes --dry-run   # dice qué haría
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Liga a su cliente, proyecto o proveedor el papeleo que entró hace "
            "poco y sigue sin dueño (sólo si no hay duda).")

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Dice qué ligaría, sin guardar nada.")
        parser.add_argument("--horas", type=int, default=48,
                            help="Qué tan atrás mirar (default 48).")

    def handle(self, *args, **opts):
        from ajustes.models import ConfiguracionPapeleo
        from lib import paperless
        from papeleo import ligado
        from papeleo.models import PapeleoLigado

        dry = opts["dry_run"]
        horas = opts["horas"]

        try:
            activo = ConfiguracionPapeleo.obtener().ligar_automatico
        except Exception as exc:  # noqa: BLE001 — sin configuración no se liga
            self.stdout.write(f"No se pudo leer la configuración del papeleo: {exc}")
            return
        if not activo:
            # Se dice y se sale: repasar para luego no guardar nada es gastar
            # llamadas al archivo cada 15 minutos.
            self.stdout.write("El ligado automático está apagado "
                              "(Gerencia → Papeleo). No se repasa nada.")
            return

        if not paperless.esta_configurado():
            self.stdout.write("El archivo de papeleo no está conectado: falta la "
                              "llave de Paperless. No se repasa nada.")
            return

        recientes = paperless.recientes(horas=horas)
        if recientes is None:
            self.stdout.write("El archivo de papeleo no contestó; se reintenta en "
                              "el siguiente repaso.")
            return

        ya_ligados = set(
            PapeleoLigado.objects.filter(
                documento_id__in=[d["id"] for d in recientes])
            .values_list("documento_id", flat=True)
        )
        pendientes = [d for d in recientes if d["id"] not in ya_ligados]

        if not pendientes:
            self.stdout.write(f"Nada pendiente en las últimas {horas} h "
                              f"({len(recientes)} revisado(s), todos con dueño).")
            return

        ligados = 0
        for d in pendientes:
            texto = d.get("texto") or ""
            if not texto.strip():
                # Sin texto el OCR todavía no termina (o el documento es una
                # imagen sin letras). Se reintenta solo en el siguiente repaso.
                self.stdout.write(f"#{d['id']} «{d['titulo']}»: todavía sin texto "
                                  "leído; queda para el siguiente repaso.")
                continue

            if dry:
                veredicto = ligado.decidir(titulo=d["titulo"], texto=texto)
                if veredicto["campo"]:
                    self.stdout.write(f"[dry] #{d['id']} «{d['titulo']}» → se "
                                      f"ligaría a {veredicto['entidad']}.")
                else:
                    self.stdout.write(f"[dry] #{d['id']} «{d['titulo']}»: sin ligar "
                                      f"— {veredicto['motivo']}")
                continue

            r = ligado.ligar_automatico(d["id"], titulo=d["titulo"], texto=texto)
            if r["ligado"] is not None:
                ligados += 1
                self.stdout.write(f"#{d['id']} «{d['titulo']}» → {r['motivo']}")
                _emitir(d, r["ligado"].a_quien)
            else:
                self.stdout.write(f"#{d['id']} «{d['titulo']}»: sin ligar — "
                                  f"{r['motivo']}")

        if not dry:
            self.stdout.write(f"Listo: {ligados} ligado(s) de {len(pendientes)} "
                              f"pendiente(s) en las últimas {horas} h.")


def _emitir(doc: dict, a_quien: str) -> None:
    """Deja rastro en El Portavoz. Best-effort: el cron no se cae por esto."""
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz

        emitir(EventoPortavoz(tipo="papeleo.ligado", actor_id=None, actor_email=None,
                              payload={"documento_id": doc["id"], "a_quien": a_quien,
                                       "origen": "automatico"}))
    except Exception:  # noqa: BLE001
        pass
