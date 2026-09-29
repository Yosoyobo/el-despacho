"""Borra de El Almacén los PDF unidos del papeleo que ya pasaron su plazo.

**Por qué hace falta.** «Unir en un PDF» (Papeleo) deja el resultado en El
Almacén para que quien lo unió lo baje o lo mande al archivo. La sesión de esa
persona recuerda los últimos 10, pero el archivo en disco se quedaba para
siempre: cada unión eran varios megas que nadie iba a volver a pedir.

**Qué borra.** Sólo lo que El Almacén tiene marcado como `temporal` del papeleo
(`papeleo.views.TEMPORAL_UNIDO`) y es más viejo que `--dias` (default 7). Los
unidos de antes de la marca se reconocen por su nombre («Papeleo unido
AAAA-MM-DD HHMM.pdf») y su edad sale de la fecha del archivo.

**Archivado o no, da igual.** Mandarlo al archivo le entrega a Paperless SU
propia copia (`paperless.subir` sube los bytes); desde ahí el almacén ya no le
sirve a nadie. Y si no se archivó, en una semana ya se bajó o ya se olvidó. Lo
que dice si se archivó vive sólo en la sesión de quien lo unió, así que este
repaso tampoco podría distinguirlo.

**Lo que NUNCA borra: lo compartido.** El Almacén está direccionado por
contenido: si alguien bajó el unido y lo anexó a una cotización, los dos apuntan
al MISMO archivo. Dos candados:

1. El Almacén le quita la marca `temporal` en cuanto el mismo contenido se
   guarda por otro camino (`lib.almacen.guardar_fileobj`).
2. Antes de borrar, se busca la llave en TODOS los campos de texto y JSON de la
   base. Si aparece en cualquier registro, se queda. Es el que cubre los unidos
   de antes de la marca y cualquier llave copiada de un registro a otro.

Uso (cron diario, madrugada):
    python manage.py papeleo_limpiar_unidos
    python manage.py papeleo_limpiar_unidos --dry-run      # dice qué borraría
    python manage.py papeleo_limpiar_unidos --dias 30
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from django.core.management.base import BaseCommand

#: El nombre que `papeleo.views.unir` le pone al resultado. Sólo sirve para
#: reconocer los unidos que se guardaron antes de la marca `temporal`.
_NOMBRE_UNIDO = re.compile(r"^Papeleo unido \d{4}-\d{2}-\d{2} \d{4}\.pdf$")

#: Campos que llevan una llave sin que eso la vuelva «en uso». La presencia anota
#: la pantalla en la que anda cada quien (`actividad_kwargs` = `{"clave": …}` de
#: `/papeleo/unido/<clave>/`): quien vio su unido ayer no debe salvarlo para
#: siempre.
_NO_SON_REFERENCIAS = frozenset({
    "cuentas.usuario.actividad_kwargs",
    "cuentas.usuario.actividad_ruta",
})


def _es_unido(datos: dict) -> bool:
    from papeleo.views import TEMPORAL_UNIDO

    if datos.get("temporal") == TEMPORAL_UNIDO:
        return True
    if "temporal" in datos:
        return False  # temporal de otra cosa: no es de este repaso
    return (bool(_NOMBRE_UNIDO.match(str(datos.get("nombre") or "")))
            and datos.get("mime") == "application/pdf")


def _creado(datos: dict, ruta) -> datetime | None:
    texto = datos.get("creado") or ""
    if texto:
        try:
            fecha = datetime.fromisoformat(texto)
            return fecha if fecha.tzinfo else fecha.replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(ruta.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def claves_en_la_base(candidatas: set[str]) -> set[str]:
    """Cuáles de estas llaves aparecen en algún registro de la base.

    Se barren todos los campos de texto (igualdad exacta, que es como se
    guardan las llaves: `archivo_clave`, `imagen_file_id`, `pdf_file_id`…) y los
    JSON (contiene, por si una lista de adjuntos la lleva adentro). Es lento
    para lo que hace, pero corre una vez al día y sólo si hay candidatos.
    """
    from django.apps import apps
    from django.db import models

    if not candidatas:
        return set()
    encontradas: set[str] = set()
    for modelo in apps.get_models():
        meta = modelo._meta
        if meta.proxy or not meta.managed or meta.app_label == "sessions":
            continue
        for campo in meta.concrete_fields:
            if f"{meta.label_lower}.{campo.name}" in _NO_SON_REFERENCIAS:
                continue
            if isinstance(campo, models.CharField | models.TextField):
                if isinstance(campo, models.CharField) and (campo.max_length or 0) < 64:
                    continue  # no cabe una llave de 64
                encontradas |= set(
                    modelo._default_manager.filter(**{f"{campo.name}__in": candidatas})
                    .values_list(campo.name, flat=True))
            elif isinstance(campo, models.JSONField):
                for clave in candidatas - encontradas:
                    if modelo._default_manager.filter(
                            **{f"{campo.name}__icontains": clave}).exists():
                        encontradas.add(clave)
    return encontradas


class Command(BaseCommand):
    help = ("Borra de El Almacén los PDF unidos del papeleo con más de N días "
            "(nunca lo que otro registro comparte).")

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Dice qué borraría, sin borrar nada.")
        parser.add_argument("--dias", type=int, default=7,
                            help="Edad mínima para borrar (default 7).")

    def handle(self, *args, **opts):
        from lib import almacen

        dry = opts["dry_run"]
        dias = max(0, opts["dias"])
        limite = datetime.now(UTC) - timedelta(days=dias)

        viejos: dict[str, dict] = {}
        for datos, ruta in almacen.metas_en_disco():
            if not _es_unido(datos):
                continue
            creado = _creado(datos, ruta)
            if creado is None or creado > limite:
                continue
            viejos[str(datos["id"])] = datos

        compartidos = claves_en_la_base(set(viejos))
        borrados = 0
        for clave, datos in viejos.items():
            nombre = datos.get("nombre") or clave
            if clave in compartidos:
                self.stdout.write(f"  se queda (otro registro lo usa): {nombre}")
                continue
            if dry:
                self.stdout.write(f"  borraría: {nombre}")
            else:
                almacen.borrar(clave)
                self.stdout.write(f"  borrado: {nombre}")
            borrados += 1

        verbo = "Se borrarían" if dry else "Se borraron"
        self.stdout.write(f"{verbo} {borrados} PDF unidos de más de {dias} días; "
                          f"{len(compartidos)} se quedan por estar en uso.")
