"""Ver los documentos del archivo dentro de El Taller.

Oscar, 2026-08-24: «crea una sección para ver documentos, los de Paperless —
cierra el bucle del GUI, y hay un lugar para buscar, además de que el Chalán
busca, encuentra y muestra».

Faltaban tres cosas y las tres se cuidan aquí:

1. **El proxy es la única puerta al documento.** Quien no puede ver papeleo no
   lo ve aunque adivine el número — es contratos y comprobantes del negocio.
   Es lo primero porque es lo único que, si falla, no se puede deshacer.
2. **Sin escribir nada se ve lo que hay.** Una pantalla de archivo que sólo
   contesta si le tecleas algo obliga a adivinar una palabra para descubrir que
   el documento existe. Eso no es «ver el archivo».
3. **Los enlaces apuntan adentro.** La dirección de Paperless sólo existe en el
   tailnet: desde el celular en la calle no abre, y además tiene su propia
   sesión.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def _archivo_conectado(monkeypatch):
    """Un Paperless que contesta, sin red."""
    from lib import paperless

    monkeypatch.setattr(paperless, "esta_configurado", lambda: True)
    return paperless


def _doc(i=3, titulo="Contrato Optimist"):
    return {"id": i, "titulo": titulo, "creado": "2026-08-20",
            "etiquetas": [], "paginas": 2}


# ── 1. La puerta ───────────────────────────────────────────────────────────


def test_sin_permiso_no_se_ve_el_documento(client, usuario_factory, monkeypatch,
                                           _archivo_conectado):
    """El modo de falla que importa: un proxy abierto entrega contratos a
    cualquiera que teclee un número."""
    from lib import paperless

    monkeypatch.setattr(paperless, "archivo",
                        lambda i, cara="preview": (b"%PDF-1.4 secreto", "application/pdf"))
    client.force_login(usuario_factory(rol="miembro"))

    for ruta in ("/papeleo/3/archivo", "/papeleo/3/miniatura", "/papeleo/3/bajar"):
        r = client.get(ruta)
        assert r.status_code == 403, f"{ruta} dejó pasar a quien no puede ver papeleo"
        assert b"secreto" not in r.content


def test_sin_sesion_tampoco(client):
    r = client.get("/papeleo/3/archivo")
    assert r.status_code in (302, 403)


def test_con_permiso_se_sirve_el_documento(client, usuario_factory, monkeypatch,
                                           _archivo_conectado):
    from lib import paperless

    monkeypatch.setattr(paperless, "archivo",
                        lambda i, cara="preview": (b"%PDF-1.4", "application/pdf"))
    client.force_login(usuario_factory(rol="super_admin"))

    r = client.get("/papeleo/3/archivo")
    assert r.status_code == 200
    assert r["Content-Type"] == "application/pdf"
    # `inline` para verlo en la página; `attachment` sólo al bajarlo.
    assert "inline" in r["Content-Disposition"]
    assert r["X-Content-Type-Options"] == "nosniff"


def test_bajar_lo_manda_como_descarga(client, usuario_factory, monkeypatch,
                                      _archivo_conectado):
    from lib import paperless

    monkeypatch.setattr(paperless, "archivo",
                        lambda i, cara="preview": (b"%PDF-1.4", "application/pdf"))
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.get("/papeleo/3/bajar")
    assert "attachment" in r["Content-Disposition"]


def test_el_documento_no_se_guarda_en_cache_pero_la_miniatura_si(
        client, usuario_factory, monkeypatch, _archivo_conectado):
    """Guardar el documento en el navegador lo dejaría a la mano de quien pierda
    el permiso entre una visita y la siguiente. La miniatura no es el documento."""
    from lib import paperless

    monkeypatch.setattr(paperless, "archivo",
                        lambda i, cara="preview": (b"x", "image/webp"))
    client.force_login(usuario_factory(rol="super_admin"))

    assert "no-store" in client.get("/papeleo/3/archivo")["Cache-Control"]
    assert "max-age" in client.get("/papeleo/3/miniatura")["Cache-Control"]


def test_si_el_archivo_no_lo_tiene_es_un_404_limpio(client, usuario_factory,
                                                    monkeypatch, _archivo_conectado):
    from lib import paperless

    monkeypatch.setattr(paperless, "archivo", lambda i, cara="preview": None)
    client.force_login(usuario_factory(rol="super_admin"))
    assert client.get("/papeleo/9999/archivo").status_code == 404


# ── 2. Ver lo que hay, sin buscar ──────────────────────────────────────────


def test_al_entrar_se_ve_lo_ultimo_sin_escribir_nada(client, usuario_factory,
                                                     monkeypatch, _archivo_conectado):
    """El corazón del pedido: antes, sin `?q=`, la pantalla salía vacía."""
    from lib import paperless

    monkeypatch.setattr(paperless, "listar", lambda n=20: [_doc()])
    monkeypatch.setattr(paperless, "cuantos", lambda: 1)
    monkeypatch.setattr(paperless, "buscar",
                        lambda *a, **k: pytest.fail("sin palabra no debe buscar"))
    client.force_login(usuario_factory(rol="super_admin"))

    cuerpo = client.get("/papeleo/").content.decode()
    assert "Contrato Optimist" in cuerpo
    assert "Lo último que entró" in cuerpo


def test_con_palabra_si_busca(client, usuario_factory, monkeypatch, _archivo_conectado):
    from lib import paperless

    monkeypatch.setattr(paperless, "buscar", lambda t, n=20: [_doc(titulo=f"Hallado {t}")])
    monkeypatch.setattr(paperless, "cuantos", lambda: 7)
    monkeypatch.setattr(paperless, "listar",
                        lambda *a, **k: pytest.fail("con palabra no debe listar"))
    client.force_login(usuario_factory(rol="super_admin"))

    cuerpo = client.get("/papeleo/?q=optimist").content.decode()
    assert "Hallado optimist" in cuerpo


def test_un_archivo_vacio_no_se_lee_como_una_busqueda_sin_resultados(
        client, usuario_factory, monkeypatch, _archivo_conectado):
    """«No hay nada archivado» y «nada con esa palabra» son noticias distintas."""
    from lib import paperless

    monkeypatch.setattr(paperless, "listar", lambda n=20: [])
    monkeypatch.setattr(paperless, "cuantos", lambda: 0)
    client.force_login(usuario_factory(rol="super_admin"))

    cuerpo = client.get("/papeleo/").content.decode()
    assert "El archivo está vacío" in cuerpo
    assert "Nada con esa palabra" not in cuerpo


def test_las_tarjetas_llevan_miniatura_y_van_a_la_ficha(client, usuario_factory,
                                                        monkeypatch, _archivo_conectado):
    """Los escaneos se titulan «scan_0042»: sin miniatura no se reconoce ninguno."""
    from lib import paperless

    monkeypatch.setattr(paperless, "listar", lambda n=20: [_doc()])
    monkeypatch.setattr(paperless, "cuantos", lambda: 1)
    client.force_login(usuario_factory(rol="super_admin"))

    cuerpo = client.get("/papeleo/").content.decode()
    assert "/papeleo/3/miniatura" in cuerpo
    assert 'href="/papeleo/3/"' in cuerpo


def test_si_el_archivo_no_contesta_lo_dice(client, usuario_factory, monkeypatch,
                                           _archivo_conectado):
    from lib import paperless

    monkeypatch.setattr(paperless, "listar", lambda n=20: None)
    client.force_login(usuario_factory(rol="super_admin"))
    assert "no contestó" in client.get("/papeleo/").content.decode()


# ── 3. La ficha ────────────────────────────────────────────────────────────


def test_la_ficha_muestra_el_documento_adentro(client, usuario_factory, monkeypatch,
                                               _archivo_conectado):
    from lib import paperless

    doc = _doc() | {"texto": "lo que dice adentro", "texto_recortado": False}
    monkeypatch.setattr(paperless, "detalle", lambda i: doc)
    monkeypatch.setattr(paperless, "url_publica", lambda: "")
    monkeypatch.setattr(paperless, "url_web", lambda i: "")
    client.force_login(usuario_factory(rol="super_admin"))

    cuerpo = client.get("/papeleo/3/").content.decode()
    assert "/papeleo/3/archivo" in cuerpo, "el documento no se embebe"
    assert "Contrato Optimist" in cuerpo
    assert "lo que dice adentro" in cuerpo


def test_la_ficha_dice_de_quien_es(client, usuario_factory, monkeypatch,
                                   _archivo_conectado, cliente_factory):
    from lib import paperless
    from papeleo.models import PapeleoLigado

    c = cliente_factory(razon_social="OPTIMIST SA")
    PapeleoLigado.objects.create(documento_id=3, titulo="Contrato", cliente=c)
    monkeypatch.setattr(paperless, "detalle", lambda i: _doc())
    monkeypatch.setattr(paperless, "url_web", lambda i: "")
    client.force_login(usuario_factory(rol="super_admin"))

    assert "OPTIMIST SA" in client.get("/papeleo/3/").content.decode()


def test_sin_permiso_no_se_abre_la_ficha(client, usuario_factory, monkeypatch,
                                         _archivo_conectado):
    from lib import paperless

    monkeypatch.setattr(paperless, "detalle", lambda i: _doc())
    client.force_login(usuario_factory(rol="miembro"))
    assert client.get("/papeleo/3/").status_code == 403


def test_un_documento_que_no_existe_regresa_a_la_lista(client, usuario_factory,
                                                       monkeypatch, _archivo_conectado):
    from lib import paperless

    monkeypatch.setattr(paperless, "detalle", lambda i: None)
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.get("/papeleo/9999/")
    assert r.status_code == 302
    assert r["Location"].endswith("/papeleo/")


# ── 4. El Chalán manda adentro, no a otra aplicación ───────────────────────


def test_el_chalan_ofrece_la_ficha_de_el_taller(monkeypatch, usuario_factory,
                                                _archivo_conectado):
    from capacidades.lecturas import _h_buscar_papeleo
    from lib import paperless

    monkeypatch.setattr(paperless, "buscar", lambda t, n=10: [_doc()])
    r = _h_buscar_papeleo({"texto": "optimist"}, usuario_factory(rol="super_admin"))
    assert r["documentos"][0]["ver"] == "/papeleo/3/"
    assert "abrir" not in r["documentos"][0], "sigue mandando a Paperless"


def test_el_detalle_del_chalan_tambien(monkeypatch, usuario_factory, _archivo_conectado):
    from capacidades.lecturas import _h_detalle_papeleo
    from lib import paperless

    monkeypatch.setattr(paperless, "detalle", lambda i: _doc())
    r = _h_detalle_papeleo({"documento_id": "3"}, usuario_factory(rol="super_admin"))
    assert r["ver"] == "/papeleo/3/"


def test_el_recuadro_de_las_fichas_abre_el_visor():
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent.parent
    html = (raiz / "el-taller/templates/papeleo/_recuadro.html").read_text()
    assert "papeleo-ver" in html
    assert "f.url_web" not in html, "sigue mandando a Paperless desde la ficha"


# ── 5. Lo que trae el archivo ──────────────────────────────────────────────


def test_listar_pide_lo_mas_reciente(monkeypatch):
    from lib import paperless

    pedido = {}

    def _espia(ruta):
        pedido["ruta"] = ruta
        return {"results": []}

    monkeypatch.setattr(paperless, "_pedir", _espia)
    paperless.listar(5)
    assert "ordering=-created" in pedido["ruta"]
    assert "page_size=5" in pedido["ruta"]


def test_listar_no_pide_mas_del_tope(monkeypatch):
    from lib import paperless

    pedido = {}

    def _espia(ruta):
        pedido["ruta"] = ruta
        return {"results": []}

    monkeypatch.setattr(paperless, "_pedir", _espia)
    paperless.listar(9999)
    assert f"page_size={paperless.TOPE}" in pedido["ruta"]


def test_una_cara_inventada_no_se_pide(monkeypatch):
    """`cara` viaja a una URL: si no se acota, cualquier cadena se concatena."""
    from lib import paperless

    monkeypatch.setattr(paperless, "llave", lambda: "t0ken")
    assert paperless.archivo(3, "../../etc/passwd") is None
    assert paperless.archivo(3, "borrar") is None


def test_sin_llave_no_se_trae_nada(monkeypatch):
    from lib import paperless

    monkeypatch.setattr(paperless, "llave", lambda: "")
    assert paperless.archivo(3) is None
    assert paperless.listar() is None
