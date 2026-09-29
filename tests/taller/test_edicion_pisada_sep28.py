"""El aviso de edición pisada (S-Pendientes-Sep28 · Deploy 3).

Decisión de Oscar: si dos personas —o dos ventanas de la misma— editan lo mismo,
el último guardado ya NO pisa al otro en silencio. En Proyecto, Cotización,
Factura, Cliente, Producto y Proveedor el servidor compara lo que había cuando
se abrió la pantalla (el *testigo*, un campo oculto) contra lo que hay hoy y lo
que se manda; si guardar reescribiría lo de alguien más, **no guarda** y
pregunta: «Ver su versión», «Guardar la mía de todos modos», «Copiar lo mío y
recargar».

Las pruebas van como el navegador: abren la pantalla, leen el formulario TAL
COMO SE PINTÓ (campos, formsets, el testigo) con un lector de HTML, cambian un
campo y lo mandan. Así un testigo que no se pinte, o que se pinte mal, truena
aquí y no en producción. Por cada modelo:

- **choque**: A y B abren; B guarda; A guarda encima → 409, no se guarda, el
  aviso dice quién fue y ofrece las tres salidas;
- **forzar**: A reenvía con «Guardar la mía» → se guarda lo de A;
- **sin choque**: una sola persona guarda como siempre; y dos personas en
  campos DISTINTOS no chocan (la comparación es campo por campo).

Y en el proyecto, que se autoguarda: dos autoguardados seguidos de la misma
ventana no chocan consigo mismos (el testigo nuevo regresa por OOB), y el alta
inline de un producto no se duplica en el autoguardado siguiente (bug V8).
"""

from __future__ import annotations

from decimal import Decimal
from html.parser import HTMLParser

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

HTMX = {"HTTP_HX_REQUEST": "true"}
AVISO = "Alguien más cambió esto mientras lo editabas"
BOTONES = ("Ver su versión", "Guardar la mía de todos modos", "Copiar lo mío y recargar")


# ── Lo que el navegador mandaría ──────────────────────────────────────────


