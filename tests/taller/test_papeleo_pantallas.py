"""Las pantallas del papeleo y la puerta por la que entra del buzón.

Lo que se cuida aquí es distinto de `tests/test_papeleo.py` (que cubre la
lógica): que las pantallas **de verdad carguen** y que la puerta del robot
**esté cerrada**.

Que la pantalla se renderice se prueba pidiéndola, no leyendo la plantilla: un
`{% url %}` a una ruta que no existe, o un `{% static %}` a un archivo que no
está, es un 500 en producción que no se ve de otra forma.
"""

from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def jefe(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    return u


@pytest.fixture
def sin_permisos(client, usuario_factory):
    u = usuario_factory(rol="miembro")
    client.force_login(u)
    return u


# ── La pantalla ─────────────────────────────────────────────────────────────


def test_la_pantalla_carga(client, jefe):  # noqa: ARG001
    r = client.get("/papeleo/")
    assert r.status_code == 200


def test_sin_llave_la_pantalla_lo_dice_en_vez_de_salir_vacia(client, jefe, monkeypatch):  # noqa: ARG001
    from lib import paperless

    monkeypatch.setattr(paperless, "llave", lambda: "")
    r = client.get("/papeleo/")
    assert "no está conectado" in r.content.decode()


def test_sin_permiso_no_se_entra(client, sin_permisos):  # noqa: ARG001
    assert client.get("/papeleo/").status_code == 403


def test_sin_sesion_manda_al_login(client):
    r = client.get("/papeleo/")
    assert r.status_code in (302, 301)


def test_buscar_pinta_lo_que_devuelve_el_archivo(client, jefe, monkeypatch):  # noqa: ARG001
    from lib import paperless

    monkeypatch.setattr(paperless, "llave", lambda: "k")
    monkeypatch.setattr(paperless, "buscar", lambda t, n=10: [
        {"id": 5, "titulo": "Contrato con Optimist", "creado": "2026-08-01",
         "etiquetas": [], "paginas": 3}])
    monkeypatch.setattr(paperless, "url_publica", lambda: "http://10.0.0.9:8204")
    cuerpo = client.get("/papeleo/?q=optimist").content.decode()
    assert "Contrato con Optimist" in cuerpo
    assert "http://10.0.0.9:8204/documents/5/details" in cuerpo


def test_si_el_archivo_no_contesta_la_pantalla_lo_dice(client, jefe, monkeypatch):  # noqa: ARG001
    """None de `buscar` es «no se pudo preguntar», no «no hay nada»: pintar
    «sin resultados» ahí sería mentir."""
    from lib import paperless

    monkeypatch.setattr(paperless, "llave", lambda: "k")
    monkeypatch.setattr(paperless, "buscar", lambda t, n=10: None)
    assert "no contestó" in client.get("/papeleo/?q=x").content.decode()


def test_la_pantalla_dice_de_quien_es_cada_documento(client, jefe, monkeypatch):
    from apps.la_cartera.models import Cliente

    from lib import paperless
    from papeleo import ligado

    cli = Cliente.objects.create(razon_social="Optimist Studio")
    ligado.ligar(5, titulo="Contrato", cliente=cli, usuario=jefe)

    monkeypatch.setattr(paperless, "llave", lambda: "k")
    monkeypatch.setattr(paperless, "buscar", lambda t, n=10: [
        {"id": 5, "titulo": "Contrato", "creado": "", "etiquetas": [],
         "paginas": 1}])
    assert "Optimist Studio" in client.get("/papeleo/?q=contrato").content.decode()


# ── Ligar y desligar desde la pantalla ──────────────────────────────────────


def test_ligar_desde_la_pantalla(client, jefe):
    from apps.la_cartera.models import Cliente

    from papeleo.models import PapeleoLigado

    cli = Cliente.objects.create(razon_social="Optimist")
    r = client.post("/papeleo/9/ligar", {"cliente": cli.pk, "titulo": "Remisión"})
    assert r.status_code == 302
    assert PapeleoLigado.objects.filter(documento_id=9, cliente=cli).exists()


def test_ligar_sin_decir_de_quien_no_crea_nada(client, jefe):  # noqa: ARG001
    from papeleo.models import PapeleoLigado

    client.post("/papeleo/9/ligar", {})
    assert not PapeleoLigado.objects.exists()


def test_sin_permiso_de_ligar_no_se_liga(client, sin_permisos):  # noqa: ARG001
    from apps.la_cartera.models import Cliente

    from papeleo.models import PapeleoLigado

    cli = Cliente.objects.create(razon_social="Optimist")
    r = client.post("/papeleo/9/ligar", {"cliente": cli.pk})
    assert r.status_code == 403
    assert not PapeleoLigado.objects.exists()


def test_desligar_no_toca_el_documento_en_paperless(client, jefe, monkeypatch):
    from apps.la_cartera.models import Cliente

    from lib import paperless
    from papeleo import ligado
    from papeleo.models import PapeleoLigado

    def _explota(*a, **k):  # pragma: no cover
        raise AssertionError("desligar no debe pedirle nada a Paperless")

    monkeypatch.setattr(paperless, "_pedir", _explota)
    cli = Cliente.objects.create(razon_social="Optimist")
    fila = ligado.ligar(9, cliente=cli, usuario=jefe)
    client.post(f"/papeleo/liga/{fila.pk}/quitar")
    assert not PapeleoLigado.objects.exists()


# ── La puerta del robot ─────────────────────────────────────────────────────


def test_sin_token_configurado_nadie_pasa(client, monkeypatch):
    """Se cierra, no se abre: un extremo que al faltarle la credencial deja
    entrar a todos es peor que uno sin credencial."""
    from papeleo import entrada

    monkeypatch.setattr(entrada, "_tokens", lambda: [])
    r = client.post("/papeleo/entra", {}, HTTP_X_PAPELEO_TOKEN="lo-que-sea")
    assert r.status_code == 404


def test_con_token_equivocado_es_404_y_no_403(client, monkeypatch):
    """404 y no 403: a quien no trae credencial no se le confirma siquiera que
    esta puerta existe."""
    from papeleo import entrada

    monkeypatch.setattr(entrada, "_tokens", lambda: ["bueno"])
    r = client.post("/papeleo/entra", {}, HTTP_X_PAPELEO_TOKEN="malo")
    assert r.status_code == 404


def test_sin_cabecera_no_pasa(client, monkeypatch):
    from papeleo import entrada

    monkeypatch.setattr(entrada, "_tokens", lambda: ["bueno"])
    assert client.post("/papeleo/entra", {}).status_code == 404


def test_get_no_se_permite(client):
    assert client.get("/papeleo/entra").status_code == 405


def test_con_token_bueno_el_archivo_se_sube(client, monkeypatch):
    from lib import paperless
    from papeleo import entrada

    monkeypatch.setattr(entrada, "_tokens", lambda: ["bueno"])
    monkeypatch.setattr(paperless, "esta_configurado", lambda: True)
    monkeypatch.setattr(paperless, "id_de_etiqueta", lambda n: 3)
    visto = {}
    monkeypatch.setattr(paperless, "subir",
                        lambda c, n, **k: visto.update(nombre=n, kw=k) or "tarea-1")

    archivo = io.BytesIO(b"%PDF-1.4 contrato")
    archivo.name = "contrato.pdf"
    r = client.post("/papeleo/entra", {"archivo": archivo},
                    HTTP_X_PAPELEO_TOKEN="bueno")
    assert r.status_code == 202
    assert r.json()["ok"] is True
    assert visto["nombre"] == "contrato.pdf"


def test_la_respuesta_no_promete_que_ya_quedo_archivado(client, monkeypatch):
    """Paperless devuelve el id de la TAREA: el documento no existe todavía y su
    OCR corre después. Decir «ya quedó» sería mentir por unos minutos."""
    from lib import paperless
    from papeleo import entrada

    monkeypatch.setattr(entrada, "_tokens", lambda: ["bueno"])
    monkeypatch.setattr(paperless, "esta_configurado", lambda: True)
    monkeypatch.setattr(paperless, "id_de_etiqueta", lambda n: None)
    monkeypatch.setattr(paperless, "subir", lambda c, n, **k: "tarea-1")

    archivo = io.BytesIO(b"x")
    archivo.name = "remision.pdf"
    r = client.post("/papeleo/entra", {"archivo": archivo},
                    HTTP_X_PAPELEO_TOKEN="bueno")
    assert "minutos" in r.json()["nota"]


def test_un_cfdi_se_rechaza_con_la_direccion_correcta(client, monkeypatch):
    """Un XML de CFDI aquí acabaría archivado como papeleo suelto, sin ligar a
    su factura y sin UUID."""
    from papeleo import entrada

    monkeypatch.setattr(entrada, "_tokens", lambda: ["bueno"])
    archivo = io.BytesIO(b"<cfdi:Comprobante/>")
    archivo.name = "factura.xml"
    r = client.post("/papeleo/entra", {"archivo": archivo},
                    HTTP_X_PAPELEO_TOKEN="bueno")
    assert r.status_code == 422
    assert "cfdi-entrante" in r.json()["error"]


def test_sin_archivo_lo_dice(client, monkeypatch):
    from papeleo import entrada

    monkeypatch.setattr(entrada, "_tokens", lambda: ["bueno"])
    r = client.post("/papeleo/entra", {}, HTTP_X_PAPELEO_TOKEN="bueno")
    assert r.status_code == 400


def test_sin_llave_de_paperless_contesta_503_y_no_una_traza(client, monkeypatch):
    """Del otro lado hay un robot: una página de error de Django no le dice
    nada y el documento se perdería sin que nadie se entere."""
    from lib import paperless
    from papeleo import entrada

    monkeypatch.setattr(entrada, "_tokens", lambda: ["bueno"])
    monkeypatch.setattr(paperless, "esta_configurado", lambda: False)
    archivo = io.BytesIO(b"x")
    archivo.name = "a.pdf"
    r = client.post("/papeleo/entra", {"archivo": archivo},
                    HTTP_X_PAPELEO_TOKEN="bueno")
    assert r.status_code == 503
    assert r.json()["ok"] is False


# ── El recuadro en las tres fichas ──────────────────────────────────────────
# El MISMO partial en las tres, con el MISMO helper de contexto. Se prueba
# pidiendo la página: un include a una plantilla inexistente o un {% url %} a
# una ruta que no está son 500 que no se ven de otra forma.


@pytest.fixture
def cliente(db):
    from apps.la_cartera.models import Cliente

    return Cliente.objects.create(razon_social="Optimist Studio")


def test_la_ficha_del_cliente_muestra_su_papeleo(client, jefe, cliente):
    from papeleo import ligado

    ligado.ligar(31, titulo="Contrato marco", cliente=cliente, usuario=jefe)
    cuerpo = client.get(f"/cartera/{cliente.pk}/").content.decode()
    assert "Contrato marco" in cuerpo


def test_la_ficha_del_proyecto_muestra_su_papeleo(client, jefe, cliente):
    from apps.los_proyectos.models import Proyecto

    from papeleo import ligado

    pr = Proyecto.objects.create(nombre="Gorras", cliente=cliente)
    ligado.ligar(32, titulo="Remisión firmada", proyecto=pr, usuario=jefe)
    cuerpo = client.get(f"/proyectos/{pr.pk}/").content.decode()
    assert "Remisión firmada" in cuerpo


def test_la_ficha_del_proveedor_muestra_su_papeleo(client, jefe):
    from apps.el_catalogo.models import Proveedor

    from papeleo import ligado

    prov = Proveedor.objects.create(razon_social="Simil Cuero Plymouth")
    ligado.ligar(33, titulo="Cotización de insumos", proveedor=prov, usuario=jefe)
    cuerpo = client.get(f"/catalogo/proveedores/{prov.pk}/").content.decode()
    assert "Cotización de insumos" in cuerpo


def test_sin_permiso_de_papeleo_la_ficha_no_pinta_el_recuadro(client, usuario_factory,
                                                             cliente):
    """El recuadro no puede aparecer vacío a quien no tiene el permiso: sería
    enseñarle un módulo al que no entra."""
    from lib.permisos_defaults import CATALOGO_PERMISOS  # noqa: F401

    u = usuario_factory(rol="miembro")
    # Se le da lo de cartera para que pueda abrir la ficha, pero NADA de papeleo.
    from cuentas.models.permiso_usuario import PermisoUsuario

    for accion in ("ver", "editar"):
        PermisoUsuario.objects.update_or_create(
            usuario=u, modulo="cartera", permiso=accion, defaults={"activo": True})
    client.force_login(u)
    cuerpo = client.get(f"/cartera/{cliente.pk}/").content.decode()
    assert "Buscar en el archivo" not in cuerpo


def test_el_boton_de_desligar_no_va_en_un_form_anidado():
    """La ficha del proyecto envuelve su sidebar en el formulario de
    autoguardado, y los formularios NO se anidan: dentro de otro, un <form>
    quedaría muerto sin que nada lo avise. Por eso el botón va por HTMX."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent.parent
    import re

    partial = (raiz / "el-taller/templates/papeleo/_recuadro.html").read_text()
    # Se mira el HTML, no los comentarios (que explican justo esto y nombran
    # la etiqueta prohibida).
    html = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "",
                  partial, flags=re.S)
    assert "<form" not in html
    assert "hx-post" in html


def test_desligar_por_htmx_contesta_para_repintar(client, jefe, cliente):
    from papeleo import ligado

    fila = ligado.ligar(34, cliente=cliente, usuario=jefe)
    r = client.post(f"/papeleo/liga/{fila.pk}/quitar", HTTP_HX_REQUEST="true",
                    HTTP_HX_CURRENT_URL=f"/cartera/{cliente.pk}/")
    assert r.status_code == 204
    assert r.headers["HX-Redirect"] == f"/cartera/{cliente.pk}/"
