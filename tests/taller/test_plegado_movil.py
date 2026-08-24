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
def test_en_tareas_solo_se_pliegan_las_CERRADAS(client, usuario_factory):
    """Oscar, 2026-08-23: «te dije bien clarito, minimiza la sección de tareas
    cerradas… minimizaste todas».

    Las columnas activas son la razón de entrar a Tareas: plegarlas deja la
    pantalla en una lista de títulos. Lo terminado es lo que ocupa lugar sin que
    nadie lo consulte.
    """
    from apps.el_pizarron.models.estado_tarea import EstadoTarea

    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    # Hace falta un estado terminal para que la sección «Cerradas» exista.
    EstadoTarea.objects.update_or_create(
        slug="completada",
        defaults={"label": "Completada", "terminal": True, "activo": True, "orden": 90},
    )
    html = client.get("/tareas/").content.decode()

    analisis = _analizar(html)
    assert not analisis.mal, f"cuerpos que no son hijos directos: {analisis.mal}"
    assert 'data-movil-plegable="cerradas"' in html, "la sección Cerradas debe plegarse"
    assert 'data-movil-plegable="col-' not in html, "las columnas ACTIVAS no se plegan"
    assert 'data-movil-plegable="filtros"' not in html, (
        "los filtros tampoco: son las pastillas que el runner usa para ver lo suyo"
    )


@pytest.mark.django_db
def test_los_mandados_NUNCA_se_pliegan_en_el_celular(client, usuario_factory):
    """Oscar, 2026-08-23: «quitaste los mandados por completo de móvil. ¿Dónde
    crees que van a armar su ruta, en la computadora?»

    El teléfono ES el lugar de trabajo del runner: el tablero de reparto y el
    widget de «Mis mandados» tienen que estar a la vista, no detrás de un toque.
    """
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)

    en_tareas = client.get("/tareas/?cat=mandados").content.decode()
    assert 'data-movil-plegable="tablero-reparto"' not in en_tareas
    # Y sus acciones se ven sin desplegar nada.
    assert "Planear rutas" in en_tareas or "Mi ruta de hoy" in en_tareas

    propia = client.get("/mandados/").content.decode()
    assert "data-movil-plegable" not in propia, (
        "en su propia pantalla no se pliega nada: ahí entraste justo a verlo"
    )

    dashboard = client.get("/").content.decode()
    assert 'data-movil-plegable="mis-mandados"' not in dashboard


@pytest.mark.django_db
def test_las_asas_no_se_ven_en_escritorio(client, usuario_factory):
    """Cada encabezado que existe SÓLO para plegar va con `md:hidden`; si se
    colara sin él, en escritorio saldría un título duplicado."""
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get("/tareas/").content.decode()

    for m in re.finditer(r"<header[^>]*data-movil-asa[^>]*>", html):
        assert "md:hidden" in m.group(0), f"asa visible en escritorio: {m.group(0)[:120]}"


@pytest.mark.django_db
def test_el_DASHBOARD_no_se_pliega(client, usuario_factory):
    """Oscar, 2026-08-23, viendo la captura: «revierte el dashboard, eso no fue
    lo que yo pedí».

    Plegado, el Dashboard queda en una lista de títulos vacíos: ocho renglones
    que no dicen nada y por los que hay que picar uno por uno. Es la pantalla que
    se abre para VER de un golpe cómo va el día — esconder su contenido la anula.
    Este candado existe para que nadie lo vuelva a intentar «por consistencia».
    """
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    html = client.get("/").content.decode()
    assert "data-movil-plegable" not in html, (
        "el Dashboard se muestra completo, en el celular también"
    )


# ── El bug de fondo: en el celular no se podía llegar a los botones ──────────

@pytest.mark.django_db
def test_el_tablero_de_reparto_trae_tarjetas_para_el_celular(client, usuario_factory):
    """Oscar, 2026-08-23: «las direcciones en los mandados siguen sin guardarse».

    No se guardaban porque **no se podía llegar al botón que las guarda**. Medido
    en un iPhone de 390px con el CSS compilado: en la tabla de siete columnas
    «En camino» y «Entregado» caían en x=682 — fuera de la pantalla — y «Fijar
    lugar» al filo. El backend guardaba bien desde el 23 de agosto; lo que
    faltaba era alcanzar el formulario.

    El arreglo es de MÓDULO: las acciones viven una sola vez
    (`mandados/_acciones.html`) y el tablero las pinta en tabla para escritorio y
    en tarjetas para el celular — así queda arreglado en las dos pantallas que
    lo usan, su propia página y Tareas.
    """
    import datetime as dt

    from apps.el_pizarron.models import Tarea
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto

    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    cli = Cliente.objects.create(razon_social="ACME")
    pro = Proyecto.objects.create(nombre="P", cliente=cli, creado_por=admin)
    Tarea.objects.create(proyecto=pro, titulo="Entrega X", tipo="entrega",
                         creado_por=admin, fecha_compromiso=dt.date.today())

    html = client.get("/mandados/").content.decode()
    # La tabla sólo para escritorio…
    assert "hidden overflow-x-auto" in html and "md:block" in html
    # …y las tarjetas sólo para el celular.
    assert "space-y-3 md:hidden" in html, "faltan las tarjetas del celular"
    # Las acciones, en las dos presentaciones (el partial se incluye dos veces).
    assert html.count("mandado-avanzar") >= 6 or html.count("Entregado") >= 2


def test_las_acciones_del_mandado_viven_en_UN_solo_lugar():
    """Si los formularios se duplicaran en la plantilla, uno se quedaría atrás:
    alguien arregla la tabla y las tarjetas siguen mandando lo viejo (o al revés).
    """
    tablero = (RAIZ / "el-taller" / "templates" / "mandados" / "_tablero.html").read_text()
    acciones = (RAIZ / "el-taller" / "templates" / "mandados" / "_acciones.html").read_text()
    assert "mandado-avanzar" in acciones
    assert "mandado-avanzar" not in tablero, (
        "el tablero no debe traer los formularios: los incluye de _acciones.html"
    )
    assert tablero.count('include "mandados/_acciones.html"') == 2, (
        "las dos presentaciones (tabla y tarjetas) incluyen el MISMO partial"
    )
