"""Regenera los derivados de El Almacén a partir de los originales.

Los derivados (`pub/`) son desechables: se rehacen desde `orig/`. Por eso el
respaldo sólo se lleva los originales. Este comando los reconstruye.

Uso:
    python manage.py medios_derivar              # sólo lo que falta
    python manage.py medios_derivar --forzar     # todo, de nuevo
    python manage.py medios_derivar --dry-run

Cuándo sirve: después de un restore que sólo trajo `orig/`, si se cambian los
tamaños de `almacen.VARIANTES`, o si `pub/` se borró a mano. En el día a día no
hace falta — cada imagen se deriva al subirse, y si a El Portero le falta un
archivo, la ruta de respaldo lo rehace sola.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from lib import almacen


class Command(BaseCommand):
    help = "Regenera los derivados de El Almacén desde los originales."

    def add_arguments(self, parser):
        parser.add_argument("--forzar", action="store_true",
                            help="Rehace también los derivados que ya existen.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Sólo reporta cuántos haría.")

    def handle(self, *args, **opciones):
        forzar = opciones["forzar"]
        seco = opciones["dry_run"]

        raiz = almacen.raiz() / "orig"
        if not raiz.is_dir():
            self.stdout.write(f"[Medios] no hay nada en {raiz}.")
            return

        imagenes = 0
        hechos = 0
        saltados = 0
        sin_derivar = 0
        for meta_json in raiz.rglob("meta.json"):
            datos = self._leer(meta_json)
            if not datos:
                continue
            clave = datos.get("id") or ""
            if not clave or not str(datos.get("mime", "")).startswith("image/"):
                continue
            imagenes += 1
            if datos.get("variantes") and not forzar:
                saltados += 1
                continue
            if seco:
                hechos += 1
                continue
            almacen.olvidar_meta(clave)
            variantes = almacen.derivar(clave, forzar=forzar)
            if variantes:
                hechos += 1
            else:
                sin_derivar += 1

        etiqueta = "haría" if seco else "regeneró"
        self.stdout.write(
            f"[Medios] imágenes={imagenes} · {etiqueta}={hechos} · "
            f"ya estaban={saltados} · sin derivar={sin_derivar}"
        )
        if sin_derivar:
            self.stdout.write(
                "[Medios] «sin derivar» son archivos que Pillow no pudo abrir "
                "(formato raro o imagen corrupta). El original se conserva y se "
                "sirve por el proxy autenticado."
            )

    def _leer(self, ruta) -> dict | None:
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — meta a medio escribir o ilegible
            return None
        return datos if isinstance(datos, dict) else None
