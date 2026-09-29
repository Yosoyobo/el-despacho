"""Resolver la configuración de un documento: lo guardado + el borrador + defaults.

Todo lo que dibuja un documento pasa por aquí y recibe un `Config`. Tres usos:

- **el documento de verdad** — `resolver("cotizacion")`: lo guardado;
- **la vista previa sin guardar** — `resolver("cotizacion", borrador=POST)`: el
  formulario de La Gerencia encima de lo guardado, sin tocar la base;
- **el camino de Google** — `resolver(..., basico=True)`: lo visual vuelve al
  documento de siempre (decisión de Oscar: si Chromium se cae, Google saca el
  PDF «con el formato de hoy»), pero el contenido —notas, datos, textos— se
  queda, porque es lo que el cliente está aceptando.

Nunca lanza por un ajuste ilegible: sin tabla, sin fila o con JSON viejo, sale el
documento de siempre. Un ajuste que no se puede leer no debe impedir que salga un
documento.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from html import escape

from . import esquema, tipos

logger = logging.getLogger(__name__)

AMBITOS_GLOBALES = tuple(s.clave for s in esquema.SECCIONES_GLOBALES)

#: Los campos de la hoja general que viven en `ajustes.ConfiguracionDocumento`.
CAMPOS_HOJA = (
    "motor", "tamano_papel", "margen_superior_pt", "margen_inferior_pt",
    "margen_izquierdo_pt", "margen_derecho_pt", "pie_texto", "numerar_paginas",
    "encabezado_texto", "marca_borrador", "interlineado",
)

_TTL = 60.0
_cache: tuple[float, dict] | None = None


def olvidar() -> None:
    """Tira el caché. Lo llama la pantalla al guardar, para que se vea ya."""
    global _cache
    _cache = None
    try:
        from lib.documentos import olvidar_configuracion

        olvidar_configuracion()
    except Exception:  # noqa: BLE001
        pass


def guardado() -> dict:
    """{ambito: valores} de la base, cacheado un minuto. {} si no hay tabla."""
    global _cache
    ahora = time.monotonic()
    if _cache is not None and ahora - _cache[0] < _TTL:
        return _cache[1]
    try:
        from .models import AjusteImprenta

        datos = {a.ambito: dict(a.valores or {}) for a in AjusteImprenta.objects.all()}
    except Exception as exc:  # noqa: BLE001 — sin tabla: el documento de siempre
        logger.debug("imprenta: sin ajustes (%s)", exc)
        datos = {}
    _cache = (ahora, datos)
    return datos


def _hoja_guardada():
    try:
        from ajustes.models import ConfiguracionDocumento

        return ConfiguracionDocumento.obtener()
    except Exception:  # noqa: BLE001
        return None


def secciones_de(ambito: str):
    """Las secciones del esquema de un ámbito (global o tipo)."""
    for s in esquema.SECCIONES_GLOBALES:
        if s.clave == ambito:
            return (s,)
    d = tipos.definicion(ambito)
    return d.secciones() if d else ()


@dataclass
class Config:
    """Lo que necesita una plantilla para dibujar un documento."""

    tipo: str
    marca: dict
    tablas: dict
    despacho: dict
    firma: dict
    doc: dict
    hoja: object | None = None
    basico: bool = False
    #: Para qué se dibuja: `motor` (Chromium, con las fuentes pegadas) o
    #: `pantalla` (vista previa en el navegador, fuentes por /static/).
    destino: str = "motor"
    extra: dict = field(default_factory=dict)

    # ── Piezas de estilo para las plantillas ────────────────────────────────

    @property
    def e(self) -> Estilo:
        return Estilo(self)

    def rotulo(self, clave: str, default: str = "") -> str:
        """El nombre de una columna o rótulo, o el de siempre si quedó vacío."""
        valor = (self.doc.get(f"col_{clave}") or "").strip()
        return valor or default

    def bloque(self, clave: str) -> bool:
        return bool(self.doc.get(f"bloque_{clave}", True))

    def datos_visibles(self) -> list[tuple[str, str]]:
        """[(rótulo, valor)] de los datos del despacho que este tipo enseña."""
        elegidos = set(self.doc.get("datos_despacho") or [])
        filas = []
        d = self.despacho
        for clave, rotulo in esquema.DATOS_DESPACHO:
            if clave not in elegidos:
                continue
            if clave == "bancarios":
                partes = [p for p in (
                    d.get("banco") and f"Banco: {d['banco']}",
                    d.get("titular") and f"Titular: {d['titular']}",
                    d.get("cuenta") and f"Cuenta: {d['cuenta']}",
                    d.get("clabe") and f"CLABE: {d['clabe']}",
                ) if p]
                if partes:
                    filas.append((rotulo, " · ".join(partes)))
                if d.get("instrucciones_pago"):
                    filas.append(("", d["instrucciones_pago"]))
                continue
            valor = (d.get(clave) or "").strip()
            if valor:
                filas.append((rotulo, valor))
        return filas

    def titulo(self, default: str, **valores) -> str:
        """El título del documento: el patrón del ajuste con sus piezas."""
        patron = (self.doc.get("titulo") or "").strip()
        if not patron:
            return default
        return rellenar(patron, valores) or default


def rellenar(patron: str, valores: dict) -> str:
    """`{folio} · {cliente}` → «COT-12 · Optimist». Piezas desconocidas se quitan."""
    import re

    def pieza(m):
        return str(valores.get(m.group(1), "") or "")

    texto = re.sub(r"\{(\w+)\}", pieza, patron)
    return " ".join(texto.split())


class Estilo:
    """El estilo como cadenas CSS listas para `style="…"`.

    Las plantillas son tablas con estilos en línea (así las entiende también
    Google), así que en vez de una hoja de estilos se entregan trozos: `e.th`,
    `e.td`, `e.cuerpo`… **Con los defaults, los trozos son idénticos al CSS que
    la plantilla traía escrito a mano**, que es lo que garantiza que el
    documento de siempre no se mueva.
    """

    def __init__(self, cfg: Config):
        self.c = cfg
        m, t = cfg.marca, cfg.tablas
        self.fuente = esquema.FUENTES.get(m.get("fuente_cuerpo"), esquema.FUENTES["arial"])[1]
        clave_titulos = m.get("fuente_titulos") or m.get("fuente_cuerpo")
        self.fuente_titulos = esquema.FUENTES.get(clave_titulos, esquema.FUENTES["arial"])[1]
        self.texto = m.get("color_texto") or "#000000"
        self.acento = m.get("color_acento") or "#000000"
        self.suave = m.get("color_suave") or "#666666"
        self.cuerpo_pt = m.get("tamano_cuerpo_pt") or 11
        self.titulo_pt = m.get("tamano_titulo_pt") or 11
        self.tabla_pt = m.get("tamano_tabla_pt") or 10
        self.notas_pt = m.get("tamano_notas_pt") or 9
        self.logo_pt = m.get("logo_alto_pt") or 50
        self.logo_alinea = m.get("logo_posicion") or "center"
        grosor = t.get("grosor_borde")
        grosor = 1 if grosor is None else grosor
        self.borde = (f"border:{grosor}px solid {t.get('borde') or '#cccccc'};"
                      if grosor else "border:none;")
        rel = t.get("relleno_pt")
        rel = 1 if rel is None else rel
        self.relleno = f"padding:{rel}pt 5pt;"
        self.fondo_th = t.get("fondo_encabezado") or "#f2f2f2"
        self.texto_th = t.get("texto_encabezado") or "#000000"
        self.cursiva_th = bool(t.get("encabezado_cursiva", True))
        self.negritas_th = bool(t.get("encabezado_negritas", False))
        self.rayado = bool(t.get("rayado", False))
        self.fondo_rayado = t.get("fondo_rayado") or "#f9fafb"

    # Trozos de estilo -------------------------------------------------------

    @property
    def cuerpo(self) -> str:
        from decimal import Decimal

        hoja = self.c.hoja
        inter = getattr(hoja, "interlineado", None) or Decimal("1.02")
        base = (f"font-family: {self.fuente}; color: {self.texto}; "
                f"font-size: {self.cuerpo_pt}pt; line-height: {inter};")
        return base

    @property
    def td(self) -> str:
        """Celda de tabla con línea (el `border:1px solid #cccccc; padding:1pt 5pt;`)."""
        return f"{self.borde} {self.relleno}"

    @property
    def th(self) -> str:
        """Encabezado de tabla: celda + fondo + letra."""
        partes = [self.td, f"background-color:{self.fondo_th};"]
        if self.texto_th.lower() != "#000000":
            partes.append(f"color:{self.texto_th};")
        if self.negritas_th:
            partes.append("font-weight:bold;")
        return " ".join(partes)

    @property
    def th_letra(self) -> str:
        """El `font-style:italic;` que llevan las celdas de encabezado."""
        return "font-style:italic;" if self.cursiva_th else ""

    def fila(self, contador) -> str:
        """Fondo de un renglón alternado (vacío si el rayado está apagado)."""
        try:
            par = int(contador) % 2 == 0
        except (TypeError, ValueError):
            par = False
        return f"background-color:{self.fondo_rayado};" if (self.rayado and par) else ""

    @property
    def titulo(self) -> str:
        m = self.c.marca
        partes = [f"text-align:{m.get('titulo_alineacion') or 'center'};"]
        if self.titulo_pt != self.cuerpo_pt:
            partes.append(f"font-size:{self.titulo_pt}pt;")
        if self.fuente_titulos != self.fuente:
            partes.append(f"font-family:{self.fuente_titulos};")
        if self.acento.lower() != self.texto.lower():
            partes.append(f"color:{self.acento};")
        if m.get("titulo_negritas"):
            partes.append("font-weight:bold;")
        return " ".join(partes)

    @property
    def total(self) -> str:
        return f"color:{self.acento};" if self.acento.lower() != self.texto.lower() else ""

    @property
    def suave_css(self) -> str:
        return f"color:{self.suave};"

    # Fuentes ----------------------------------------------------------------

    def archivos_fuente(self) -> list[str]:
        """Los .ttf que usa este documento (para pegarlos a la conversión)."""
        usados = []
        for clave in {self.c.marca.get("fuente_cuerpo"),
                      self.c.marca.get("fuente_titulos") or ""}:
            datos = esquema.FUENTES.get(clave or "")
            if datos:
                usados.extend(datos[2].values())
        return sorted(set(usados))

    @property
    def fuentes_css(self) -> str:
        """`<style>@font-face…</style>` de las fuentes elegidas. Vacío con Arial.

        Para el motor, la ruta es el nombre del archivo a secas: el archivo viaja
        junto al HTML en la misma petición a Gotenberg. En pantalla, por /static/.
        """
        reglas = []
        for clave in sorted({self.c.marca.get("fuente_cuerpo") or "",
                             self.c.marca.get("fuente_titulos") or ""}):
            datos = esquema.FUENTES.get(clave)
            if not datos or not datos[2]:
                continue
            familia = datos[1].split(",")[0].strip().strip("'")
            for (peso, estilo), archivo in sorted(datos[2].items()):
                url = url_fuente(archivo, self.c.destino)
                reglas.append(
                    f"@font-face{{font-family:'{familia}';src:url('{url}') format('truetype');"
                    f"font-weight:{peso};font-style:{estilo};}}")
        return f"<style>{''.join(reglas)}</style>" if reglas else ""

    # Imágenes ---------------------------------------------------------------

    @property
    def logo_ancho(self) -> int:
        """Ancho del logotipo en puntos, respetando su proporción.

        Va con ancho y alto FIJOS como atributos (el convertidor de Google les
        hace caso), así que hay que calcular el ancho: un logotipo apaisado con
        los dos lados iguales saldría aplastado. El de siempre es cuadrado.
        """
        clave = self.c.marca.get("logo")
        if not clave:
            return self.logo_pt
        try:
            from lib import almacen

            prop = almacen.proporcion(clave)
        except Exception:  # noqa: BLE001
            prop = 0.0
        if prop <= 0:
            return self.logo_pt
        return max(1, int(round(self.logo_pt / prop)))

    @property
    def logo_url(self) -> str:
        return url_imagen(self.c.marca.get("logo"), respaldo="logo")

    @property
    def firma_url(self) -> str:
        return url_imagen(self.c.firma.get("imagen"))


def url_fuente(archivo: str, destino: str) -> str:
    if destino == "motor":
        return archivo
    try:
        from django.templatetags.static import static

        return static(f"imprenta/fuentes/{archivo}")
    except Exception:  # noqa: BLE001
        return f"/static/imprenta/fuentes/{archivo}"


def url_imagen(clave: str | None, *, respaldo: str = "") -> str:
    """URL ABSOLUTA de una imagen de El Almacén (el convertidor la baja de ahí).

    Sin imagen propia, el logotipo de siempre. Absoluta porque quien la baja es
    el convertidor, sin la sesión del usuario (ver `lib/almacen.py`).
    """
    from lib import almacen

    if clave:
        url = almacen.url(clave, "w1000", absoluta=True)
        if url:
            return url
    if respaldo == "logo":
        return f"{almacen.base_publica()}/static/branding/Logo_LC-256.png"
    return ""


def resolver(tipo: str, *, borrador: dict | None = None, basico: bool = False,
             destino: str = "motor") -> Config:
    """La configuración con la que se dibuja un documento de `tipo`.

    `borrador` es `{ambito: valores_limpios}` — lo que trae el formulario de la
    vista previa. Pisa a lo guardado sólo en los ámbitos que trae.
    """
    base = guardado()
    borrador = borrador or {}

    def ambito(nombre):
        valores = {**base.get(nombre, {}), **borrador.get(nombre, {})}
        return esquema.mezclar(secciones_de(nombre), valores, basico=basico)

    hoja = _hoja_guardada()
    if "hoja" in borrador and hoja is not None:
        # Una copia en memoria: la vista previa no toca la fila de la base.
        import copy

        hoja = copy.copy(hoja)
        for clave, valor in borrador["hoja"].items():
            if clave in CAMPOS_HOJA:
                setattr(hoja, clave, valor)

    return Config(
        tipo=tipo,
        marca=ambito("marca"), tablas=ambito("tablas"),
        despacho=ambito("despacho"), firma=ambito("firma"),
        doc=ambito(tipo) if tipos.definicion(tipo) else {},
        hoja=hoja, basico=basico, destino=destino,
    )


def pagina(cfg: Config, default: dict | None = None) -> dict:
    """El diccionario de hoja que espera el generador, con lo propio del tipo.

    Parte de la hoja general (`ConfiguracionDocumento.como_pagina`) y le encima
    lo que este tipo pida distinto: vacío hereda, cero es cero.
    """
    hoja = cfg.hoja
    pag = hoja.como_pagina() if hoja is not None else dict(default or {})
    doc = cfg.doc or {}
    for clave in ("margen_superior_pt", "margen_inferior_pt",
                  "margen_izquierdo_pt", "margen_derecho_pt"):
        valor = doc.get(clave)
        if valor is not None:
            pag[clave] = valor
    tamano = doc.get("tamano_papel")
    if tamano:
        from ajustes.models.documento import TAMANOS

        if tamano in TAMANOS:
            pag["ancho_in"], pag["alto_in"] = TAMANOS[tamano]
    for clave in ("pie_texto", "encabezado_texto"):
        if (doc.get(clave) or "").strip():
            pag[clave] = doc[clave].strip()
    if cfg.destino == "motor" and not cfg.basico:
        pag["fuentes"] = cfg.e.archivos_fuente()
    return pag


def alto_util_pt(cfg: Config, default: int) -> int:
    """El alto que de verdad cabe, con la hoja y los márgenes de este tipo."""
    pag = pagina(cfg)
    alto_in = pag.get("alto_in")
    if not alto_in:
        return default
    return int(alto_in * 72) - int(pag.get("margen_superior_pt") or 0) - int(
        pag.get("margen_inferior_pt") or 0)


def texto_html(texto: str) -> str:
    """Un texto libre del ajuste, escapado y con sus saltos de línea."""
    return escape(texto or "").replace("\n", "<br>")


__all__ = ["AMBITOS_GLOBALES", "CAMPOS_HOJA", "Config", "Estilo", "alto_util_pt",
           "guardado", "olvidar", "pagina", "rellenar", "resolver", "secciones_de",
           "texto_html", "url_imagen"]
