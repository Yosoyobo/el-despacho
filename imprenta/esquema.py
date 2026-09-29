"""El esquema de La Imprenta — qué se puede ajustar de los documentos, y cómo.

**Por qué un esquema y no columnas.** Oscar pidió poder editar «todo lo posible»
de los PDF (2026-09-29). Con una columna por ajuste cada perilla nueva sería una
migración, y tres cosas que se piden juntas se volverían difíciles:

- **la vista previa sin guardar**: el formulario se aplica sobre la configuración
  guardada y se dibuja, sin tocar la base;
- **el historial con «volver a esta versión»**: una versión es una foto del
  diccionario entero, así que restaurar es copiarla de vuelta;
- **documentos nuevos**: cada tipo declara sus bloques y columnas y la pantalla
  los pinta sola.

Cada ajuste es un `Campo`, con su tipo, su valor por defecto y sus límites. **El
valor por defecto es el documento de hoy**: quien no toque nada sigue viendo la
cotización exactamente como salía antes de La Imprenta.

**Vacío hereda, cero es cero** (regla del repo). Un margen por tipo que se deja
vacío toma el de la hoja general; un 0 escrito es cero de verdad. Por eso los
enteros «opcionales» guardan `None`, nunca un 0 centinela.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# ── Tipos de campo ──────────────────────────────────────────────────────────

TEXTO = "texto"
TEXTO_LARGO = "texto_largo"
COLOR = "color"
ENTERO = "entero"
BOOL = "bool"
OPCION = "opcion"
IMAGEN = "imagen"
MULTI = "multi"
DECIMAL = "decimal"
#: Una lista ordenada de notas: `[{"id", "texto", "activa"}]`. El id es estable
#: para que cada cotización pueda quitar una en particular aunque se reordenen.
NOTAS = "notas"

_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class Campo:
    clave: str
    tipo: str
    etiqueta: str
    default: object = ""
    ayuda: str = ""
    minimo: int | None = None
    maximo: int | None = None
    largo: int = 200
    opciones: tuple[tuple[str, str], ...] = ()
    #: `None` en lugar del default cuando llega vacío: «vacío hereda».
    opcional: bool = False
    #: Un ajuste VISUAL se descarta cuando el documento lo arma Google (el
    #: camino de respaldo sale «con el formato de hoy», decisión de Oscar). Los
    #: de CONTENIDO —notas, datos, textos— sí viajan: son lo que el cliente acepta.
    visual: bool = True

    def limpiar(self, crudo):
        """El valor listo para guardar, a partir de lo que mandó el formulario.

        Nunca lanza: lo que no se entiende vuelve al default. El formulario del
        navegador se puede manipular, así que aquí no se confía en nada.
        """
        if self.tipo == BOOL:
            return str(crudo or "").strip().lower() in {"1", "on", "true", "si", "sí"}
        if self.tipo == NOTAS:
            return limpiar_notas(crudo)
        if self.tipo == MULTI:
            validas = {c for c, _ in self.opciones}
            valores = crudo if isinstance(crudo, list | tuple) else [crudo]
            return [v for v in valores if v in validas]
        texto = "" if crudo is None else str(crudo).strip()
        if self.tipo == ENTERO:
            if texto == "":
                return None if self.opcional else self.default
            try:
                n = int(Decimal(texto))
            except (InvalidOperation, ValueError):
                return None if self.opcional else self.default
            if self.minimo is not None:
                n = max(self.minimo, n)
            if self.maximo is not None:
                n = min(self.maximo, n)
            return n
        if self.tipo == DECIMAL:
            try:
                n = Decimal(texto.replace(",", "."))
            except (InvalidOperation, ValueError):
                return self.default
            if self.minimo is not None:
                n = max(Decimal(str(self.minimo)), n)
            if self.maximo is not None:
                n = min(Decimal(str(self.maximo)), n)
            return str(n.quantize(Decimal("0.01")))
        if self.tipo == COLOR:
            return texto.lower() if _COLOR.match(texto) else self.default
        if self.tipo == OPCION:
            return texto if texto in {c for c, _ in self.opciones} else self.default
        # TEXTO / TEXTO_LARGO / IMAGEN (la imagen guarda su llave de El Almacén).
        if self.tipo == TEXTO:
            texto = " ".join(texto.split())
        return texto[: self.largo]

    def describir(self, valor) -> str:
        """El valor en palabras, para el historial («Fuente: Arial → Lato»)."""
        if self.tipo == BOOL:
            return "sí" if valor else "no"
        if self.tipo == OPCION:
            return dict(self.opciones).get(valor, str(valor or "—"))
        if self.tipo == MULTI:
            nombres = dict(self.opciones)
            return ", ".join(nombres.get(v, v) for v in (valor or [])) or "ninguno"
        if self.tipo == IMAGEN:
            return "imagen propia" if valor else "la de siempre"
        if self.tipo == NOTAS:
            notas = valor or []
            activas = sum(1 for n in notas if n.get("activa", True))
            return f"{len(notas)} nota(s), {activas} activa(s)"
        if valor in (None, ""):
            return "vacío"
        texto = str(valor)
        return texto if len(texto) <= 60 else texto[:57] + "…"


@dataclass(frozen=True)
class Seccion:
    clave: str
    titulo: str
    ayuda: str
    campos: tuple[Campo, ...]
    #: El permiso que hace falta para cambiarla (acción del módulo `documentos`).
    permiso: str = "editar_estilo"


def limpiar_notas(crudo) -> list[dict]:
    """Normaliza una lista de notas. Las vacías se van; las nuevas reciben id.

    `crudo` es una lista de dicts `{id, texto, activa}` (la arma la vista a
    partir de los campos repetidos del formulario).
    """
    import secrets

    limpias, vistos = [], set()
    for n in crudo if isinstance(crudo, list | tuple) else []:
        if not isinstance(n, dict):
            continue
        texto = " ".join(str(n.get("texto") or "").split())[:400]
        if not texto:
            continue
        ident = re.sub(r"[^a-z0-9]", "", str(n.get("id") or "").lower())[:12]
        if not ident or ident in vistos:
            ident = "n" + secrets.token_hex(3)
        vistos.add(ident)
        limpias.append({"id": ident, "texto": texto, "activa": bool(n.get("activa", True))})
    return limpias[:30]


def notas_de_fabrica(textos) -> list[dict]:
    """Las notas de siempre, con ids estables `n1`, `n2`…"""
    return [{"id": f"n{i}", "texto": t, "activa": True} for i, t in enumerate(textos, 1)]


# ── Tipografía ──────────────────────────────────────────────────────────────
#
# Las fuentes van DENTRO del repo (`static/imprenta/fuentes/`, licencia OFL) y
# viajan pegadas a cada conversión: Chromium no tiene por qué salir a internet
# para armar un documento. Arial es la del documento de siempre.

#: clave → (nombre en pantalla, pila CSS, archivos {(peso, estilo): archivo})
FUENTES: dict[str, tuple[str, str, dict[tuple[str, str], str]]] = {
    "arial": ("Arial (la de siempre)", "Arial, Helvetica, sans-serif", {}),
    "inter": ("Inter", "LCInter, Arial, sans-serif", {
        ("100 900", "normal"): "Inter.ttf", ("100 900", "italic"): "Inter-Italic.ttf"}),
    "montserrat": ("Montserrat", "LCMontserrat, Arial, sans-serif", {
        ("100 900", "normal"): "Montserrat.ttf",
        ("100 900", "italic"): "Montserrat-Italic.ttf"}),
    "lato": ("Lato", "LCLato, Arial, sans-serif", {
        ("400", "normal"): "Lato-Regular.ttf", ("700", "normal"): "Lato-Bold.ttf",
        ("400", "italic"): "Lato-Italic.ttf", ("700", "italic"): "Lato-BoldItalic.ttf"}),
    "poppins": ("Poppins", "LCPoppins, Arial, sans-serif", {
        ("400", "normal"): "Poppins-Regular.ttf", ("700", "normal"): "Poppins-Bold.ttf",
        ("400", "italic"): "Poppins-Italic.ttf", ("700", "italic"): "Poppins-BoldItalic.ttf"}),
    "lora": ("Lora (con remates)", "LCLora, Georgia, serif", {
        ("400 700", "normal"): "Lora.ttf", ("400 700", "italic"): "Lora-Italic.ttf"}),
    "georgia": ("Georgia (con remates, del sistema)", "Georgia, 'Times New Roman', serif", {}),
}

OPCIONES_FUENTE = tuple((clave, datos[0]) for clave, datos in FUENTES.items())
OPCIONES_FUENTE_TITULO = (("", "Igual que el cuerpo"), *OPCIONES_FUENTE)

ALINEACIONES = (("center", "Al centro"), ("left", "A la izquierda"), ("right", "A la derecha"))


# ── Global: la marca ────────────────────────────────────────────────────────

MARCA = Seccion(
    "marca", "Marca",
    "Logotipo, colores y letra. Aplica a todos los documentos.",
    (
        Campo("logo", IMAGEN, "Logotipo", "",
              "PNG o JPG. Si no subes uno, sale el de Learning Center."),
        Campo("logo_alto_pt", ENTERO, "Alto del logotipo", 50,
              "En puntos. 50 es el de siempre; 72 es una pulgada.", 16, 144),
        Campo("logo_posicion", OPCION, "Dónde va el logotipo", "center",
              "", opciones=ALINEACIONES),
        Campo("color_texto", COLOR, "Color del texto", "#000000"),
        Campo("color_acento", COLOR, "Color de acento", "#000000",
              "El del título y el total. Negro es el de siempre."),
        Campo("color_suave", COLOR, "Color secundario", "#666666",
              "Para lo que va en segundo plano: rótulos, notas al pie."),
        Campo("fuente_cuerpo", OPCION, "Letra del documento", "arial",
              "Todas son libres y viajan con el documento.", opciones=OPCIONES_FUENTE),
        Campo("fuente_titulos", OPCION, "Letra de los títulos", "",
              "", opciones=OPCIONES_FUENTE_TITULO),
        Campo("tamano_cuerpo_pt", ENTERO, "Tamaño del texto", 11, "En puntos.", 7, 16),
        Campo("tamano_titulo_pt", ENTERO, "Tamaño del título", 11,
              "11 es igual al texto, como hasta hoy.", 8, 28),
        Campo("titulo_negritas", BOOL, "Título en negritas", False),
        Campo("titulo_alineacion", OPCION, "Alineación del título", "center",
              "", opciones=ALINEACIONES),
        Campo("tamano_tabla_pt", ENTERO, "Tamaño en las tablas", 10, "", 6, 14),
        Campo("tamano_notas_pt", ENTERO, "Tamaño de las notas", 9, "", 6, 12),
    ),
)

TABLAS = Seccion(
    "tablas", "Tablas",
    "Cómo se ven las tablas de conceptos y montos.",
    (
        Campo("borde", COLOR, "Color de las líneas", "#cccccc"),
        Campo("grosor_borde", ENTERO, "Grosor de las líneas", 1,
              "En píxeles. 0 las quita.", 0, 3),
        Campo("fondo_encabezado", COLOR, "Fondo del encabezado", "#f2f2f2"),
        Campo("texto_encabezado", COLOR, "Letra del encabezado", "#000000"),
        Campo("encabezado_cursiva", BOOL, "Encabezado en cursiva", True),
        Campo("encabezado_negritas", BOOL, "Encabezado en negritas", False),
        Campo("rayado", BOOL, "Renglones alternados", False,
              "Pinta un renglón sí y uno no, para seguir la fila con la vista."),
        Campo("fondo_rayado", COLOR, "Color del renglón alternado", "#f9fafb"),
        Campo("relleno_pt", ENTERO, "Aire dentro de cada celda", 1,
              "En puntos, arriba y abajo. 1 es lo apretado de siempre.", 0, 8),
    ),
)

# ── Global: los datos del despacho ──────────────────────────────────────────

DATOS_DESPACHO = (
    ("nombre", "Nombre"), ("razon_social", "Razón social"), ("rfc", "RFC"),
    ("direccion", "Dirección"), ("telefono", "Teléfono"), ("correo", "Correo"),
    ("web", "Sitio web"), ("bancarios", "Datos para depósito"),
)

DESPACHO = Seccion(
    "despacho", "Datos del despacho",
    "Quién emite el documento. Cada tipo de documento elige cuáles enseña.",
    (
        Campo("nombre", TEXTO, "Nombre comercial", "Learning Center", largo=120,
              visual=False),
        Campo("razon_social", TEXTO, "Razón social", "", largo=200, visual=False),
        Campo("rfc", TEXTO, "RFC", "", largo=13, visual=False),
        Campo("direccion", TEXTO_LARGO, "Dirección", "", largo=300, visual=False),
        Campo("telefono", TEXTO, "Teléfono", "", largo=40, visual=False),
        Campo("correo", TEXTO, "Correo", "", largo=120, visual=False),
        Campo("web", TEXTO, "Sitio web", "", largo=120, visual=False),
        Campo("banco", TEXTO, "Banco", "", largo=80, visual=False),
        Campo("titular", TEXTO, "Titular de la cuenta", "", largo=120, visual=False),
        Campo("cuenta", TEXTO, "Número de cuenta", "", largo=30, visual=False),
        Campo("clabe", TEXTO, "CLABE", "", "Las 18 cifras.", largo=18, visual=False),
        Campo("instrucciones_pago", TEXTO_LARGO, "Instrucciones de pago", "",
              "Se imprime junto a los datos para depósito.", largo=400, visual=False),
    ),
    permiso="editar_datos",
)

FIRMA = Seccion(
    "firma", "Firma",
    "Quién firma los documentos que llevan firma.",
    (
        Campo("imagen", IMAGEN, "Firma o sello", "",
              "PNG con fondo transparente, de preferencia.", visual=False),
        Campo("nombre", TEXTO, "Nombre de quien firma", "", largo=120, visual=False),
        Campo("cargo", TEXTO, "Cargo", "", largo=120, visual=False),
    ),
    permiso="editar_datos",
)

SECCIONES_GLOBALES: tuple[Seccion, ...] = (MARCA, TABLAS, DESPACHO, FIRMA)

# ── La hoja general (vive en `ajustes.ConfiguracionDocumento`) ──────────────
#
# No se guarda en `AjusteImprenta`: el generador ya la lee de su tabla. Se
# declara aquí para validarla igual que lo demás y para que el historial la
# pueda contar en palabras.

MOTORES = (
    ("auto", "Automático — Chromium si está disponible, si no Google"),
    ("gotenberg", "Sólo Chromium (aquí en el servidor)"),
    ("google", "Sólo Google Docs (como antes)"),
)

HOJA = Seccion(
    "hoja", "Hoja general",
    "Quién arma el PDF, la hoja y sus márgenes. Aplica a todos los documentos.",
    (
        Campo("motor", OPCION, "Quién arma el PDF", "auto", opciones=MOTORES),
        Campo("tamano_papel", OPCION, "Tamaño de hoja", "carta", opciones=(
            ("carta", "Carta (21.6 × 27.9 cm)"), ("oficio", "Oficio (21.6 × 33 cm)"),
            ("a4", "A4 (21 × 29.7 cm)"))),
        Campo("interlineado", DECIMAL, "Interlineado", "1.02",
              "1.02 es lo más apretado sin que los acentos se encimen; 1.5 es holgado.",
              minimo=0.8, maximo=2.0),
        Campo("margen_superior_pt", ENTERO, "Margen de arriba", 36, "", 0, 216),
        Campo("margen_inferior_pt", ENTERO, "Margen de abajo", 43, "", 0, 216),
        Campo("margen_izquierdo_pt", ENTERO, "Margen izquierdo", 72, "", 0, 216),
        Campo("margen_derecho_pt", ENTERO, "Margen derecho", 72, "", 0, 216),
        Campo("pie_texto", TEXTO, "Pie de página", "", largo=120, visual=False),
        Campo("numerar_paginas", BOOL, "Numerar las páginas", True),
        Campo("encabezado_texto", TEXTO, "Encabezado", "", largo=120, visual=False),
        Campo("marca_borrador", TEXTO, "Marca en documentos sin enviar", "BORRADOR",
              largo=30, visual=False),
    ),
)


# ── Por tipo de documento ───────────────────────────────────────────────────

OPCIONES_TAMANO = (
    ("", "El de la hoja general"),
    ("carta", "Carta (21.6 × 27.9 cm)"),
    ("oficio", "Oficio (21.6 × 33 cm)"),
    ("a4", "A4 (21 × 29.7 cm)"),
)

OPCIONES_QR = (
    ("", "Sin código QR"),
    ("pago", "Al link de pago (si La Caja está encendida)"),
    ("portal", "Al portal del cliente"),
)


def campos_hoja() -> tuple[Campo, ...]:
    """La hoja de un tipo: vacío = la de la hoja general (vacío hereda)."""
    def margen(clave, etiqueta):
        return Campo(clave, ENTERO, etiqueta, None, "Vacío = el de la hoja general.",
                     0, 216, opcional=True)
    return (
        Campo("tamano_papel", OPCION, "Tamaño de hoja", "", opciones=OPCIONES_TAMANO),
        margen("margen_superior_pt", "Margen de arriba"),
        margen("margen_inferior_pt", "Margen de abajo"),
        margen("margen_izquierdo_pt", "Margen izquierdo"),
        margen("margen_derecho_pt", "Margen derecho"),
        Campo("pie_texto", TEXTO, "Pie de página propio", "",
              "Vacío = el de la hoja general.", largo=120, visual=False),
        Campo("encabezado_texto", TEXTO, "Encabezado propio", "",
              "Vacío = el de la hoja general.", largo=120, visual=False),
    )


@dataclass(frozen=True)
class Bloque:
    clave: str
    etiqueta: str
    default: bool = True
    ayuda: str = ""


@dataclass(frozen=True)
class Columna:
    clave: str
    default: str


@dataclass(frozen=True)
class Marca:
    """Una marca de agua que se estampa según el estado del documento."""

    clave: str
    etiqueta: str
    texto: str = ""
    color: str = "#d92d20"


@dataclass(frozen=True)
class DefinicionTipo:
    """Lo que un tipo de documento declara para que la pantalla lo pinte.

    El armado del documento (de dónde salen los datos) vive en `imprenta.tipos`;
    aquí sólo la forma de sus ajustes, para que el esquema no importe modelos.
    """

    slug: str
    nombre: str
    bloques: tuple[Bloque, ...] = ()
    columnas: tuple[Columna, ...] = ()
    titulo_default: str = ""
    #: Qué datos del despacho enseña de fábrica.
    datos_default: tuple[str, ...] = ()
    #: Campos propios del tipo, además de los comunes.
    extra: tuple[Campo, ...] = ()
    #: Dónde se guarda en Drive.
    subcarpeta: str = "Documentos"
    ayuda: str = ""
    #: Las marcas de agua por estado (vacío = sin marca en ese estado).
    marcas: tuple[Marca, ...] = ()
    #: Si el documento tiene vigencia («válida hasta»).
    vigencia: bool = False
    #: Las notas de fábrica. Vacío = el tipo no lleva notas.
    notas_default: tuple[str, ...] = ()
    #: La nota automática del final (p. ej. la forma de pago), si la hay.
    nota_automatica: str = ""
    #: De fábrica: folio visible, firma, aceptación, PDF/A.
    folio_default: bool = False
    firma_default: bool = False
    aceptacion_default: bool = False
    aceptacion_texto: str = "Acepto las condiciones de este documento."
    pdfa_default: bool = False
    #: Qué destinos de QR tienen sentido aquí.
    qr_opciones: tuple[str, ...] = ("", "portal")

    def secciones(self) -> tuple[Seccion, ...]:
        bloques = tuple(
            Campo(f"bloque_{b.clave}", BOOL, b.etiqueta, b.default, b.ayuda, visual=False)
            for b in self.bloques
        )
        columnas = tuple(
            Campo(f"col_{c.clave}", TEXTO, f"Columna «{c.default}»", c.default,
                  "Vacío = el nombre de siempre.", largo=40, visual=False)
            for c in self.columnas
        )
        contenido = (
            Campo("titulo", TEXTO, "Título del documento", self.titulo_default,
                  "Vacío = el de siempre. Acepta {folio}, {cliente}, {proyecto}, {fecha}.",
                  largo=160, visual=False),
            Campo("datos_despacho", MULTI, "Datos del despacho que enseña",
                  list(self.datos_default), opciones=DATOS_DESPACHO, visual=False),
            Campo("texto_intro", TEXTO_LARGO, "Texto de entrada", "",
                  "Va debajo del título, antes del contenido.", largo=1000, visual=False),
            Campo("texto_cierre", TEXTO_LARGO, "Texto de cierre", "",
                  "Va al final, antes de las notas.", largo=1000, visual=False),
        )
        secciones = [Seccion("contenido", "Contenido", "Título y textos propios.", contenido)]
        if bloques:
            secciones.append(Seccion("bloques", "Qué lleva",
                                     "Enciende o apaga cada parte del documento.", bloques))
        if columnas:
            secciones.append(Seccion("columnas", "Nombres de las columnas",
                                     "Cómo se llama cada columna de las tablas.", columnas))
        if self.notas_default:
            notas = [Campo("notas", NOTAS, "Notas", notas_de_fabrica(self.notas_default),
                           "Se editan, se reordenan y se apagan aquí; cada documento "
                           "puede quitar alguna o sumar las suyas.", visual=False)]
            if self.nota_automatica:
                notas.append(Campo("nota_automatica", BOOL, f"Agregar al final: {self.nota_automatica}",
                                   True, "Se arma sola con lo que diga el documento.",
                                   visual=False))
            secciones.append(Seccion("notas", "Notas",
                                     "Las condiciones que acompañan al documento.",
                                     tuple(notas), permiso="editar_notas"))
        firma = (
            Campo("firma", BOOL, "Firma del despacho", self.firma_default,
                  "La imagen, el nombre y el cargo de «Datos y firma».", visual=False),
            Campo("aceptacion", BOOL, "Renglón para que firme el cliente", self.aceptacion_default,
                  "", visual=False),
            Campo("aceptacion_texto", TEXTO, "Texto de aceptación", self.aceptacion_texto,
                  largo=160, visual=False),
        )
        secciones.append(Seccion("firmas", "Firma y aceptación", "", firma))
        qr = tuple(o for o in OPCIONES_QR if o[0] in self.qr_opciones)
        folio = [Campo("mostrar_folio", BOOL, "Enseñar el folio", self.folio_default,
                       "Debajo del título.", visual=False)]
        if self.vigencia:
            folio.append(Campo("mostrar_vigencia", BOOL, "Enseñar «válida hasta»", False,
                               "", visual=False))
        folio.append(Campo("qr", OPCION, "Código QR", "",
                           "Sólo lo pone el motor propio (Chromium).", opciones=qr))
        secciones.append(Seccion("folio", "Folio, vigencia y QR", "", tuple(folio)))
        if self.marcas:
            marcas = []
            for m in self.marcas:
                marcas.append(Campo(f"marca_{m.clave}", TEXTO, f"Marca «{m.etiqueta}»", m.texto,
                                    "Vacío = sin marca.", largo=30, visual=False))
                marcas.append(Campo(f"marca_{m.clave}_color", COLOR, f"Color «{m.etiqueta}»", m.color))
            secciones.append(Seccion("marcas", "Marcas de agua por estado",
                                     "Se estampan cruzadas y tenues en todas las hojas.",
                                     tuple(marcas)))
        archivo = (
            Campo("patron_archivo", TEXTO, "Nombre del archivo", "",
                  "Vacío = el de siempre. Acepta {folio}, {cliente}, {CLIENTE}, {proyecto}, "
                  "{version} y {fecha}.", largo=120, visual=False),
            Campo("pdfa", BOOL, "Guardar como PDF/A (para archivar)", self.pdfa_default,
                  "El formato que se conserva igual por años. Sólo con el motor propio.",
                  visual=False),
        )
        secciones.append(Seccion("archivo", "El archivo", "", archivo))
        if self.extra:
            secciones.append(Seccion("extra", "Más ajustes", "", self.extra))
        secciones.append(Seccion("hoja", "Hoja de este documento",
                                 "Sólo si este documento necesita algo distinto a la hoja general.",
                                 campos_hoja()))
        return tuple(secciones)

    def campos(self) -> tuple[Campo, ...]:
        return tuple(c for s in self.secciones() for c in s.campos)


# ── Utilidades del esquema ──────────────────────────────────────────────────


def defaults(secciones) -> dict:
    return {c.clave: (list(c.default) if isinstance(c.default, list | tuple) else c.default)
            for s in secciones for c in s.campos}


def mezclar(secciones, guardado: dict | None, *, basico: bool = False) -> dict:
    """Lo guardado sobre los defaults. `basico=True` descarta lo visual.

    Una clave que ya no existe en el esquema se ignora (un ajuste retirado no
    rompe nada); una que falta toma su default (un ajuste nuevo nace con el
    documento de siempre).
    """
    guardado = guardado or {}
    valores = {}
    for s in secciones:
        for c in s.campos:
            if c.clave in guardado and not (basico and c.visual):
                valores[c.clave] = guardado[c.clave]
            else:
                valores[c.clave] = (list(c.default) if isinstance(c.default, list | tuple)
                                    else c.default)
    return valores


def limpiar(secciones, datos, prefijo: str = "") -> dict:
    """Lee un formulario (QueryDict o dict) y devuelve los valores limpios.

    `prefijo` separa los ámbitos dentro de un mismo formulario
    (`marca__color_acento`, `cotizacion__bloque_fotos`…).
    """
    valores = {}
    for s in secciones:
        for c in s.campos:
            nombre = f"{prefijo}{c.clave}"
            if c.tipo == NOTAS:
                valores[c.clave] = c.limpiar(_notas_del_formulario(datos, nombre))
                continue
            if c.tipo == MULTI:
                crudo = datos.getlist(nombre) if hasattr(datos, "getlist") else datos.get(nombre, [])
            else:
                crudo = datos.get(nombre)
            valores[c.clave] = c.limpiar(crudo)
    return valores


def _notas_del_formulario(datos, nombre: str) -> list[dict]:
    """Las notas vienen en campos repetidos, en el orden de la pantalla:
    `<nombre>__id`, `<nombre>__texto` y `<nombre>__activa` (valor = id)."""
    if hasattr(datos, "getlist"):
        ids, textos = datos.getlist(f"{nombre}__id"), datos.getlist(f"{nombre}__texto")
        activas = set(datos.getlist(f"{nombre}__activa"))
    else:
        crudo = datos.get(nombre)
        return list(crudo) if isinstance(crudo, list | tuple) else []
    notas = []
    for i, texto in enumerate(textos):
        ident = ids[i] if i < len(ids) else ""
        notas.append({"id": ident, "texto": texto, "activa": (ident in activas) if ident else True})
    return notas


def diferencias(secciones, antes: dict, despues: dict) -> list[str]:
    """Los cambios en palabras, para el historial."""
    cambios = []
    for s in secciones:
        for c in s.campos:
            a, d = (antes or {}).get(c.clave, c.default), (despues or {}).get(c.clave, c.default)
            if _norm(a) != _norm(d):
                cambios.append(f"{c.etiqueta}: {c.describir(a)} → {c.describir(d)}")
    return cambios


def _norm(v):
    """Para comparar: las listas simples sin orden; las de notas, con orden."""
    if isinstance(v, list | tuple):
        if any(isinstance(x, dict) for x in v):
            return [dict(x) for x in v]
        return sorted(v)
    return v


__all__ = [
    "BOOL", "COLOR", "DECIMAL", "DESPACHO", "HOJA", "ENTERO", "FIRMA", "FUENTES", "IMAGEN", "MARCA",
    "MULTI", "NOTAS", "OPCION", "SECCIONES_GLOBALES", "TABLAS", "TEXTO", "TEXTO_LARGO",
    "Bloque", "Campo", "Columna", "DefinicionTipo", "Marca", "Seccion", "defaults",
    "diferencias", "limpiar", "mezclar",
]
