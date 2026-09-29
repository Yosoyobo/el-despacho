"""El teclado: la ñ y los acentos, con las dos formas de escribir (LC 2026-09-28).

Oscar escribe la ñ de DOS maneras: con la tecla directa de un teclado ISO y con
Option+n → n. La segunda —igual que el acento ´ + a— es una COMPOSICIÓN: dos
pulsaciones, y entre una y otra el navegador está armando la letra. Cualquier
manejador que en ese hueco reescriba el campo, mueva su tamaño, le robe el foco o
se trague el Enter/Tab/Esc corta la letra a medias.

La regla (ver el encabezado de ``ui.js``):

  * un manejador de ``input`` que ESCRIBE en el campo (``.value =``, tamaño,
    selección, foco, el título que lo desplaza) pregunta primero
    ``despachoComponiendo(e)`` / ``isComposing``;
  * un manejador de teclas que reacciona a Enter/Tab/Esc o hace
    ``preventDefault`` también;
  * los que sólo LEEN para filtrar NO se detienen: en Android el teclado compone
    cada palabra completa y pausarlos congelaría los buscadores.

Y la garantía que lo hace posible: ``ui.js`` reparte un ``input`` sintético al
terminar la composición cuando el navegador no manda uno (Chrome), así quien se
saltó el «componiendo» procesa la letra ya armada.

Este archivo es el CANDADO: recorre todo el JavaScript del repo —archivos y
``<script>`` de plantillas— y falla si un manejador riesgoso no se protege.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

# Dónde vive el JavaScript que escribimos nosotros (lo vendoreado no se toca).
CARPETAS_JS = [
    RAIZ / "el-taller" / "static" / "js",
    RAIZ / "la-gerencia" / "static" / "js",
    RAIZ / "referencias" / "static" / "js",
]
CARPETAS_PLANTILLAS = [
    RAIZ / "el-taller" / "templates",
    RAIZ / "la-gerencia" / "templates",
    RAIZ / "la-recepcion" / "templates",
]
for _app in ("papeleo", "campanas", "referencias", "interfono", "buzon",
             "proximamente", "auth_google", "chalanes", "cuentas", "ajustes"):
    _t = RAIZ / _app / "templates"
    if _t.is_dir():
        CARPETAS_PLANTILLAS.append(_t)

EVENTOS_TEXTO = ("input", "beforeinput")
EVENTOS_TECLA = ("keydown", "keyup", "keypress")

# Un manejador de `input` que hace alguna de estas cosas toca el campo o lo mueve.
_ESCRIBE_CAMPO = re.compile(
    r"\.value\s*=(?!=)"                 # reescribe un valor
    r"|style\.height|scrollHeight|offsetHeight"  # mide o cambia el tamaño
    r"|\.focus\(|\.select\(|setSelectionRange"   # roba el foco o la selección
    r"|selection(?:Start|End)\s*=(?!=)"
    r"|document\.title\s*="             # espejo del título (lo desplaza)
)
# Un manejador de teclas que reacciona a esto le gana al teclado.
_TECLA_RIESGOSA = re.compile(r"""['"](?:Enter|Tab|Escape)['"]|preventDefault""")
_GUARDA = re.compile(r"isComposing|despachoComponiendo|[cC]omponiendo\(")
# Excepción declarada, con su razón escrita en el propio manejador:
#   «teclado: fuera de campos de texto» — nunca corre sobre un campo (borrar una
#       foto con Supr sobre su recuadro);
#   «teclado: no toca el campo que se escribe» — sólo vuelca a un oculto. Pausarlo
#       a media letra no protege nada y, en Android, dejaría la última palabra
#       fuera de lo que se guarda.
_EXENTO = re.compile(r"teclado:\s*(?:fuera de campos de texto|no toca el campo que se escribe)")



@dataclass
class Manejador:
    origen: str
    linea: int
    evento: str
    cuerpo: str


