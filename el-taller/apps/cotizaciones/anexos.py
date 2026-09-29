"""Los anexos de la cotización: agregarlos, ordenarlos y pegarlos al PDF.

Ver el modelo (`models/anexo.py`) para el porqué. Aquí vive la mecánica, en un
solo lugar para que las tres puertas por las que entra un anexo —la subida en la
página de la cotización, el papeleo que El Chalán trae del archivo y la herencia
a la versión siguiente— se comporten igual.

Nada de esto lanza hacia la vista: cada operación devuelve qué pasó en español,
porque el que está mirando necesita saber si su ficha quedó o no, no una traza.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction

logger = logging.getLogger(__name__)

#: Una ficha técnica escaneada son unos megas. El tope es el de los adjuntos.
MAX_BYTES = 25 * 1024 * 1024
#: Más de diez anexos en una cotización ya no es una propuesta, es un expediente
#: — y cada uno alarga el PDF que se le manda al cliente.
MAX_ANEXOS = 10


@dataclass
class Resultado:
    ok: bool
    mensaje: str
    #: "success" | "warning" | "error" — el nivel del mensaje para la pantalla.
    nivel: str = "success"
    anexo: object | None = None


def _es_pdf(contenido: bytes) -> bool:
    return b"%PDF" in (contenido or b"")[:1024]


def aceptable(nombre: str) -> bool:
    """¿Se puede anexar? PDF, o un Word/Excel que se convierte."""
    from lib.a_pdf import es_convertible

    return (nombre or "").lower().endswith(".pdf") or es_convertible(nombre)


def agregar(cot, contenido: bytes, nombre: str, usuario=None) -> Resultado:
    """Guarda un anexo en El Almacén y lo pone al final de la lista.

    Un Word/Excel se convierte a PDF aquí mismo; si el convertidor no contesta se
    guarda el original y se reintenta al armar el documento (no se pierde la
    ficha por un servicio caído).
    """
    from lib import almacen
    from lib.a_pdf import es_convertible, preparar

    from .models import CotizacionAnexo

    nombre = (nombre or "anexo").strip()[:200] or "anexo"
    if not contenido:
        return Resultado(False, f"«{nombre}» llegó vacío.", "error")
    if len(contenido) > MAX_BYTES:
        return Resultado(False, f"«{nombre}» pesa más de 25 MB.", "error")
    if not aceptable(nombre):
        return Resultado(False, f"«{nombre}»: sólo se anexan PDF, Word o Excel.",
                         "error")
    if cot.anexos.count() >= MAX_ANEXOS:
        return Resultado(False, f"Una cotización lleva a lo mucho {MAX_ANEXOS} "
                                "anexos.", "error")

    original = nombre
    aviso = ""
    if es_convertible(nombre):
        preparado = preparar(contenido, nombre)
        contenido, nombre, aviso = preparado.contenido, preparado.nombre, preparado.aviso
    elif not _es_pdf(contenido):
        # Termina en .pdf pero no lo es: al unirlo, Gotenberg lo rechazaría y la
        # cotización saldría sin sus anexos. Mejor decirlo ahora.
        return Resultado(False, f"«{nombre}» no parece un PDF válido.", "error")

    es_pdf = _es_pdf(contenido)
    try:
        guardado = almacen.guardar_bytes(
            contenido, nombre=nombre,
            mime="application/pdf" if es_pdf else "application/octet-stream")
    except Exception as exc:  # noqa: BLE001 — disco lleno, permisos
        logger.warning("anexos: no se pudo guardar %s: %s", nombre, exc)
        return Resultado(False, f"No se pudo guardar «{nombre}»: {exc}", "error")

    with transaction.atomic():
        ultimo = cot.anexos.order_by("-orden").values_list("orden", flat=True).first()
        anexo = CotizacionAnexo.objects.create(
            cotizacion=cot,
            orden=(ultimo + 1) if ultimo is not None else 0,
            nombre=nombre,
            nombre_original=original if original != nombre else "",
            archivo_clave=guardado["id"],
            es_pdf=es_pdf,
            tamano=len(contenido),
            subido_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        )

    if aviso:
        return Resultado(True, f"{aviso} Se va a intentar convertir otra vez al "
                               "armar el PDF.", "warning", anexo)
    if original != nombre:
        return Resultado(True, f"«{original}» se anexó convertido a PDF.",
                         "success", anexo)
    return Resultado(True, f"«{nombre}» quedó anexado.", "success", anexo)


def _normalizar_orden(cot) -> list:
    """Deja el orden 0..n-1 sin huecos y devuelve los anexos en ese orden."""
    anexos = list(cot.anexos.order_by("orden", "pk"))
    for i, a in enumerate(anexos):
        if a.orden != i:
            a.orden = i
            a.save(update_fields=["orden"])
    return anexos


def mover(anexo, direccion: str) -> bool:
    """Sube o baja un lugar (botones ↑/↓, decisión del repo sobre arrastrar en
    tablas administrativas). Devuelve si se movió."""
    with transaction.atomic():
        anexos = _normalizar_orden(anexo.cotizacion)
        i = next((n for n, a in enumerate(anexos) if a.pk == anexo.pk), None)
        if i is None:
            return False
        j = i - 1 if direccion == "arriba" else i + 1
        if j < 0 or j >= len(anexos):
            return False
        a, b = anexos[i], anexos[j]
        a.orden, b.orden = b.orden, a.orden
        a.save(update_fields=["orden"])
        b.save(update_fields=["orden"])
    return True


def quitar(anexo) -> None:
    """Quita el anexo de la cotización. **El archivo NO se borra del almacén**:
    la misma llave puede estar en otra versión o en una cotización ya enviada."""
    cot = anexo.cotizacion
    with transaction.atomic():
        anexo.delete()
        _normalizar_orden(cot)


def heredar(de_cot, a_cot) -> int:
    """Copia los anexos a otra cotización (la versión siguiente o un duplicado).

    Se copia la FILA, no el archivo: la llave es la misma, así que diez versiones
    con la misma ficha ocupan un solo archivo en disco. Devuelve cuántos copió.
    """
    from .models import CotizacionAnexo

    if de_cot is None:
        return 0
    n = 0
    for a in de_cot.anexos.order_by("orden", "pk"):
        CotizacionAnexo.objects.create(
            cotizacion=a_cot, orden=a.orden, nombre=a.nombre,
            nombre_original=a.nombre_original, archivo_clave=a.archivo_clave,
            es_pdf=a.es_pdf, tamano=a.tamano, subido_por=a.subido_por,
        )
        n += 1
    return n


def pdfs_para_documento(cot) -> tuple[list[bytes], list[str]]:
    """Los bytes de cada anexo, en orden, listos para pegarse al final.

    Devuelve `(pdfs, avisos)`. Un anexo que no se pueda leer o convertir se
    **salta con aviso** en vez de tumbar el documento: una cotización sin su ficha
    técnica sigue siendo mejor que ninguna cotización.

    Un Word/Excel que no se pudo convertir al subirlo se reintenta aquí; si ahora
    sí, se guarda la versión PDF y la fila se cura (ya no se vuelve a convertir).
    """
    from lib import almacen
    from lib.a_pdf import preparar

    pdfs: list[bytes] = []
    avisos: list[str] = []
    for a in cot.anexos.order_by("orden", "pk"):
        try:
            contenido, _mime, _nombre = almacen.leer(a.archivo_clave)
        except Exception as exc:  # noqa: BLE001
            avisos.append(f"El anexo «{a.nombre}» no se encontró ({exc}); salió sin él.")
            continue

        if not a.es_pdf:
            preparado = preparar(contenido, a.nombre_original or a.nombre)
            if not preparado.convertido:
                avisos.append(f"El anexo «{a.nombre}» no se pudo pasar a PDF; salió "
                              "sin él.")
                continue
            contenido = preparado.contenido
            try:
                guardado = almacen.guardar_bytes(
                    contenido, nombre=preparado.nombre, mime="application/pdf")
                a.archivo_clave = guardado["id"]
                a.nombre = preparado.nombre[:200]
                a.es_pdf = True
                a.tamano = len(contenido)
                a.save(update_fields=["archivo_clave", "nombre", "es_pdf", "tamano"])
            except Exception as exc:  # noqa: BLE001 — se usa igual esta vez
                logger.warning("anexos: no se pudo curar %s: %s", a.pk, exc)

        if not _es_pdf(contenido):
            avisos.append(f"El anexo «{a.nombre}» no es un PDF válido; salió sin él.")
            continue
        pdfs.append(contenido)
    return pdfs, avisos


def anexar_desde_papeleo(cot, documento_id: int, usuario=None) -> Resultado:
    """Trae un documento del archivo del papeleo y lo anexa.

    Es la puerta de El Chalán: en el chat no se suben archivos a una cotización,
    pero sí se puede decir «anéxale la ficha técnica del papeleo #45».
    """
    from lib import paperless

    detalle = paperless.detalle(documento_id)
    if detalle is None:
        return Resultado(False, f"No encontré el documento #{documento_id} en el "
                                "archivo del papeleo.", "error")
    traido = paperless.archivo(documento_id, "download")
    if traido is None:
        return Resultado(False, f"No se pudo traer el documento #{documento_id} del "
                                "archivo.", "error")
    contenido, _tipo = traido
    titulo = (detalle.get("titulo") or f"Documento {documento_id}").strip()
    nombre = titulo if titulo.lower().endswith(".pdf") else f"{titulo}.pdf"
    if not _es_pdf(contenido):
        return Resultado(False, f"«{titulo}» no es un PDF; no se puede anexar.",
                         "error")
    return agregar(cot, contenido, nombre, usuario)


__all__ = [
    "MAX_ANEXOS", "MAX_BYTES", "Resultado", "aceptable", "agregar",
    "anexar_desde_papeleo", "heredar", "mover", "pdfs_para_documento", "quitar",
]
