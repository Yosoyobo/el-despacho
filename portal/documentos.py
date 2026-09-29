"""La papelería que el cliente le entrega al despacho — fuente única para las dos apps.

- **La Recepción**: el cliente sube (`subir`), ve lo que ha entregado y qué le
  falta (`documentos_de`, `pendientes_de`).
- **El Taller**: el equipo sube en su nombre, revisa (`revisar`) y aplica lo que
  El Chalán leyó de la CSF (`portal.csf.aplicar`).

**El archivo se revisa por su contenido, no por lo que dice el navegador.** El
`content_type` de una subida lo escribe quien la manda; aquí se miran los
primeros bytes y sólo pasan PDF e imágenes (JPEG, PNG, WebP, HEIC). Eso deja
fuera HTML, SVG, ejecutables y Office con macros, que desde un portal abierto a
gente de fuera no tienen por qué entrar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import (
    ESTADO_APROBADO,
    ESTADO_RECHAZADO,
    ESTADO_RECIBIDO,
    TIPO_COMPROBANTE,
    TIPO_CSF,
    TIPOS_DICT,
    ConfiguracionPortal,
    DocumentoCliente,
)
from .servicios import ErrorPortal, registrar_evento

logger = logging.getLogger(__name__)

#: 25 MB, el mismo tope que el resto de los adjuntos del repo (`lib.adjuntos`).
LIMITE_BYTES = 25 * 1024 * 1024
#: Lo que acepta el campo en el navegador. Es sólo ayuda: el candado es `tipo_real`.
ACEPTA = ".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif,application/pdf,image/*"


def tipo_real(cabecera: bytes) -> str:
    """El MIME por los primeros bytes, o "" si no es PDF ni imagen aceptada."""
    c = cabecera or b""
    if c[:5] == b"%PDF-":
        return "application/pdf"
    if c[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if c[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if c[:4] == b"RIFF" and c[8:12] == b"WEBP":
        return "image/webp"
    if c[4:8] == b"ftyp" and c[8:12] in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heim", b"heis"):
        return "image/heic"
    return ""


def _nombre_seguro(nombre: str) -> str:
    nombre = (nombre or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return "".join(ch for ch in nombre if ch.isprintable())[:200] or "documento"


def validar(archivo) -> tuple[str, str]:
    """(mime, "") si se acepta; ("", mensaje) si no."""
    if archivo is None:
        return "", "Elige el archivo que quieres subir."
    tam = getattr(archivo, "size", 0) or 0
    if tam <= 0:
        return "", "El archivo está vacío."
    if tam > LIMITE_BYTES:
        return "", "El archivo pesa más de 25 MB. Si es un escaneo, bájale la resolución o súbelo en partes."
    try:
        archivo.seek(0)
        cabecera = archivo.read(16)
        archivo.seek(0)
    except Exception:  # noqa: BLE001
        return "", "No pudimos leer el archivo. Vuelve a intentarlo."
    mime = tipo_real(cabecera)
    if not mime:
        return "", "Sólo se aceptan PDF o fotos (JPG, PNG, WebP o HEIC)."
    return mime, ""


# ── Subir ────────────────────────────────────────────────────────────────────


def subir(cliente, tipo: str, archivo, *, acceso=None, usuario=None, nota: str = "",
          factura=None, request=None) -> DocumentoCliente:
    """Guarda el documento. Lanza `ErrorPortal` con un mensaje para la persona.

    `factura` sólo cuenta para el comprobante de pago y tiene que ser de ESTE
    cliente (quien llama la busca por `consultas.factura_de(cliente, pk)`; aquí
    se vuelve a comprobar).
    """
    if tipo not in TIPOS_DICT:
        raise ErrorPortal("Elige qué documento es.")
    mime, error = validar(archivo)
    if error:
        raise ErrorPortal(error)
    if factura is not None and (tipo != TIPO_COMPROBANTE or factura.cliente_id != cliente.pk):
        factura = None

    from lib import adjuntos

    # El nombre y el tipo que dice el navegador no se usan: se guarda con los
    # que acabamos de comprobar.
    archivo.name = _nombre_seguro(getattr(archivo, "name", ""))
    archivo.content_type = mime
    res = adjuntos.subir(archivo, subcarpeta=f"Portal de clientes/{cliente.razon_social}"[:120])
    if not res.ok:
        logger.warning("portal: no se guardó un documento de cliente=%s: %s", cliente.pk, res.error)
        raise ErrorPortal("No pudimos guardar el archivo en este momento. Intenta en unos minutos.")
    data = res.data or {}
    # El nombre es el de ESTA subida, no el que guarda El Almacén: el almacén va
    # por contenido, así que el mismo PDF subido por dos clientes es un solo
    # archivo con el nombre del primero. Sólo cambia la extensión si el almacén
    # convirtió el archivo (una foto HEIC queda en JPEG).
    mime_final = (data.get("mimeType") or mime)[:100]
    nombre = archivo.name
    if mime_final != mime and mime_final == "image/jpeg":
        nombre = nombre.rsplit(".", 1)[0] + ".jpg"

    doc = DocumentoCliente.objects.create(
        cliente=cliente, tipo=tipo, acceso=acceso,
        subido_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        archivo=data.get("id", ""), nombre_archivo=nombre[:200],
        mime=mime_final, tamano=int(data.get("size") or archivo.size or 0),
        espejo_drive=(data.get("espejo_drive") or "")[:128],
        nota=(nota or "").strip()[:2000], factura=factura,
        ia_estado="pendiente" if tipo == TIPO_CSF else "",
    )
    if acceso is not None:
        registrar_evento(acceso, "documento", f"{doc.tipo_nombre} · {doc.nombre_archivo}", request)
    _emitir("portal.documento_subido", doc, usuario, {"tipo": tipo, "factura_id": doc.factura_id})

    from . import avisos

    avisos.documento_subido(doc)
    if tipo == TIPO_CSF:
        _leer_csf_despues(doc.pk)
    return doc


def _leer_csf_despues(doc_id: int) -> None:
    """El Chalán lee la constancia en el fondo, después del commit: la persona no
    espera a la IA para ver que su archivo quedó."""
    def _hacer():
        from .csf import procesar

        procesar(doc_id)

    def _al_confirmar():
        from lib.tareas_fondo import ejecutar_en_fondo

        ejecutar_en_fondo(_hacer)

    try:
        transaction.on_commit(_al_confirmar)
    except Exception:  # noqa: BLE001
        logger.exception("portal: no se pudo programar la lectura de la CSF %s", doc_id)


# ── Revisar (El Taller) ─────────────────────────────────────────────────────


def revisar(doc: DocumentoCliente, usuario, *, aprobar: bool, motivo: str = "") -> DocumentoCliente:
    motivo = (motivo or "").strip()[:500]
    if not aprobar and not motivo:
        raise ErrorPortal("Escribe por qué se rechaza: el cliente lo ve para volver a subirlo.")
    doc.estado = ESTADO_APROBADO if aprobar else ESTADO_RECHAZADO
    doc.motivo_rechazo = "" if aprobar else motivo
    doc.revisado_por = usuario if getattr(usuario, "is_authenticated", False) else None
    doc.revisado_en = timezone.now()
    doc.save(update_fields=["estado", "motivo_rechazo", "revisado_por", "revisado_en"])
    _emitir("portal.documento_revisado", doc, usuario, {"estado": doc.estado})
    return doc


# ── Consultas ────────────────────────────────────────────────────────────────


def documentos_de(cliente, limite: int = 200) -> list[DocumentoCliente]:
    return list(DocumentoCliente.objects.filter(cliente=cliente)
                .select_related("acceso", "subido_por", "revisado_por", "factura")
                .order_by("-creado_en")[:limite])


@dataclass
class Pendiente:
    tipo: str
    nombre: str
    estado: str  # falta | revision | rechazado | listo
    doc: DocumentoCliente | None


def requeridos() -> list[str]:
    try:
        lista = ConfiguracionPortal.obtener().documentos_requeridos or []
    except Exception:  # noqa: BLE001
        return []
    return [t for t in lista if t in TIPOS_DICT]


def pendientes_de(cliente, docs: list[DocumentoCliente] | None = None) -> list[Pendiente]:
    """Lo que se le pide a todo cliente (La Gerencia → Portal) y cómo va cada uno.

    Cuenta el MÁS RECIENTE de cada tipo: si rechazaron uno y subió otro, manda el
    nuevo.
    """
    docs = documentos_de(cliente) if docs is None else docs
    ultimo: dict[str, DocumentoCliente] = {}
    for d in docs:  # vienen del más nuevo al más viejo
        ultimo.setdefault(d.tipo, d)
    filas = []
    for tipo in requeridos():
        d = ultimo.get(tipo)
        if d is None:
            estado = "falta"
        elif d.estado == ESTADO_APROBADO:
            estado = "listo"
        elif d.estado == ESTADO_RECHAZADO:
            estado = "rechazado"
        else:
            estado = "revision"
        filas.append(Pendiente(tipo=tipo, nombre=TIPOS_DICT[tipo], estado=estado, doc=d))
    return filas


def por_revisar(cliente=None):
    qs = DocumentoCliente.objects.filter(estado=ESTADO_RECIBIDO)
    return qs.filter(cliente=cliente) if cliente is not None else qs


def _emitir(tipo: str, doc: DocumentoCliente, actor=None, extra: dict | None = None) -> None:
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz

        autenticado = getattr(actor, "is_authenticated", False)
        payload = {"documento_id": doc.pk, "cliente_id": doc.cliente_id, "tipo": doc.tipo,
                   "acceso_id": doc.acceso_id, "via": "portal" if doc.acceso_id else "taller"}
        payload.update(extra or {})
        emitir(EventoPortavoz(
            tipo=tipo,
            actor_id=getattr(actor, "pk", None) if autenticado else None,
            actor_email=(getattr(actor, "email", None) if autenticado
                         else getattr(doc.acceso, "email", None)),
            payload=payload,
        ))
    except Exception:  # noqa: BLE001
        logger.warning("portal: no se pudo emitir %s", tipo, exc_info=True)


__all__ = [
    "ACEPTA",
    "LIMITE_BYTES",
    "Pendiente",
    "documentos_de",
    "pendientes_de",
    "por_revisar",
    "requeridos",
    "revisar",
    "subir",
    "tipo_real",
    "validar",
]
