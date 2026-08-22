"""Trae a El Almacén los medios que hoy sólo viven en Google Drive.

Recorre las columnas del repo que guardan una llave de archivo, baja de Drive lo
que falte y lo guarda **bajo la misma llave**, así que la base de datos no cambia
(ver `lib/almacen.py`).

Uso:
    python manage.py medios_importar --dry-run          # cuántos y cuánto pesan
    python manage.py medios_importar --tipo imagenes    # primero el camino caliente
    python manage.py medios_importar --limite 200       # por lotes
    python manage.py medios_importar                    # todo

Idempotente y reanudable: lo que ya está en disco se salta. Se puede correr con
el sistema en uso — mientras la importación avanza, cada lectura que llegue a una
llave todavía ausente la trae sola (`almacen.leer`), así que nada se rompe.

`--pausa` deja un respiro entre descargas para no pegarle a la cuota de la API.
"""

from __future__ import annotations

import time

from django.apps import apps as django_apps
from django.core.management.base import BaseCommand

from lib import almacen

# Las columnas que guardan una llave de archivo, con su grupo.
#
# `cotizaciones.Cotizacion.pdf_file_id` NO está a propósito: ese PDF lo genera
# Google convirtiendo nuestro HTML (regla §8) y nadie lo baja — la descarga lo
# vuelve a generar. Traerlo al disco no serviría de nada.
REGISTRO: tuple[tuple[str, str, str, str], ...] = (
    # (grupo, app_label, modelo, campo)
    ("imagenes", "el_catalogo", "Servicio", "imagen_file_id"),
    ("imagenes", "proyectos", "ProyectoProducto", "imagen_file_id"),
    ("imagenes", "proyectos", "ProyectoProductoVersion", "imagen_file_id"),
    ("imagenes", "cotizaciones", "CotizacionItem", "imagen_file_id"),
    ("avatares", "cuentas", "Usuario", "avatar_drive_id"),
    ("comprobantes", "tesoreria", "Ingreso", "drive_file_id"),
    ("comprobantes", "tesoreria", "Egreso", "drive_file_id"),
    ("comprobantes", "tesoreria", "EgresoOcrLog", "drive_file_id"),
    ("cfdi", "facturacion", "Factura", "pdf_file_id"),
    ("cfdi", "facturacion", "Factura", "xml_file_id"),
    ("adjuntos", "recados", "RecadoAdjunto", "drive_file_id"),
    ("adjuntos", "recados", "MensajeAdjunto", "drive_file_id"),
    ("adjuntos", "buzon", "MensajeBuzonAdjunto", "drive_file_id"),
    ("adjuntos", "el_dictado", "MensajeChatAdjunto", "drive_file_id"),
)

GRUPOS = ("imagenes", "avatares", "comprobantes", "cfdi", "adjuntos")


class Command(BaseCommand):
    help = "Importa a El Almacén los medios que sólo están en Google Drive."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tipo", default="todos",
            choices=("todos", *GRUPOS),
            help="Qué grupo importar (default: todos).",
        )
        parser.add_argument("--limite", type=int, default=0,
                            help="Máximo de archivos a bajar en esta corrida (0 = sin tope).")
        parser.add_argument("--pausa", type=float, default=0.25,
                            help="Segundos de espera entre descargas (default 0.25).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Sólo reporta qué falta; no baja nada.")

    def handle(self, *args, **opciones):
        tipo = opciones["tipo"]
        limite = opciones["limite"]
        pausa = opciones["pausa"]
        seco = opciones["dry_run"]

        pendientes = self._pendientes(tipo)
        self.stdout.write(
            f"[Medios] {len(pendientes)} archivo(s) por importar"
            + (f" (grupo «{tipo}»)" if tipo != "todos" else "")
        )
        if seco:
            for grupo, claves in self._por_grupo(pendientes).items():
                self.stdout.write(f"  · {grupo}: {len(claves)}")
            self.stdout.write("[Medios] --dry-run: no se bajó nada.")
            return

        ok = fallidas = 0
        bytes_totales = 0
        for i, (clave, grupo) in enumerate(pendientes, start=1):
            if limite and ok + fallidas >= limite:
                self.stdout.write(f"[Medios] tope de {limite} alcanzado; falta continuar.")
                break
            datos = self._importar(clave)
            if datos is None:
                fallidas += 1
                self.stderr.write(f"  ✕ {grupo} · {clave}")
            else:
                ok += 1
                bytes_totales += int(datos.get("bytes") or 0)
                if ok % 25 == 0:
                    self.stdout.write(f"  … {ok} importados ({i}/{len(pendientes)})")
            if pausa:
                time.sleep(pausa)

        self.stdout.write(
            f"[Medios] terminó · importados={ok} · fallidos={fallidas} · "
            f"peso={bytes_totales / 1_048_576:.1f} MB"
        )
        if fallidas:
            self.stdout.write(
                "[Medios] los fallidos suelen ser archivos ya borrados de Drive. "
                "Vuelve a correr el comando para reintentar; lo importado no se repite."
            )

    # ── Interno ─────────────────────────────────────────────────────────────

    def _pendientes(self, tipo: str) -> list[tuple[str, str]]:
        """`[(clave, grupo)]` sin repetir: una misma llave puede estar en varias
        tablas (la foto del catálogo congelada en tres cotizaciones)."""
        vistas: set[str] = set()
        salida: list[tuple[str, str]] = []
        for grupo, app_label, modelo, campo in REGISTRO:
            if tipo not in ("todos", grupo):
                continue
            try:
                Modelo = django_apps.get_model(app_label, modelo)
            except LookupError:
                self.stderr.write(f"  (aviso) {app_label}.{modelo} no está instalada; se salta.")
                continue
            claves = (Modelo.objects.exclude(**{campo: ""})
                      .exclude(**{f"{campo}__isnull": True})
                      .values_list(campo, flat=True).distinct())
            for clave in claves:
                clave = (clave or "").strip()
                if not clave or clave in vistas:
                    continue
                vistas.add(clave)
                if almacen.existe(clave):
                    continue
                salida.append((clave, grupo))
        return salida

    def _por_grupo(self, pendientes) -> dict[str, list[str]]:
        agrupado: dict[str, list[str]] = {}
        for clave, grupo in pendientes:
            agrupado.setdefault(grupo, []).append(clave)
        return agrupado

    def _importar(self, clave: str) -> dict | None:
        """Baja de Drive y guarda. Nunca lanza: un archivo que ya no existe no
        puede abortar la importación de los otros."""
        try:
            from lib.google_drive import drive

            contenido, mime, nombre = drive.descargar(clave)
        except Exception:  # noqa: BLE001 — borrado, sin permisos, Drive caído
            return None
        if not contenido:
            return None
        try:
            return almacen.guardar_bytes(contenido, mime=mime, nombre=nombre, clave=clave)
        except Exception:  # noqa: BLE001 — disco lleno o ruta mal montada
            return None
