"""Gerencia → Ajustes → Documentos, la pantalla de La Imprenta (2026-09-29).

Lo que se cuida:

1. **Cada pestaña abre** (hoja, marca, datos, cada tipo, historial).
2. **Cada pestaña pide SU permiso** (§4 #20): quien cambia colores no por eso
   cambia la CLABE, y quien sólo ve no guarda nada.
3. **La vista previa dibuja lo del formulario y no guarda.**
4. **El PDF de prueba** lo arma el motor de verdad, y si no contesta se dice.
5. **El testigo** no deja pisar lo que guardó otra persona sin preguntar.
6. **El logotipo** se guarda en El Almacén; un archivo que no es imagen no.
7. **Restaurar** exige poder editar todo.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _sin_cache():
    from imprenta import config

    config.olvidar()
    yield
    config.olvidar()


@pytest.fixture
def jefe(usuario_factory):
    return usuario_factory(rol="super_admin")


@pytest.fixture
def cot(cliente_factory, jefe):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem

    c = Cotizacion.objects.create(cliente=cliente_factory(creado_por=jefe),
                                  titulo="Termos", creado_por=jefe, estado="generada")
    CotizacionItem.objects.create(cotizacion=c, orden=0, concepto="Termo",
                                  cantidad=Decimal("10"), precio_unitario=Decimal("100"))
    return c


def _con_permisos(usuario_factory, *acciones):
    """Alguien que entra a La Gerencia con sólo esas acciones de `documentos`."""
    from cuentas.models.permiso_usuario import PermisoUsuario

    u = usuario_factory(rol="dueno")
    PermisoUsuario.objects.filter(usuario=u, modulo="documentos").delete()
    for accion in ("ver", "editar_estilo", "editar_notas", "editar_datos"):
        PermisoUsuario.objects.create(usuario=u, modulo="documentos", permiso=accion,
                                      activo=accion in acciones)
    from lib import permisos
    if hasattr(permisos, "olvidar_cache"):
        permisos.olvidar_cache()
    return u


URL = "ajustes-documentos"


# ── 1. Las pestañas ────────────────────────────────────────────────────────


@pytest.mark.parametrize("tab", ["general", "marca", "despacho", "cotizacion", "factura",
                                 "recibo_pago", "estado_cuenta", "remision", "orden_trabajo",
                                 "reembolso", "orden_compra", "historial"])
def test_cada_pestana_abre(client, jefe, cot, tab):
    client.force_login(jefe)
    r = client.get(reverse(URL), {"tab": tab})
    assert r.status_code == 200, tab
    assert b"Documentos" in r.content


def test_la_pestana_de_marca_pinta_los_campos_del_esquema(client, jefe):
    client.force_login(jefe)
    html = client.get(reverse(URL), {"tab": "marca"}).content.decode()
    for nombre in ("marca__color_acento", "marca__fuente_cuerpo", "tablas__fondo_encabezado",
                   "marca__logo_archivo"):
        assert f'name="{nombre}"' in html, nombre


def test_la_pestana_de_un_tipo_pinta_sus_bloques_y_columnas(client, jefe):
    client.force_login(jefe)
    html = client.get(reverse(URL), {"tab": "cotizacion"}).content.decode()
    assert 'name="cotizacion__bloque_fotos"' in html
    assert 'name="cotizacion__col_precio"' in html
    assert 'name="cotizacion__margen_superior_pt"' in html


# ── 2. Los permisos ────────────────────────────────────────────────────────


def test_guardar_la_marca(client, jefe):
    from imprenta.config import resolver

    client.force_login(jefe)
    r = client.post(reverse(URL), {"seccion": "marca", "base": "0",
                                   "marca__color_acento": "#D92D20",
                                   "marca__fuente_cuerpo": "inter",
                                   "tablas__grosor_borde": "2"})
    assert r.status_code == 302
    cfg = resolver("cotizacion")
    assert cfg.marca["color_acento"] == "#d92d20"
    assert cfg.marca["fuente_cuerpo"] == "inter"
    assert cfg.tablas["grosor_borde"] == 2


def test_una_opcion_inventada_no_se_guarda(client, jefe):
    """El `select` se puede manipular desde el navegador."""
    from imprenta.config import resolver

    client.force_login(jefe)
    client.post(reverse(URL), {"seccion": "marca", "marca__fuente_cuerpo": "comic-sans",
                               "marca__color_acento": "rojo"})
    cfg = resolver("cotizacion")
    assert cfg.marca["fuente_cuerpo"] == "arial"
    assert cfg.marca["color_acento"] == "#000000"


def test_quien_solo_ve_no_guarda(client, usuario_factory):
    from imprenta.models import AjusteImprenta

    client.force_login(_con_permisos(usuario_factory, "ver"))
    assert client.get(reverse(URL), {"tab": "marca"}).status_code == 200
    r = client.post(reverse(URL), {"seccion": "marca", "marca__color_acento": "#d92d20"})
    assert r.status_code == 403
    assert not AjusteImprenta.objects.exists()


def test_quien_cambia_el_estilo_no_cambia_los_datos(client, usuario_factory):
    from imprenta.models import AjusteImprenta

    client.force_login(_con_permisos(usuario_factory, "ver", "editar_estilo"))
    r = client.post(reverse(URL), {"seccion": "despacho", "despacho__clabe": "012345678901234567"})
    assert r.status_code == 403, "cambió la CLABE quien sólo tiene permiso de estilo"
    assert not AjusteImprenta.objects.filter(ambito="despacho").exists()
    r = client.post(reverse(URL), {"seccion": "marca", "marca__color_acento": "#d92d20"})
    assert r.status_code == 302


def test_sin_permiso_no_entra(client, usuario_factory):
    client.force_login(usuario_factory(rol="miembro"))
    assert client.get(reverse(URL)).status_code in (302, 403)
    assert client.post(reverse("ajustes-documentos-vista"), {}).status_code in (302, 403)


# ── 3. La vista previa ──────────────────────────────────────────────────────


def test_la_vista_previa_dibuja_lo_del_formulario_sin_guardar(client, jefe, cot):
    from imprenta.models import AjusteImprenta

    client.force_login(jefe)
    r = client.post(reverse("ajustes-documentos-vista"), {
        "seccion": "cotizacion", "tipo": "cotizacion", "ejemplo": str(cot.pk),
        # Una casilla que no viaja es una casilla apagada, como en el navegador.
        "cotizacion__col_precio": "Precio c/u", "cotizacion__bloque_montos": "on"})
    html = r.content.decode()
    assert r.status_code == 200
    assert ">Precio c/u<" in html
    assert "lc-hoja" in html, "la vista previa debe enseñar la hoja"
    assert "lc-barra" not in html.split("</style>")[-1], "la barra de acciones no va en La Gerencia"
    assert not AjusteImprenta.objects.exists(), "la vista previa guardó"


def test_la_vista_previa_de_la_hoja_sigue_los_margenes(client, jefe, cot):
    client.force_login(jefe)
    r = client.post(reverse("ajustes-documentos-vista"), {
        "seccion": "general", "tipo": "cotizacion", "ejemplo": str(cot.pk),
        "motor": "auto", "tamano_papel": "carta", "margen_superior_pt": "72",
        "margen_inferior_pt": "43", "margen_izquierdo_pt": "72", "margen_derecho_pt": "72",
        "interlineado": "1.02"})
    assert "padding: 1.0in 1.0in 0.597in 1.0in" in r.content.decode()


def test_la_vista_previa_sin_documentos_lo_dice(client, jefe):
    client.force_login(jefe)
    r = client.post(reverse("ajustes-documentos-vista"), {"seccion": "marca", "tipo": "cotizacion"})
    assert "No hay ningún documento" in r.content.decode()


def test_un_ejemplo_ajeno_no_se_dibuja(client, jefe, cot):
    """El id del ejemplo viaja en el formulario: sólo se aceptan los de la lista."""
    client.force_login(jefe)
    r = client.post(reverse("ajustes-documentos-vista"), {
        "seccion": "marca", "tipo": "cotizacion", "ejemplo": "999999"})
    assert r.status_code == 200 and "Termo" in r.content.decode()


# ── 4. El PDF de prueba ─────────────────────────────────────────────────────


def test_el_pdf_de_prueba_sale_del_motor(client, jefe, cot, monkeypatch):
    from lib import gotenberg

    capturado = {}
    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)

    def _convertir(html, pagina=None):
        capturado["html"], capturado["pagina"] = html, pagina
        return b"%PDF-1.4 prueba"

    monkeypatch.setattr(gotenberg, "html_a_pdf", _convertir)
    client.force_login(jefe)
    r = client.post(reverse("ajustes-documentos-vista-pdf"), {
        "seccion": "marca", "tipo": "cotizacion", "ejemplo": str(cot.pk),
        "marca__fuente_cuerpo": "lato"})
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert "LCLato" in capturado["html"]
    assert "url('Lato-Regular.ttf')" in capturado["html"], "para el motor la fuente va pegada"
    assert "Lato-Regular.ttf" in capturado["pagina"]["fuentes"]


def test_el_pdf_de_prueba_sin_motor_lo_dice(client, jefe, cot, monkeypatch):
    from lib import gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: False)
    client.force_login(jefe)
    r = client.post(reverse("ajustes-documentos-vista-pdf"), {
        "seccion": "marca", "tipo": "cotizacion", "ejemplo": str(cot.pk)})
    assert r.status_code == 503


# ── 5. El testigo ───────────────────────────────────────────────────────────


def test_el_testigo_pregunta_antes_de_pisar(client, jefe, usuario_factory):
    from imprenta import servicios
    from imprenta.config import resolver

    base = servicios.guardar({"marca": {"color_acento": "#111111"}}, jefe).pk
    servicios.guardar({"marca": {"color_acento": "#222222"}}, usuario_factory(rol="super_admin"))

    client.force_login(jefe)
    datos = {"seccion": "marca", "base": str(base), "marca__color_acento": "#333333"}
    r = client.post(reverse(URL), datos)
    assert r.status_code == 409
    assert "Guardar lo mío de todos modos" in r.content.decode()
    assert 'value="#333333"' in r.content.decode(), "el aviso borró lo que la persona escribió"
    assert resolver("cotizacion").marca["color_acento"] == "#222222", "se pisó sin preguntar"

    r = client.post(reverse(URL), {**datos, "forzar": "1"})
    assert r.status_code == 302
    from imprenta import config
    config.olvidar()
    assert resolver("cotizacion").marca["color_acento"] == "#333333"


# ── 6. El logotipo ──────────────────────────────────────────────────────────


def _png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (200, 100), (255, 0, 0, 255)).save(buf, "PNG")
    return buf.getvalue()


def test_el_logotipo_se_guarda_en_el_almacen_y_sale_apaisado(client, jefe, cot):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from imprenta.config import resolver

    client.force_login(jefe)
    archivo = SimpleUploadedFile("logo.png", _png(), content_type="image/png")
    r = client.post(reverse(URL), {"seccion": "marca", "marca__logo_alto_pt": "40",
                                   "marca__logo_archivo": archivo})
    assert r.status_code == 302
    cfg = resolver("cotizacion")
    assert cfg.marca["logo"], "no se guardó la llave del logotipo"
    assert "/medios/" in cfg.e.logo_url
    assert cfg.e.logo_ancho == 80, "un logotipo 2:1 de 40pt de alto mide 80 de ancho"


def test_un_archivo_que_no_es_imagen_no_entra(client, jefe):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from imprenta.config import resolver

    client.force_login(jefe)
    archivo = SimpleUploadedFile("logo.svg", b"<svg onload=alert(1)>", content_type="image/svg+xml")
    client.post(reverse(URL), {"seccion": "marca", "marca__logo_archivo": archivo})
    assert resolver("cotizacion").marca["logo"] == ""


# ── 7. Restaurar ────────────────────────────────────────────────────────────


def test_restaurar_pide_poder_editar_todo(client, jefe, usuario_factory):
    from imprenta import servicios
    from imprenta.models import VersionImprenta

    servicios.guardar({"marca": {"color_acento": "#d92d20"}}, jefe)
    inicial = VersionImprenta.objects.order_by("pk").first()

    client.force_login(_con_permisos(usuario_factory, "ver", "editar_estilo"))
    r = client.post(reverse("ajustes-documentos-restaurar", args=[inicial.pk]))
    assert r.status_code == 403

    client.force_login(jefe)
    r = client.post(reverse("ajustes-documentos-restaurar", args=[inicial.pk]))
    assert r.status_code == 302
    assert VersionImprenta.objects.first().restaurada_de_id == inicial.pk


def test_el_historial_cuenta_lo_que_cambio(client, jefe):
    from imprenta import servicios

    servicios.guardar({"marca": {"fuente_cuerpo": "lato"}}, jefe, motivo="Marca y tablas")
    client.force_login(jefe)
    html = client.get(reverse(URL), {"tab": "historial"}).content.decode()
    assert "Letra del documento" in html and "Lato" in html
    assert "Volver a esta versión" in html


# ── La siembra de los permisos ──────────────────────────────────────────────


def test_la_siembra_da_documentos_a_quien_entraba_a_ajustes(usuario_factory):
    """«Como hoy»: la pantalla vivía en Ajustes; el permiso nuevo nace para las
    mismas personas y para nadie más."""
    import importlib

    from django.apps import apps

    from cuentas.models.permiso_usuario import PermisoUsuario

    con_ajustes = usuario_factory(rol="dueno")
    PermisoUsuario.objects.update_or_create(usuario=con_ajustes, modulo="ajustes",
                                            permiso="acceder", defaults={"activo": True})
    sin_ajustes = usuario_factory(rol="dueno")
    PermisoUsuario.objects.filter(usuario=sin_ajustes, modulo="ajustes").delete()
    PermisoUsuario.objects.filter(modulo="documentos").delete()

    mig = importlib.import_module("imprenta.migrations.0002_seed_permisos_documentos")
    mig.sembrar(apps, None)

    def acciones(u):
        return set(PermisoUsuario.objects.filter(usuario=u, modulo="documentos", activo=True)
                   .values_list("permiso", flat=True))

    assert acciones(con_ajustes) == {"ver", "editar_estilo", "editar_notas", "editar_datos"}
    assert acciones(sin_ajustes) == set()


def test_la_vista_previa_de_un_recibo_real(client, jefe, cliente_factory):
    import datetime as dt

    from apps.tesoreria.models import Ingreso

    ing = Ingreso.objects.create(monto=Decimal("500"), descripcion="Pago de vasos", fecha=dt.date.today(),
                                 metodo="efectivo", cliente=cliente_factory(creado_por=jefe),
                                 creado_por=jefe)
    client.force_login(jefe)
    r = client.post(reverse("ajustes-documentos-vista"), {
        "seccion": "recibo_pago", "tipo": "recibo_pago", "ejemplo": str(ing.pk),
        "recibo_pago__col_rotulo_recibimos": "Pagó", "recibo_pago__bloque_letra": "on"})
    html = r.content.decode()
    assert "Pago de vasos" in html and ">Pagó<" in html
    assert "QUINIENTOS PESOS 00/100 M.N." in html