class _LectorDeFormularios(HTMLParser):
    """Junta los campos de cada <form> como los enviaría un navegador.

    Sabe lo justo: inputs (casillas y radios sólo marcados), selects (la opción
    elegida o la primera), textareas, el atributo `form=`, y que lo que vive
    dentro de un <template> (la tarjeta vacía que clona el JS) no se envía."""

    _NO_SE_ENVIAN = {"submit", "button", "image", "reset", "file"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.formas: list[dict] = []        # {"id": ..., "campos": [(nombre, valor)]}
        self.sueltos: list[tuple[str, str]] = []
        self._actual: int | None = None
        self._en_template = 0
        self._textarea: tuple[str, int | None] | None = None
        self._texto: list[str] = []
        self._select: dict | None = None
        self._opcion: dict | None = None

    def _destino(self, attrs) -> int | None:
        dueno = attrs.get("form")
        if dueno:
            for i, f in enumerate(self.formas):
                if f["id"] == dueno:
                    return i
            return None
        return self._actual

    def _agregar(self, destino, nombre, valor):
        if destino is None:
            self.sueltos.append((nombre, valor))
        else:
            self.formas[destino]["campos"].append((nombre, valor))

    def handle_starttag(self, tag, attrs_lista):
        attrs = dict(attrs_lista)
        if tag == "template":
            self._en_template += 1
            return
        if self._en_template:
            return
        if tag == "form":
            self.formas.append({"id": attrs.get("id") or "", "campos": []})
            self._actual = len(self.formas) - 1
            return
        nombre = attrs.get("name")
        if tag == "input" and nombre and "disabled" not in attrs:
            tipo = (attrs.get("type") or "text").lower()
            if tipo in self._NO_SE_ENVIAN:
                return
            if tipo in ("checkbox", "radio"):
                if "checked" in attrs:
                    self._agregar(self._destino(attrs), nombre, attrs.get("value") or "on")
                return
            self._agregar(self._destino(attrs), nombre, attrs.get("value") or "")
        elif tag == "textarea" and nombre and "disabled" not in attrs:
            self._textarea = (nombre, self._destino(attrs))
            self._texto = []
        elif tag == "select" and nombre and "disabled" not in attrs:
            self._select = {"nombre": nombre, "destino": self._destino(attrs),
                            "multiple": "multiple" in attrs, "opciones": []}
        elif tag == "option" and self._select is not None:
            self._opcion = {"valor": attrs.get("value"), "texto": [],
                            "elegida": "selected" in attrs}

    def handle_endtag(self, tag):
        if tag == "template":
            self._en_template = max(0, self._en_template - 1)
            return
        if self._en_template:
            return
        if tag == "form":
            self._actual = None
        elif tag == "textarea" and self._textarea is not None:
            texto = "".join(self._texto)
            if texto.startswith("\n"):
                texto = texto[1:]
            self._agregar(self._textarea[1], self._textarea[0], texto)
            self._textarea = None
        elif tag == "option" and self._opcion is not None and self._select is not None:
            self._cerrar_opcion()
        elif tag == "select" and self._select is not None:
            if self._opcion is not None:
                self._cerrar_opcion()
            ops = self._select["opciones"]
            elegidas = [o for o in ops if o["elegida"]]
            if not self._select["multiple"] and not elegidas and ops:
                elegidas = [ops[0]]
            for o in elegidas:
                self._agregar(self._select["destino"], self._select["nombre"], o["valor"])
            self._select = None

    def _cerrar_opcion(self):
        o = self._opcion
        valor = o["valor"] if o["valor"] is not None else "".join(o["texto"]).strip()
        self._select["opciones"].append({"valor": valor, "elegida": o["elegida"]})
        self._opcion = None

    def handle_data(self, data):
        if self._en_template:
            return
        if self._textarea is not None:
            self._texto.append(data)
        elif self._opcion is not None:
            self._opcion["texto"].append(data)


def _a_dict(campos) -> dict[str, list[str]]:
    datos: dict[str, list[str]] = {}
    for nombre, valor in campos:
        datos.setdefault(nombre, []).append(valor)
    return datos


def _form_con_testigo(html: str) -> dict[str, list[str]]:
    """Los campos del <form> que lleva el testigo, como los enviaría el navegador."""
    lector = _LectorDeFormularios()
    lector.feed(html)
    for f in lector.formas:
        if any(n == "_edicion_testigo" for n, _ in f["campos"]):
            return _a_dict(f["campos"])
    raise AssertionError("la pantalla no pintó el testigo dentro de su formulario")


def _sueltos(html: str) -> dict[str, list[str]]:
    """Los campos de un fragmento OOB (no trae <form>)."""
    lector = _LectorDeFormularios()
    lector.feed(html)
    return _a_dict(lector.sueltos)


def _abrir(cliente: Client, url: str) -> dict[str, list[str]]:
    resp = cliente.get(url)
    assert resp.status_code == 200, f"GET {url} → {resp.status_code}"
    return _form_con_testigo(resp.content.decode())


def _con(datos: dict, **cambios) -> dict:
    nuevo = {k: list(v) for k, v in datos.items()}
    for k, v in cambios.items():
        nuevo[k] = [v]
    return nuevo


def _forzado(datos: dict) -> dict:
    return _con(datos, _edicion_forzar="1")


def _guardo(resp) -> bool:
    return resp.status_code in (200, 302) and AVISO not in resp.content.decode()


def _assert_choque(resp, quien: str, lo_mio: str, *, htmx=False):
    assert resp.status_code == 409, f"esperaba el choque (409), llegó {resp.status_code}"
    cuerpo = resp.content.decode()
    assert AVISO in cuerpo
    assert quien in cuerpo, "el aviso no dice quién cambió el registro"
    for b in BOTONES:
        assert b in cuerpo, f"falta el botón «{b}»"
    # «Copiar lo mío»: lo que la persona escribió, legible, va en el aviso.
    assert lo_mio in cuerpo, "lo que escribió la persona no va en el portapapeles"
    if htmx:
        assert resp.headers.get("X-Edicion-Choque") == "1"
        assert 'hx-swap-oob="true"' in cuerpo


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def dos(usuario_factory):
    """Dos personas con permiso de editar, cada una en su navegador."""
    ana = usuario_factory(rol="super_admin")
    beto = usuario_factory(rol="super_admin")
    ana.nombre_completo, beto.nombre_completo = "Ana Aguirre", "Beto Barrios"
    ana.save(update_fields=["nombre_completo"])
    beto.save(update_fields=["nombre_completo"])
    ca, cb = Client(), Client()
    ca.force_login(ana)
    cb.force_login(beto)
    return {"ana": ana, "beto": beto, "ca": ca, "cb": cb}


# ── Los seis modelos ──────────────────────────────────────────────────────
#
# Cada caso dice cómo crear el registro, qué pantalla lo edita, qué campo se
# pelean Ana y Beto y si esa pantalla se autoguarda (HTMX) o se guarda con el
# botón (POST normal). El proyecto y el proveedor tienen las dos.


def _crear_cliente(f):
    return f["cliente_factory"](razon_social="Heladería Original")


def _crear_proyecto(f):
    return f["proyecto_factory"](nombre="Menú de temporada")


def _crear_cotizacion(f):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    proyecto = f["proyecto_factory"](nombre="Menú de temporada")
    cot = Cotizacion.objects.create(
        cliente=proyecto.cliente, proyecto=proyecto, titulo="Menús de verano",
        regimen_fiscal="iva", creado_por=f["usuario_factory"](rol="super_admin"))
    CotizacionItem.objects.create(
        cotizacion=cot, orden=0, descripcion="Diseño de menú",
        cantidad=Decimal("2"), unidad="pieza", precio_unitario=Decimal("1500.00"))
    return cot


def _crear_factura(f):
    from apps.facturacion.models import Factura, FacturaItem
    fac = Factura.objects.create(
        cliente=f["cliente_factory"](), titulo="Factura de verano",
        regimen_fiscal="iva", creado_por=f["usuario_factory"](rol="super_admin"),
        concepto="Diseño de menús", notas="Notas originales")
    FacturaItem.objects.create(
        factura=fac, orden=0, descripcion="Diseño de menú", cantidad=Decimal("1"),
        unidad="pieza", precio_unitario=Decimal("1000.00"))
    return fac


def _crear_servicio(f):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Impresos", defaults={"orden": 10})
    return Servicio.objects.create(nombre="Menú laminado", precio_base="100",
                                   costo="40", categoria=cat)


def _crear_proveedor(f):
    from apps.el_catalogo.models import Proveedor
    return Proveedor.objects.create(razon_social="Crea Blanks", activo=True,
                                    nombre_contacto="Original")


CASOS = {
    # nombre: (crear, nombre de la URL, campo en pelea, autoguardado HTMX)
    "cliente": (_crear_cliente, "cartera-editar", "razon_social", False),
    "proyecto-autoguardado": (_crear_proyecto, "proyectos-detalle", "nombre", True),
    "proyecto-editar": (_crear_proyecto, "proyectos-editar", "nombre", False),
    "cotizacion": (_crear_cotizacion, "cotizaciones:editar", "titulo", False),
    "factura": (_crear_factura, "facturacion:editar", "notas", False),
    "producto": (_crear_servicio, "catalogo-editar", "nombre", False),
    "proveedor-autoguardado": (_crear_proveedor, "catalogo-proveedor-detalle",
                               "nombre_contacto", True),
    "proveedor-editar": (_crear_proveedor, "catalogo-proveedor-editar",
                         "nombre_contacto", False),
}


@pytest.fixture(params=sorted(CASOS))
def caso(request, cliente_factory, proyecto_factory, usuario_factory):
    crear, url_nombre, campo, htmx = CASOS[request.param]
    obj = crear({"cliente_factory": cliente_factory, "proyecto_factory": proyecto_factory,
                 "usuario_factory": usuario_factory})
    extra = HTMX if htmx else {}

    def leer():
        obj.refresh_from_db()
        return str(getattr(obj, campo)).casefold()

    def guardar(cliente, datos):
        return cliente.post(reverse(url_nombre, args=[obj.pk]), datos, **extra)

    return {"obj": obj, "url": reverse(url_nombre, args=[obj.pk]), "campo": campo,
            "htmx": htmx, "leer": leer, "guardar": guardar}


def test_choque_detectado_y_no_se_guarda(dos, caso):
    a = _abrir(dos["ca"], caso["url"])
    b = _abrir(dos["cb"], caso["url"])
    resp_b = caso["guardar"](dos["cb"], _con(b, **{caso["campo"]: "Lo de Beto"}))
    assert _guardo(resp_b), f"Beto no pudo guardar ({resp_b.status_code})"
    assert caso["leer"]() == "lo de beto"

    resp = caso["guardar"](dos["ca"], _con(a, **{caso["campo"]: "Lo de Ana"}))
    _assert_choque(resp, "Beto Barrios", "Lo de Ana", htmx=caso["htmx"])
    assert caso["leer"]() == "lo de beto", "el guardado de Ana pisó a Beto"


def test_forzar_guarda_lo_mio(dos, caso):
    a = _abrir(dos["ca"], caso["url"])
    b = _abrir(dos["cb"], caso["url"])
    caso["guardar"](dos["cb"], _con(b, **{caso["campo"]: "Lo de Beto"}))
    mio = _con(a, **{caso["campo"]: "Lo de Ana"})
    assert caso["guardar"](dos["ca"], mio).status_code == 409
    # «Guardar la mía de todos modos»: el mismo envío con la bandera.
    resp = caso["guardar"](dos["ca"], _forzado(mio))
    assert _guardo(resp), f"forzar no guardó ({resp.status_code})"
    assert caso["leer"]() == "lo de ana"


def test_sin_choque_guarda_como_siempre(dos, caso):
    a = _abrir(dos["ca"], caso["url"])
    resp = caso["guardar"](dos["ca"], _con(a, **{caso["campo"]: "Lo nuevo"}))
    assert _guardo(resp), f"sin nadie más, no guardó ({resp.status_code})"
    assert caso["leer"]() == "lo nuevo"


def test_sin_testigo_pasa_como_antes(dos, caso):
    """Una pestaña abierta antes de este cambio no trae testigo: no hay con qué
    comparar y bloquearla dejaría a alguien sin poder guardar."""
    a = _abrir(dos["ca"], caso["url"])
    b = _abrir(dos["cb"], caso["url"])
    caso["guardar"](dos["cb"], _con(b, **{caso["campo"]: "Lo de Beto"}))
    viejo = _con(a, **{caso["campo"]: "Lo de Ana"})
    viejo.pop("_edicion_testigo")
    assert _guardo(caso["guardar"](dos["ca"], viejo))
    assert caso["leer"]() == "lo de ana"


def test_un_campo_que_no_tocaste_tambien_detiene(dos, cliente_factory):
    """El form manda TODOS sus campos: guardar el de Ana devolvería la razón
    social vieja y borraría lo de Beto aunque ella no la tocara. Así que también
    se pregunta, y el aviso nombra el campo."""
    cli = cliente_factory(razon_social="Heladería Original")
    url = reverse("cartera-editar", args=[cli.pk])
    a = _abrir(dos["ca"], url)
    b = _abrir(dos["cb"], url)
    dos["cb"].post(url, _con(b, razon_social="Heladería de Beto"))
    resp = dos["ca"].post(url, _con(a, notas="Paga los viernes"))
    _assert_choque(resp, "Beto Barrios", "Paga los viernes")
    assert "Razón social" in resp.content.decode()
    cli.refresh_from_db()
    assert cli.razon_social == "HELADERÍA DE BETO"


def test_una_fecha_con_default_tambien_se_vigila(dos, cliente_factory, proyecto_factory,
                                                  usuario_factory):
    """La fecha de emisión tiene un default que es una función, así que Django le
    pone un `initial-fecha_emision` oculto y su `changed_data` compara contra ÉL
    (lo que había al abrir), no contra la base. Si el testigo se fiara de eso,
    Ana reenviaría la fecha vieja y borraría la de Beto sin aviso."""
    from datetime import date

    cot = _crear_cotizacion({"cliente_factory": cliente_factory,
                             "proyecto_factory": proyecto_factory,
                             "usuario_factory": usuario_factory})
    url = reverse("cotizaciones:editar", args=[cot.pk])
    a = _abrir(dos["ca"], url)
    b = _abrir(dos["cb"], url)
    assert "initial-fecha_emision" in a, "el caso ya no ejercita show_hidden_initial"
    assert _guardo(dos["cb"].post(url, _con(b, fecha_emision="2026-01-15")))
    cot.refresh_from_db()
    assert cot.fecha_emision == date(2026, 1, 15)
    resp = dos["ca"].post(url, _con(a, titulo="Lo de Ana"))
    _assert_choque(resp, "Beto Barrios", "Lo de Ana")
    cot.refresh_from_db()
    assert cot.fecha_emision == date(2026, 1, 15)


def test_otra_ventana_de_la_misma_persona_tambien_choca(dos, proyecto_factory):
    """Dos pestañas de Ana: guardar en una y luego en la otra también pisaría.
    El aviso lo dice así, en vez de culpar a «otra persona»."""
    p = proyecto_factory(nombre="Menú de temporada")
    url = reverse("proyectos-detalle", args=[p.pk])
    ventana1 = _abrir(dos["ca"], url)
    ventana2 = _abrir(dos["ca"], url)
    assert dos["ca"].post(url, _con(ventana1, nombre="Desde la uno"), **HTMX).status_code == 200
    resp = dos["ca"].post(url, _con(ventana2, nombre="Desde la dos"), **HTMX)
    _assert_choque(resp, "Tú mismo, desde otra ventana o pestaña", "Desde la dos", htmx=True)
    p.refresh_from_db()
    assert p.nombre == "Desde la uno"


# ── El autoguardado del proyecto ──────────────────────────────────────────


def _tras_autoguardado(datos: dict, resp) -> dict:
    """Lo que el navegador tiene en el form después de un autoguardado: el OOB
    le cambia el testigo y, si se dio de alta una tarjeta, el formset entero."""
    assert resp.status_code == 200, resp.status_code
    oob = _sueltos(resp.content.decode())
    assert "_edicion_testigo" in oob, "el autoguardado no devolvió el testigo nuevo"
    nuevo = {k: list(v) for k, v in datos.items()}
    if "productos-TOTAL_FORMS" in oob:
        nuevo = {k: v for k, v in nuevo.items() if not k.startswith("productos-")}
    for k, v in oob.items():
        if k.startswith(("productos-", "_edicion_")):
            nuevo[k] = v
    return nuevo


@pytest.fixture
def servicio():
    return _crear_servicio({})


def test_dos_autoguardados_seguidos_no_chocan(dos, proyecto_factory):
    """La misma ventana cambia el MISMO campo dos veces seguidas. Sin el testigo
    nuevo del OOB, el segundo autoguardado vería «alguien cambió el nombre desde
    que abriste» (fue ella misma) y se detendría."""
    p = proyecto_factory(nombre="Menú de temporada")
    url = reverse("proyectos-detalle", args=[p.pk])
    datos = _con(_abrir(dos["ca"], url), nombre="Menú v2")
    r1 = dos["ca"].post(url, datos, **HTMX)
    datos = _con(_tras_autoguardado(datos, r1), nombre="Menú v3")
    r2 = dos["ca"].post(url, datos, **HTMX)
    assert r2.status_code == 200 and AVISO not in r2.content.decode(), \
        "el segundo autoguardado chocó consigo mismo"
    # Y de regreso al valor con el que se abrió: tampoco es un choque.
    datos = _con(_tras_autoguardado(datos, r2), nombre="Menú de temporada")
    r3 = dos["ca"].post(url, datos, **HTMX)
    assert r3.status_code == 200 and AVISO not in r3.content.decode()
    p.refresh_from_db()
    assert p.nombre == "Menú de temporada"


def test_alta_inline_no_duplica_la_linea_ni_choca(dos, proyecto_factory, servicio):
    """El bug de V8: tras dar de alta una tarjeta, el siguiente autoguardado la
    volvía a crear. El OOB trae el formset con el pk de la nueva Y el testigo que
    ya la incluye, así que el segundo guardado la edita sin chocar."""
    p = proyecto_factory(nombre="Menú de temporada")
    url = reverse("proyectos-detalle", args=[p.pk])
    datos = _abrir(dos["ca"], url)
    n = int(datos["productos-TOTAL_FORMS"][0])
    datos = _con(datos, **{
        "productos-TOTAL_FORMS": str(n + 1),
        f"productos-{n}-servicio": str(servicio.pk),
        f"productos-{n}-cantidad": "2",
        f"productos-{n}-incluir_en_calculo": "on",
    })
    r1 = dos["ca"].post(url, datos, **HTMX)
    assert p.productos.count() == 1
    linea = p.productos.get()
    datos = _tras_autoguardado(datos, r1)
    assert datos.get(f"productos-{n}-id") == [str(linea.pk)], "la tarjeta nueva volvió sin su pk"

    r2 = dos["ca"].post(url, _con(datos, **{f"productos-{n}-cantidad": "5"}), **HTMX)
    assert r2.status_code == 200 and AVISO not in r2.content.decode()
    assert p.productos.count() == 1, "el autoguardado duplicó la línea (bug V8)"
    linea.refresh_from_db()
    assert linea.cantidad == 5


def test_choque_en_una_linea_de_producto(dos, proyecto_factory, servicio):
    """Las tarjetas también se vigilan: Beto cambia la cantidad de una línea y
    Ana, con la pantalla vieja, la cambia a otra cosa."""
    p = proyecto_factory(nombre="Menú de temporada")
    url = reverse("proyectos-detalle", args=[p.pk])
    datos = _abrir(dos["ca"], url)
    datos = _con(datos, **{
        "productos-TOTAL_FORMS": "1", "productos-0-servicio": str(servicio.pk),
        "productos-0-cantidad": "1", "productos-0-incluir_en_calculo": "on",
    })
    dos["ca"].post(url, datos, **HTMX)
    linea = p.productos.get()

    a = _abrir(dos["ca"], url)
    b = _abrir(dos["cb"], url)
    assert dos["cb"].post(url, _con(b, **{"productos-0-cantidad": "3"}), **HTMX).status_code == 200
    resp = dos["ca"].post(url, _con(a, **{"productos-0-cantidad": "7"}), **HTMX)
    _assert_choque(resp, "Beto Barrios", "7", htmx=True)
    assert "de «Menú laminado»" in resp.content.decode(), "el aviso no nombra la línea"
    linea.refresh_from_db()
    assert linea.cantidad == 3
    assert p.productos.count() == 1


# ── El navegador: `ui.js` y las plantillas hablan el mismo idioma ─────────


def test_ui_js_y_el_servidor_usan_los_mismos_nombres():
    """El JS que pinta el 409, detiene el autoguardado y cablea los tres botones
    depende de nombres que pone el servidor. Si uno cambia sin el otro, el aviso
    llega pero no se ve, o se ve y sus botones no hacen nada."""
    from pathlib import Path

    from lib import edicion

    raiz = Path(__file__).resolve().parents[2]
    js = (raiz / "el-taller/static/js/ui.js").read_text(encoding="utf-8")
    aviso = (raiz / "el-taller/templates/edicion/_aviso_choque.html").read_text(encoding="utf-8")
    testigo = (raiz / "el-taller/templates/edicion/_testigo.html").read_text(encoding="utf-8")

    assert f"'{edicion.CABECERA_CHOQUE}'" in js
    assert f'name="{edicion.CAMPO_TESTIGO}"' in testigo and edicion.CAMPO_TESTIGO in js
    assert f'name="{edicion.CAMPO_FORZAR}"' in testigo and edicion.CAMPO_FORZAR in js
    for accion in ("ver", "copiar", "forzar"):
        assert f'data-edicion-accion="{accion}"' in aviso
        assert f"accion === '{accion}'" in js
    # El estado «⚠ Choque» de la barra global de guardado.
    assert "choque: ['⚠ Choque" in js
