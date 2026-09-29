"""Las tablas anchas se leen como TARJETAS en el celular (LC 2026-09-28).

Decisión de Oscar: «tarjetas en móvil, todas; en escritorio no cambia nada».
Una tabla de seis columnas mide 640–1000px y un iPhone 390: se leía con scroll
de lado y lo de la derecha (estado, fecha, Ver/Editar) caía fuera de la pantalla.

Es un MÓDULO: basta ``data-tabla-movil`` en la ``<table>``. ``input.css`` apila
cada renglón como tarjeta en ``<md`` y ``ui.js`` pone a cada celda la etiqueta de
su columna (``data-label``) y su papel (``data-movil``) — al cargar, tras cada
swap de HTMX y cuando un script agrega renglones. Ninguna lista duplica su HTML.

Este archivo es el CANDADO: toda ``<table>`` de las plantillas nace con la marca,
salvo las de la lista de abajo, cada una con su razón.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
APPS = ("el-taller", "la-gerencia")

CARPETAS_PLANTILLAS = [RAIZ / "el-taller" / "templates", RAIZ / "la-gerencia" / "templates",
                       RAIZ / "la-recepcion" / "templates"]
for _app in ("papeleo", "campanas", "referencias", "interfono", "buzon", "proximamente",
             "auth_google", "chalanes", "cuentas", "ajustes"):
    if (RAIZ / _app / "templates").is_dir():
        CARPETAS_PLANTILLAS.append(RAIZ / _app / "templates")

# Tablas que NO pasan a tarjetas, y por qué. Agregar aquí exige una razón.
EXENTAS = {
    # El Vigía y El Site comparten estos partials (regla §4 #22): son
    # `table-fixed w-full`, ya caben en cualquier ancho y la pared no es un celular.
    "la-gerencia/templates/site/vivo/_chalanes.html": "El Vigía: table-fixed, ya cabe",
    "la-gerencia/templates/site/vivo/_peticiones.html": "El Vigía: table-fixed, ya cabe",
    "la-gerencia/templates/site/vivo/_procesos.html": "El Vigía: table-fixed, ya cabe",
    # Estados financieros y conciliación: dos columnas (concepto · monto). Caben,
    # y como tarjeta perderían la lectura de columna de montos.
    "el-taller/templates/contaduria/balance_general.html": "concepto · monto, cabe",
    "el-taller/templates/contaduria/estado_resultados.html": "concepto · monto, cabe",
    "el-taller/templates/contaduria/conciliacion_detalle.html": "dos columnas, cabe",
    # Mandados ya trae su propia lista de tarjetas para el celular (S-Movil-Mandados);
    # esta tabla sólo se muestra de `md` para arriba.
    "el-taller/templates/mandados/_tablero.html": "tabla sólo de escritorio (hidden md:block)",
}


def _plantillas():
    for carpeta in CARPETAS_PLANTILLAS:
        yield from sorted(carpeta.rglob("*.html"))


def _tablas(html: str):
    """(línea, etiqueta de apertura, cuerpo hasta su </table>)."""
    for m in re.finditer(r"<table\b[^>]*>", html):
        fin = html.find("</table>", m.end())
        yield html.count("\n", 0, m.start()) + 1, m.group(0), html[m.end(): fin if fin != -1 else None]


def _rel(f: Path) -> str:
    return str(f.relative_to(RAIZ))


# ── El candado ────────────────────────────────────────────────────────────────


def test_el_recorrido_encuentra_tablas():
    """Si el escaneo dejara de encontrar tablas, el candado pasaría sin revisar nada."""
    marcadas = sum(1 for f in _plantillas() for _, tag, _ in _tablas(f.read_text(encoding="utf-8"))
                   if "data-tabla-movil" in tag)
    assert marcadas >= 50


def test_toda_tabla_nace_con_la_marca_movil():
    faltan = []
    for f in _plantillas():
        rel = _rel(f)
        if rel in EXENTAS or f.name == "pdf.html":   # los PDF se imprimen en carta
            continue
        for linea, tag, _ in _tablas(f.read_text(encoding="utf-8")):
            if "data-tabla-movil" not in tag:
                faltan.append(f"{rel}:{linea}")
    assert not faltan, (
        "Estas tablas se leerían con scroll de lado en el celular. Agrega "
        "`data-tabla-movil` a la <table> (y `data-tabla-movil=\"A|B|C\"` si no trae "
        "<thead>), o exéntala en EXENTAS con su razón:\n  " + "\n  ".join(faltan))


def test_las_exentas_siguen_existiendo():
    """Una exención de un archivo que ya no existe esconde el día que vuelva."""
    for rel in EXENTAS:
        assert (RAIZ / rel).is_file(), f"{rel} ya no existe: quítalo de EXENTAS"


def test_una_tabla_sin_thead_trae_sus_etiquetas():
    """Sin <thead> ui.js no tiene de dónde leer las etiquetas: van en el atributo."""
    malas = []
    for f in _plantillas():
        for linea, tag, cuerpo in _tablas(f.read_text(encoding="utf-8")):
            if "data-tabla-movil" not in tag or "<thead" in cuerpo:
                continue
            m = re.search(r'data-tabla-movil="([^"]*)"', tag)
            if not m or "|" not in m.group(1):
                malas.append(f"{_rel(f)}:{linea}")
    assert not malas, "Tablas sin <thead> ni etiquetas en data-tabla-movil:\n  " + "\n  ".join(malas)


# ── El módulo: input.css + ui.js, dual-copy ──────────────────────────────────


def _bloque_css(app: str) -> str:
    t = (RAIZ / app / "static" / "css" / "input.css").read_text(encoding="utf-8")
    i = t.index("las tablas anchas se leen como")
    return t[i:]


@pytest.mark.parametrize("app", APPS)
class TestElModulo:
    def test_css_apila_solo_en_el_celular(self, app):
        css = _bloque_css(app)
        assert "@media (max-width: 767px)" in css
        # En escritorio la tabla es la de siempre: todo lo del módulo vive en la
        # media query (ninguna regla de table[data-tabla-movil] fuera de ella).
        antes_de_media = css[: css.index("@media (max-width: 767px)")]
        assert "table[data-tabla-movil]" not in re.sub(r"/\*.*?\*/", "", antes_de_media, flags=re.S)
        assert "display: grid" in css

    def test_css_pone_la_etiqueta_arriba_de_cada_celda(self, app):
        css = _bloque_css(app)
        assert "[data-label]::before" in css
        assert "content: attr(data-label)" in css

    def test_css_respeta_lo_que_ya_se_escondia(self, app):
        """Una columna `hidden md:table-cell` sigue escondida en el celular."""
        assert ':is(.hidden, [data-movil="oculta"]) { display: none; }' in _bloque_css(app)

    def test_css_no_deja_que_un_campo_se_salga_de_su_celda(self, app):
        """Un <select class="w-48"> en media tarjeta se encimaba en la de al lado."""
        css = _bloque_css(app)
        assert re.search(r":is\(select, textarea, input[^)]*\)[^{]*\{\s*max-width: 100%;", css)

    def test_ui_js_prepara_al_cargar_tras_htmx_y_al_agregar_renglones(self, app):
        t = (RAIZ / app / "static" / "js" / "ui.js").read_text(encoding="utf-8")
        i = t.index("Tablas anchas → tarjetas en el celular")
        js = t[i:]
        assert "table[data-tabla-movil]" in js
        assert "setAttribute('data-label'" in js
        assert "addEventListener('htmx:afterSettle', escanear)" in js
        assert "MutationObserver" in js
        # Sólo pone atributos: nunca reescribe el contenido de una celda (así los
        # formularios y botones son los mismos en escritorio y en el celular).
        assert "innerHTML" not in js and "outerHTML" not in js and "cloneNode" not in js


def test_el_bloque_css_es_dual_copy():
    assert _bloque_css("el-taller") == _bloque_css("la-gerencia"), (
        "El bloque de tablas-tarjeta de input.css se desincronizó (regla §18)")


@pytest.mark.parametrize("partial", ["_tabla_datos.html", "_tabla.html"])
def test_los_partials_de_tabla_son_dual_copy_y_llevan_la_marca(partial):
    a = (RAIZ / "el-taller" / "templates" / "_componentes_tailadmin" / partial).read_text(encoding="utf-8")
    b = (RAIZ / "la-gerencia" / "templates" / "_componentes_tailadmin" / partial).read_text(encoding="utf-8")
    assert a == b, f"{partial} se desincronizó entre El Taller y La Gerencia (regla §18)"
    assert "<table data-tabla-movil" in a


# ── El partial canónico, renderizado ─────────────────────────────────────────


@pytest.fixture
def render_tabla_datos():
    from django.template.loader import render_to_string

    def _r(**ctx):
        return render_to_string("_componentes_tailadmin/_tabla_datos.html", ctx)
    return _r


def test_tabla_datos_pone_etiqueta_y_papel_por_columna(render_tabla_datos):
    html = render_tabla_datos(
        cabeceras=[{"label": "Proyecto", "movil": "titulo"}, {"label": "Cliente"},
                   {"label": "", "movil": "acciones"}],
        filas_html="<tr><td>LC-0001</td><td>Kari Kari</td><td><a href='#'>Ver</a></td></tr>")
    assert "data-tabla-movil" in html
    assert 'data-label="Proyecto" data-movil="titulo"' in html
    assert 'data-label="Cliente" class=' in html      # sin `movil`: ui.js adivina
    assert 'data-movil="acciones"' in html


def test_tabla_datos_scroll_vertical_solo_de_escritorio(render_tabla_datos):
    """En el celular las tarjetas corren con la página: una caja que scrollea
    dentro de otra que también scrollea se pelea con el dedo."""
    html = render_tabla_datos(cabeceras=[{"label": "A"}])
    assert "md:max-h-[70vh] md:overflow-y-auto" in html
    assert re.search(r'class="[^"]*(?<![:\w-])max-h-\[70vh\]', html) is None
