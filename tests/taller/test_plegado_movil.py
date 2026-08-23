"""En el celular y en la PWA, las tarjetas nacen plegadas.

Oscar, 2026-08-23: «En el dashboard en la versión móvil y PWA y las tareas y
mandados, debemos ver esas tarjetas minimizadas siempre por default. Hay mucho
scroll. RECUERDA QUE ES SOLO PARA MOVIL Y PWA.»

Lo que cuidan estos tests, y por qué importa:

1. **Que en escritorio no cambie NADA.** El pliegue vive dentro de una media
   query y las asas son `md:hidden`. Si eso se rompiera, alguien en su
   computadora se encontraría el tablero convertido en una lista de títulos.
2. **Que el cuerpo sea HIJO DIRECTO de su plegable.** El selector del CSS usa
   `>` a propósito, para que una sección plegable dentro de otra no se
   confunda con la de afuera. Si alguien mueve un `data-movil-cuerpo` un nivel
   más adentro, deja de plegarse **en silencio**: no hay error, simplemente no
   funciona en el teléfono, que es donde nadie está mirando el código.
3. **Que las dos copias sigan iguales** (regla §18): el CSS y `ui.js` viven
   dos veces y divergen sin avisar.
"""

from __future__ import annotations

import pathlib
import re
from html.parser import HTMLParser

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
CSS = [
    RAIZ / "el-taller" / "static" / "css" / "input.css",
    RAIZ / "la-gerencia" / "static" / "css" / "input.css",
]
UIJS = [
    RAIZ / "el-taller" / "static" / "js" / "ui.js",
    RAIZ / "la-gerencia" / "static" / "js" / "ui.js",
]

pytestmark = pytest.mark.taller


# ── El mecanismo: la hoja de estilos ────────────────────────────────────────

def _dentro_del_corte_movil(css: str) -> str:
    """Devuelve el CUERPO de la media query de móvil, contando llaves.

    Se cuentan a mano porque un `in` simple encontraría el selector escrito en
    el comentario que documenta el contrato, no la regla que de verdad aplica.
    """
    inicio = css.index("@media (max-width: 767px)")
    abre = css.index("{", inicio)
    nivel, i = 0, abre
    while i < len(css):
        if css[i] == "{":
            nivel += 1
        elif css[i] == "}":
            nivel -= 1
            if nivel == 0:
                return css[abre + 1:i]
        i += 1
    raise AssertionError("la media query de móvil no cierra")


@pytest.mark.parametrize("hoja", CSS, ids=["taller", "gerencia"])
def test_el_pliegue_vive_en_una_media_query_de_movil(hoja):
    cuerpo = _dentro_del_corte_movil(hoja.read_text())
    assert "[data-movil-plegable]" in cuerpo, (
        "el pliegue tiene que estar dentro del corte de móvil: fuera de él, "
        "también se plegaría en escritorio"
    )


@pytest.mark.parametrize("hoja", CSS, ids=["taller", "gerencia"])
def test_solo_se_pliega_el_hijo_directo(hoja):
    css = hoja.read_text()
    assert "[data-movil-plegable]:not([data-abierto]) > [data-movil-cuerpo]" in css, (
        "el selector va con `>`: sin él, una sección plegable dentro de otra "
        "esconde también el cuerpo de la de afuera"
    )
    assert "display: none" in css


def test_el_css_del_pliegue_es_identico_en_las_dos_copias():
    """Regla §18: el CSS vive dos veces y divergiría sin avisar."""
    def bloque(p):
        t = p.read_text()
        i = t.index("LC 2026-08-23 (Oscar): en el celular")
        j = t.index("/* ── V6 Bloque 8", i)
        return t[i:j]

    assert bloque(CSS[0]) == bloque(CSS[1])


# ── El mecanismo: el toggle ─────────────────────────────────────────────────

def test_el_toggle_es_identico_en_las_dos_copias_de_ui_js():
    a, b = (p.read_text() for p in UIJS)
    assert a == b, "ui.js es dual-copy (regla §18) y las dos copias divergieron"


@pytest.mark.parametrize("js", UIJS, ids=["taller", "gerencia"])
def test_el_toggle_no_hace_nada_en_escritorio(js):
    t = js.read_text()
    i = t.index("data-movil-plegable")
    bloque = t[i - 2000:]
    assert "max-width: 767px" in bloque
    assert "if (!esMovil()) return;" in bloque, (
        "sin el corte, picar un encabezado en escritorio plegaría la sección"
    )


@pytest.mark.parametrize("js", UIJS, ids=["taller", "gerencia"])
def test_un_enlace_dentro_del_asa_navega_en_vez_de_plegar(js):
    """El encabezado de «Tareas pendientes» lleva a Tareas; ese clic tiene que
    navegar, no plegar. Sin el filtro, el enlace se volvería inalcanzable."""
    t = js.read_text()
    i = t.index("data-movil-plegable")
    bloque = t[i - 2000:]
    assert "asa.contains(dentro)" in bloque