def _quitar_cadenas_y_comentarios(src: str) -> str:
    """Sustituye el contenido de cadenas y comentarios por espacios (conserva el
    largo y los saltos de línea) para poder contar llaves sin tropezar."""
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = src.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif c == "/" and nxt == "*":
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif c in "'\"`":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                j += 1
            for k in range(i + 1, min(j, n)):
                if out[k] != "\n":
                    out[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(out)


def _bloque(src: str, limpio: str, desde: int) -> str:
    """Devuelve el texto (original) desde la primera `{` a partir de `desde`
    hasta su llave de cierre."""
    ini = limpio.find("{", desde)
    if ini == -1:
        return ""
    prof = 0
    for k in range(ini, len(limpio)):
        if limpio[k] == "{":
            prof += 1
        elif limpio[k] == "}":
            prof -= 1
            if prof == 0:
                return src[ini:k + 1]
    return src[ini:]


def _cuerpo_de_funcion_nombrada(src: str, limpio: str, nombre: str) -> str:
    for patron in (rf"function\s+{re.escape(nombre)}\s*\(",
                   rf"(?:var|let|const)\s+{re.escape(nombre)}\s*=\s*(?:function\b|\()"):
        m = re.search(patron, limpio)
        if m:
            return _bloque(src, limpio, m.end())
    return ""


def _manejadores(src: str, origen: str, desplazamiento_linea: int = 0) -> list[Manejador]:
    limpio = _quitar_cadenas_y_comentarios(src)
    res: list[Manejador] = []
    # Se busca sobre el código limpio: un `addEventListener('input'` que viva
    # dentro de un comentario no es un manejador. El nombre del evento se lee del
    # original (en el limpio las cadenas quedaron en blanco).
    for m in re.finditer(r"addEventListener\(\s*", limpio):
        resto = src[m.end():m.end() + 40]
        mm = re.match(r"""(['"])(\w+)\1\s*,\s*""", resto)
        if not mm:
            continue
        evento = mm.group(2)
        if evento not in EVENTOS_TEXTO + EVENTOS_TECLA:
            continue
        pos = m.end() + mm.end()
        siguiente = src[pos:pos + 60]
        ident = re.match(r"([A-Za-z_$][\w$]*)\s*[,)]", siguiente)
        miembro = re.match(r"(?:this|[A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\s*[,)]", siguiente)
        if miembro:
            # this._onKeyCapture → su definición `this._onKeyCapture = (e) => {…}`
            d = re.search(rf"\.{re.escape(miembro.group(1))}\s*=\s*", limpio)
            cuerpo = _bloque(src, limpio, d.end()) if d else ""
        elif ident and ident.group(1) not in ("function", "async"):
            cuerpo = _cuerpo_de_funcion_nombrada(src, limpio, ident.group(1))
        else:
            # function (e) { … }  ·  (e) => { … }  ·  e => expr
            flecha = re.match(r"(?:async\s+)?(?:function\b[^{]*|\(?[\w\s,]*\)?\s*=>\s*)", siguiente)
            cola = src[pos:pos + 400]
            if flecha and "=>" in flecha.group(0) and not cola[flecha.end():].lstrip().startswith("{"):
                fin = cola.find("\n")
                cuerpo = cola[: fin if fin != -1 else len(cola)]
            else:
                cuerpo = _bloque(src, limpio, pos)
        linea = src.count("\n", 0, m.start()) + 1 + desplazamiento_linea
        res.append(Manejador(origen, linea, evento, cuerpo))
    return res


def _es_riesgoso(h: Manejador) -> bool:
    if h.evento in EVENTOS_TEXTO:
        return bool(_ESCRIBE_CAMPO.search(h.cuerpo))
    return bool(_TECLA_RIESGOSA.search(h.cuerpo))


def _scripts_de_plantilla(html: str) -> list[tuple[int, str]]:
    """Bloques <script> inline (sin src) con la línea donde empiezan."""
    out = []
    for m in re.finditer(r"<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S | re.I):
        out.append((html.count("\n", 0, m.start(1)), m.group(1)))
    return out


def recolectar(raiz: Path = RAIZ) -> list[Manejador]:
    manejadores: list[Manejador] = []
    for carpeta in CARPETAS_JS:
        carpeta = raiz / carpeta.relative_to(RAIZ)
        if not carpeta.is_dir():
            continue
        for f in sorted(carpeta.rglob("*.js")):
            if "vendor" in f.parts:
                continue
            manejadores += _manejadores(f.read_text(encoding="utf-8"), str(f.relative_to(raiz)))
    for carpeta in CARPETAS_PLANTILLAS:
        carpeta = raiz / carpeta.relative_to(RAIZ)
        if not carpeta.is_dir():
            continue
        for f in sorted(carpeta.rglob("*.html")):
            html = f.read_text(encoding="utf-8")
            for linea, js in _scripts_de_plantilla(html):
                manejadores += _manejadores(js, str(f.relative_to(raiz)), linea)
    return manejadores


def violaciones(raiz: Path = RAIZ) -> list[str]:
    malos = []
    for h in recolectar(raiz):
        if not _es_riesgoso(h):
            continue
        if _GUARDA.search(h.cuerpo) or _EXENTO.search(h.cuerpo):
            continue
        malos.append(f"{h.origen}:{h.linea} ({h.evento})")
    return malos


def violaciones_inline(raiz: Path = RAIZ) -> list[str]:
    """Atributos on* de las plantillas (onkeydown="…")."""
    malos = []
    for carpeta in CARPETAS_PLANTILLAS:
        carpeta = raiz / carpeta.relative_to(RAIZ)
        if not carpeta.is_dir():
            continue
        for f in sorted(carpeta.rglob("*.html")):
            html = f.read_text(encoding="utf-8")
            for m in re.finditer(r"""\bon(keydown|keyup|keypress|input)\s*=\s*"([^"]*)\"""", html):
                evento, codigo = m.group(1), m.group(2)
                riesgo = (_ESCRIBE_CAMPO if evento == "input" else _TECLA_RIESGOSA).search(codigo)
                if riesgo and not _GUARDA.search(codigo):
                    linea = html.count("\n", 0, m.start()) + 1
                    malos.append(f"{f.relative_to(raiz)}:{linea} (on{evento})")
    return malos


# ── El candado ────────────────────────────────────────────────────────────────


class TestElCandado:
    def test_el_recolector_encuentra_manejadores(self):
        """Si el escaneo dejara de encontrar manejadores, el candado pasaría en
        verde sin revisar nada."""
        hs = recolectar()
        assert len(hs) > 30
        origenes = {h.origen for h in hs}
        assert any("referencias.js" in o for o in origenes)
        assert any("form_widgets.js" in o for o in origenes)
        assert any(o.endswith(".html") for o in origenes)

    def test_sabe_ver_un_manejador_riesgoso_sin_guarda(self):
        js = "el.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); go(); } });"
        (h,) = _manejadores(js, "x.js")
        assert _es_riesgoso(h)
        assert not _GUARDA.search(h.cuerpo)

    def test_sabe_ver_un_manejador_por_nombre(self):
        js = ("function pintar(e) { campo.value = e.target.value.toUpperCase(); }\n"
              "campo.addEventListener('input', pintar);")
        (h,) = _manejadores(js, "x.js")
        assert _es_riesgoso(h)

    def test_un_filtro_que_solo_lee_no_se_detiene(self):
        """Pausar un buscador a media letra lo congelaría en Android."""
        js = "q.addEventListener('input', function () { pintar(q.value); });"
        (h,) = _manejadores(js, "x.js")
        assert not _es_riesgoso(h)

    def test_ningun_manejador_riesgoso_sin_guarda(self):
        malos = violaciones()
        assert not malos, (
            "Estos manejadores escriben en el campo o reaccionan a Enter/Tab/Esc sin "
            "preguntar si el teclado está a media letra (ñ con Option+n, ´ + a). "
            "Agrega `if (window.despachoComponiendo(e)) return;` al inicio:\n  "
            + "\n  ".join(malos)
        )

    def test_ningun_atributo_on_riesgoso_sin_guarda(self):
        malos = violaciones_inline()
        assert not malos, "Atributos on* sin guarda de composición:\n  " + "\n  ".join(malos)


# ── La garantía de ui.js ──────────────────────────────────────────────────────


@pytest.mark.parametrize("app", ["el-taller", "la-gerencia"])
class TestUiJsGarantiza:
    def _ui(self, app):
        return (RAIZ / app / "static" / "js" / "ui.js").read_text(encoding="utf-8")

    def test_expone_la_guarda(self, app):
        t = self._ui(app)
        assert "window.despachoComponiendo = function" in t
        assert "e.isComposing" in t and "keyCode === 229" in t

    def test_sigue_la_composicion_por_sus_eventos(self, app):
        """Safari no siempre marca `isComposing` en las teclas muertas: la marca
        propia sale de compositionstart/compositionend."""
        t = self._ui(app)
        assert "addEventListener('compositionstart'" in t
        assert "addEventListener('compositionend'" in t

    def test_reparte_el_input_que_chrome_no_manda(self, app):
        """En Chrome el último `input` llega todavía «componiendo» y después ya
        no llega otro: sin el sintético, la ñ nunca se procesaría."""
        t = self._ui(app)
        i = t.index("addEventListener('compositionend'")
        tramo = t[i:i + 900]
        assert "dispatchEvent(new Event('input'" in tramo
        assert "__despachoFaltaInput" in tramo

    def test_la_guarda_va_antes_que_todo(self, app):
        """Los demás bloques de ui.js la usan: tiene que estar definida primero."""
        t = self._ui(app)
        assert t.index("window.despachoComponiendo = function") < t.index("--- Sidebar móvil ---")


def test_nadie_pisa_la_guarda_de_ui_js():
    """Una `function` suelta en un script clásico se vuelve propiedad de `window`.

    ``form_widgets.js`` carga DESPUÉS de ``ui.js``: si declarara una función
    llamada ``despachoComponiendo`` reemplazaría la de ui.js y, como la de
    respaldo delega en ``window.despachoComponiendo``, se llamaría a sí misma sin
    fin — cada tecla terminaría en «Maximum call stack» y ningún Esc cerraría
    nada. Pasó en el primer intento de este sprint; esto no deja que vuelva.
    """
    declaradas = []
    for carpeta in CARPETAS_JS:
        for f in sorted(carpeta.rglob("*.js")):
            if "vendor" in f.parts:
                continue
            limpio = _quitar_cadenas_y_comentarios(f.read_text(encoding="utf-8"))
            if re.search(r"\bfunction\s+despachoComponiendo\b"
                         r"|\b(?:var|let|const)\s+despachoComponiendo\b", limpio):
                declaradas.append(str(f.relative_to(RAIZ)))
    assert not declaradas, (
        "Declaran una función llamada `despachoComponiendo` y pisan la de ui.js "
        "(recursión infinita). Usa otro nombre local:\n  " + "\n  ".join(declaradas))


def test_ui_js_sigue_siendo_dual_copy():
    a = (RAIZ / "el-taller" / "static" / "js" / "ui.js").read_text(encoding="utf-8")
    b = (RAIZ / "la-gerencia" / "static" / "js" / "ui.js").read_text(encoding="utf-8")
    assert a == b, "ui.js se desincronizó entre El Taller y La Gerencia (regla §18)"


@pytest.mark.parametrize("nombre", ["form_widgets.js", "geo_picker.js", "textarea_ia.js"])
def test_los_widgets_siguen_siendo_dual_copy(nombre):
    a = (RAIZ / "el-taller" / "static" / "js" / nombre).read_text(encoding="utf-8")
    b = (RAIZ / "la-gerencia" / "static" / "js" / nombre).read_text(encoding="utf-8")
    assert a == b, f"{nombre} se desincronizó entre El Taller y La Gerencia (regla §18)"


# ── Casos concretos ──────────────────────────────────────────────────────────


def test_el_autocompletado_de_referencias_acepta_la_ene():
    """Con [A-Za-z] la ñ cerraba el dropdown: «@toñ» dejaba de buscar a Toño."""
    t = (RAIZ / "referencias" / "static" / "js" / "referencias.js").read_text(encoding="utf-8")
    m = re.search(r"texto\.match\((/.+/)(\w*)\)", t)
    assert m, "no encontré la expresión del token"
    patron, banderas = m.group(1), m.group(2)
    assert "u" in banderas, "sin la bandera u, \\p{L} no significa «letra»"
    assert "\\p{L}" in patron
    assert "A-Za-z0-9_-]" not in patron


@pytest.mark.parametrize("plantilla", [
    "el-taller/templates/el_dictado/chat.html",
    "el-taller/templates/recados/chat_conversacion.html",
])
def test_enter_para_enviar_respeta_la_letra_a_medias(plantilla):
    """Enter manda el mensaje — pero no el Enter que confirma un acento."""
    t = (RAIZ / plantilla).read_text(encoding="utf-8")
    m = re.search(r'onkeydown="([^"]*requestSubmit[^"]*)"', t)
    assert m
    assert "isComposing" in m.group(1) and "229" in m.group(1)


def test_el_escape_a_media_letra_no_cierra_el_modal():
    """Esc para soltar una tecla muerta vaciaba #modal-slot y se llevaba lo escrito."""
    t = (RAIZ / "el-taller" / "static" / "js" / "ui.js").read_text(encoding="utf-8")
    i = t.index("if (e.key === 'Escape') cerrarSlotModal();")
    assert "despachoComponiendo(e)" in t[i - 300:i]
