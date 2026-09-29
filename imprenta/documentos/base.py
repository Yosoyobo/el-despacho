"""Dibujar, paginar y convertir los documentos de La Imprenta, todos igual."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from ..esquema import DefinicionTipo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Documento:
    """Lo que un tipo de documento declara.

    - `obtener(pk)` → el objeto (lanza `DoesNotExist`).
    - `puede(usuario, objeto)` → si lo puede ver. Con `objeto=None`: si puede ver
      documentos de este tipo en general (para listarlos como ejemplo).
    - `contexto(objeto, cfg)` → lo propio de su plantilla.
    - `piezas(objeto)` → folio, cliente, proyecto, fecha… para el título y el
      nombre del archivo.
    - `ejemplos(limite)` → `[(pk, etiqueta)]` recientes.
    """

    definicion: DefinicionTipo
    plantilla: str
    rotulo: str
    obtener: Callable
    puede: Callable
    contexto: Callable
    piezas: Callable
    ejemplos: Callable
    titulo: Callable
    fecha: Callable = lambda o: None
    marca: Callable = lambda o, cfg: ("", "")
    qr_pago: Callable = lambda o: ""
    extra: dict = field(default_factory=dict)

    @property
    def slug(self) -> str:
        return self.definicion.slug


def configuracion(doc: Documento, *, destino: str = "motor", basico: bool = False):
    from .. import config

    return config.resolver(doc.slug, destino=destino, basico=basico)


def nombre_archivo(doc: Documento, obj, cfg) -> str:
    import re

    piezas = doc.piezas(obj)
    cliente = re.sub(r'[\\/:"*?<>|\s]+', "", piezas.get("cliente", "")).upper()
    default = "-".join(x for x in (doc.rotulo.upper().replace(" ", "_"),
                                   piezas.get("folio", ""), cliente) if x)
    return cfg.nombre_archivo(default, **{**piezas, "CLIENTE": piezas.get("cliente", "").upper()})


def _qr(doc: Documento, obj, cfg) -> tuple[str, str]:
    destino = cfg.doc.get("qr") or ""
    if not destino or cfg.basico:
        return "", ""
    from .. import qr

    if destino == "pago":
        url, texto = doc.qr_pago(obj), "Escanea para pagar en línea"
    else:
        url, texto = qr.url_portal(), "Escanea para verlo en el portal"
    uri = qr.data_uri(url)
    return (uri, texto) if uri else ("", "")


def dibujar(doc: Documento, obj, cfg, *, preview: bool = False, sin_barra: bool = False,
            url_pdf: str = "") -> str:
    """El HTML del documento con la configuración `cfg`."""
    from django.template.loader import render_to_string

    from .. import config

    piezas = doc.piezas(obj)
    qr_uri, qr_texto = _qr(doc, obj, cfg)
    folio = piezas.get("folio", "")
    contexto = {
        "c": cfg, "e": cfg.e,
        "b": {bl.clave: cfg.bloque(bl.clave) for bl in doc.definicion.bloques},
        "r": {col.clave: cfg.rotulo(col.clave, col.default) for col in doc.definicion.columnas},
        "logo_url": cfg.e.logo_url,
        "rotulo_tipo": doc.rotulo.upper(),
        "folio": folio,
        "fecha_documento": doc.fecha(obj),
        "titulo_documento": cfg.titulo(doc.titulo(obj), **piezas),
        "linea_folio": f"Folio {folio}" if (cfg.doc.get("mostrar_folio") and folio) else "",
        "texto_intro": (cfg.doc.get("texto_intro") or "").strip(),
        "texto_cierre": (cfg.doc.get("texto_cierre") or "").strip(),
        "qr_uri": qr_uri, "qr_texto": qr_texto,
        "preview": preview, "sin_barra": sin_barra,
        "hoja_css": config.hoja_css(config.pagina(cfg)),
        "url_descargar": url_pdf if preview else "",
        "nombre_archivo": nombre_archivo(doc, obj, cfg),
    }
    contexto.update(doc.contexto(obj, cfg))
    return render_to_string(doc.plantilla, contexto)


def pagina(doc: Documento, obj, cfg) -> dict:
    """La hoja del documento: la de La Gerencia + su marca + sus metadatos."""
    from .. import config

    pag = config.pagina(cfg)
    marca, color = doc.marca(obj, cfg)
    if marca:
        pag = {**pag, "marca_agua": marca, "marca_color": color}
    piezas = doc.piezas(obj)
    pag["metadatos"] = {
        "Title": cfg.titulo(doc.titulo(obj), **piezas),
        "Author": cfg.despacho.get("nombre") or "Learning Center",
        "Subject": piezas.get("cliente", ""),
        "Keywords": piezas.get("folio", ""),
    }
    return pag


def pdf(doc: Documento, obj) -> bytes | None:
    """El PDF armado por el motor propio. None si no contesta (nunca lanza)."""
    from lib import gotenberg

    try:
        if not gotenberg.disponible():
            return None
        cfg = configuracion(doc)
        return gotenberg.html_a_pdf(dibujar(doc, obj, cfg), pagina=pagina(doc, obj, cfg))
    except Exception:  # noqa: BLE001 — sin PDF, la versión imprimible
        logger.warning("imprenta: no se pudo armar el PDF de %s", doc.slug, exc_info=True)
        return None


__all__ = ["Documento", "configuracion", "dibujar", "nombre_archivo", "pagina", "pdf"]