@pytest.mark.parametrize("js", UIJS, ids=["taller", "gerencia"])
def test_la_memoria_es_de_la_sesion_no_permanente(js):
    """`sessionStorage` y no `localStorage`: al entrar fresco todo está plegado
    —lo que se pidió— pero volver con Atrás no te vuelve a cerrar lo abierto."""
    t = js.read_text()
    i = t.index("despacho-movil-abiertas")
    bloque = t[i - 500:i + 2000]
    assert "sessionStorage" in bloque
    assert "localStorage.setItem('despacho-movil-abiertas'" not in t


# ── Las pantallas ───────────────────────────────────────────────────────────

class _Anidamiento(HTMLParser):
    """Comprueba que cada `data-movil-cuerpo` sea hijo directo de su plegable."""

    VACIOS = {"br", "hr", "img", "input", "meta", "link", "path", "circle", "rect"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pila: list[tuple[str, dict]] = []
        self.bien: list[str] = []
        self.mal: list[str] = []
        self.abiertos: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "data-movil-plegable" in d and "data-movil-abierto" in d:
            self.abiertos.append(d["data-movil-plegable"])
        if "data-movil-cuerpo" in d:
            padre = self.pila[-1] if self.pila else ("", {})
            destino = self.bien if "data-movil-plegable" in padre[1] else self.mal
            destino.append(padre[1].get("data-movil-plegable", f"<{padre[0]}>"))
        texto = self.get_starttag_text() or ""
        if tag not in self.VACIOS and not texto.endswith("/>"):
            self.pila.append((tag, d))

    def handle_endtag(self, tag):
        for i in range(len(self.pila) - 1, -1, -1):
            if self.pila[i][0] == tag:
                del self.pila[i:]
                return


def _analizar(html: str) -> _Anidamiento:
    limpio = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    p = _Anidamiento()
    p.feed(limpio)
    return p


@pytest.mark.django_db
def test_el_dashboard_pliega_sus_tarjetas(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get("/").content.decode()

    analisis = _analizar(html)
    assert not analisis.mal, f"cuerpos que no son hijos directos: {analisis.mal}"
    # Las pesadas: si alguna se cae de la lista, vuelve el scroll que Oscar reportó.
    for seccion in ("acciones", "indicadores", "proyectos", "calendario", "tu-tablero"):
        assert f'data-movil-plegable="{seccion}"' in html, f"falta plegar «{seccion}»"


@pytest.mark.django_db
def test_los_avisos_del_dashboard_nacen_abiertos(client, usuario_factory):
    """«Mis mandados» y las sugerencias sólo aparecen cuando hay algo que
    atender: plegarlos sería esconder el aviso."""
    from ajustes.models import PlantillaCorreo  # noqa: F401  (asegura apps cargadas)

    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get("/").content.decode()

    # Sólo se comprueba lo que esté presente: las dos secciones son condicionales.
    for seccion in ("sugerencias", "mis-mandados"):
        marca = f'data-movil-plegable="{seccion}"'
        if marca in html:
            assert seccion in _analizar(html).abiertos, (
                f"«{seccion}» es un aviso: tiene que nacer abierto"
            )


@pytest.mark.django_db
def test_tareas_pliega_filtros_columnas_y_reparto(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get("/tareas/").content.decode()

    analisis = _analizar(html)
    assert not analisis.mal, f"cuerpos que no son hijos directos: {analisis.mal}"
    assert 'data-movil-plegable="filtros"' in html
    assert 'data-movil-plegable="col-' in html, "las columnas del tablero no se plegan"


@pytest.mark.django_db
def test_el_tablero_de_reparto_se_pliega_dentro_de_tareas(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get("/tareas/?cat=mandados").content.decode()
    assert 'data-movil-plegable="tablero-reparto"' in html


@pytest.mark.django_db
def test_su_propia_pantalla_de_mandados_NO_se_pliega(client, usuario_factory):
    """A `/mandados/` se entra a ver los mandados. Plegarlos ahí dejaría la
    página vacía: el pliegue es para las secciones secundarias."""
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get("/mandados/").content.decode()
    assert 'data-movil-plegable="tablero-reparto"' not in html


@pytest.mark.django_db
def test_las_asas_nuevas_no_se_ven_en_escritorio(client, usuario_factory):
    """Cada encabezado que existe SÓLO para plegar va con `md:hidden`; si se
    colara sin él, en escritorio saldría un título duplicado."""
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get("/").content.decode()

    for m in re.finditer(r"<header[^>]*data-movil-asa[^>]*>", html):
        assert "md:hidden" in m.group(0), f"asa visible en escritorio: {m.group(0)[:120]}"
