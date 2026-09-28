"""LC 2026-09-28 — Deploy 2 (producto) del sprint de pendientes.

Decisiones de Oscar, literales (`docs/SPRINT-Pendientes-Sep28.md`):

1. **Proveedor ★ al cambiarlo → «preguntar al guardar»**, y el modal ofrece
   «sólo los que se pueden (vivos, sin egreso de esa línea, sin cotización
   pagada, con el proveedor anterior), todos marcados».
2. **Color de tarjeta → sólo alias y catálogo** (la descripción deja de decidir).
3. **HEIC → convertir a JPEG** (`pillow-heif`).
4. **@persona crea una tarea ligada al producto**, en el campo de tareas del
   producto, directo y sin IA; fecha: la que se escriba o la entrega del
   proyecto.
5. **Plegado móvil** de la ficha del cliente y de la ficha del producto.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.taller]


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def categoria(db):
    from apps.el_catalogo.models import CategoriaServicio
    return CategoriaServicio.objects.create(nombre="Textiles")


@pytest.fixture
def cliente(db, cliente_factory):
    return cliente_factory(razon_social="Optimist")


def _prov(razon):
    from apps.el_catalogo.models import Proveedor
    return Proveedor.objects.create(razon_social=razon, activo=True)


def _proyecto(cliente, nombre="Vivo", **extra):
    from apps.los_proyectos.models import Proyecto
    extra.setdefault("estado", "en_proceso_diseno")
    return Proyecto.objects.create(nombre=nombre, cliente=cliente, **extra)


def _linea(proyecto, servicio, **extra):
    from apps.los_proyectos.models import ProyectoProducto
    extra.setdefault("cantidad", 10)
    return ProyectoProducto.objects.create(proyecto=proyecto, servicio=servicio, **extra)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Proveedor ★: «¿También en estos proyectos?»
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def producto_con_dos(categoria):
    """Un producto cuyo principal es Alfa, que también puede surtir Zeta."""
    from apps.el_catalogo.models import Servicio
    alfa, zeta = _prov("Alfa Textiles"), _prov("Zeta Bordados")
    srv = Servicio.objects.create(nombre="Playera", categoria=categoria,
                                  costo=50, precio_base=100, proveedor_principal=alfa)
    srv.proveedores.set([alfa, zeta])
    return srv, alfa, zeta


def _post_principal(client, srv, categoria, ids):
    return client.post(f"/catalogo/{srv.pk}/editar", {
        "nombre": srv.nombre, "descripcion_default": "", "costo": "50",
        "precio_base": "100", "categoria": categoria.pk,
        "proveedores": [str(i) for i in ids],
        "proveedores_orden": ",".join(str(i) for i in ids),
    })


def test_elegibles_solo_las_vivas_con_el_proveedor_anterior(
        cliente, producto_con_dos):
    """La regla que acordó Oscar, línea por línea."""
    from apps.cotizaciones.models import Cotizacion
    from apps.el_catalogo.propagacion import lineas_para_proveedor
    from apps.tesoreria.models import CentroDeCosto, Egreso

    srv, alfa, zeta = producto_con_dos
    buena = _linea(_proyecto(cliente, "Bueno"), srv, proveedor=alfa)
    # Un proveedor puesto a mano para ese proyecto es una decisión: no se ofrece.
    _linea(_proyecto(cliente, "A mano"), srv, proveedor=zeta)
    # Cerrado y archivado: ya no se tocan.
    _linea(_proyecto(cliente, "Cerrado", estado="cerrado"), srv, proveedor=alfa)
    _linea(_proyecto(cliente, "Archivado", archivado=True), srv, proveedor=alfa)
    # Con egreso: ese dinero ya salió.
    centro, _ = CentroDeCosto.objects.get_or_create(
        slug="insumos-de-proyecto", defaults={"nombre": "Insumos de proyecto"})
    egreso = Egreso.objects.create(monto=Decimal("500.00"), descripcion="x",
                                   centro_de_costo=centro, fecha=dt.date.today())
    _linea(_proyecto(cliente, "Pagado a proveedor"), srv, proveedor=alfa, egreso=egreso)
    # Con cotización pagada: lo facturado no se mueve.
    pagado = _proyecto(cliente, "Cotización pagada")
    Cotizacion.objects.create(cliente=cliente, proyecto=pagado, version=1, estado="pagada")
    _linea(pagado, srv, proveedor=alfa)

    assert [linea.pk for linea in lineas_para_proveedor(srv, alfa.pk)] == [buena.pk]


def test_cambiar_el_principal_abre_el_modal_una_sola_vez(
        client, usuario_factory, categoria, cliente, producto_con_dos):
    """«Preguntar al guardar»: el modal se pide tras el redirect, y recargar la
    ficha ya no vuelve a preguntar (la pregunta sale de la sesión)."""
    srv, alfa, zeta = producto_con_dos
    _linea(_proyecto(cliente), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))

    resp = _post_principal(client, srv, categoria, [zeta.pk, alfa.pk])
    assert resp.status_code == 302
    srv.refresh_from_db()
    assert srv.proveedor_principal_id == zeta.pk

    html = client.get(f"/catalogo/{srv.pk}/editar").content.decode()
    assert f"/catalogo/{srv.pk}/propagar-proveedor?anterior={alfa.pk}" in html
    assert 'hx-trigger="load"' in html

    otra_vez = client.get(f"/catalogo/{srv.pk}/editar").content.decode()
    assert "propagar-proveedor" not in otra_vez


def test_sin_elegibles_no_aparece_nada(
        client, usuario_factory, categoria, cliente, producto_con_dos):
    srv, alfa, zeta = producto_con_dos
    _linea(_proyecto(cliente, "Cerrado", estado="cerrado"), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))
    _post_principal(client, srv, categoria, [zeta.pk, alfa.pk])
    html = client.get(f"/catalogo/{srv.pk}/editar").content.decode()
    assert "propagar-proveedor" not in html


def test_guardar_sin_cambiar_el_principal_no_pregunta(
        client, usuario_factory, categoria, cliente, producto_con_dos):
    srv, alfa, zeta = producto_con_dos
    _linea(_proyecto(cliente), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))
    _post_principal(client, srv, categoria, [alfa.pk, zeta.pk])
    html = client.get(f"/catalogo/{srv.pk}/editar").content.decode()
    assert "propagar-proveedor" not in html


def test_el_modal_lista_los_elegibles_todos_marcados(
        client, usuario_factory, cliente, producto_con_dos):
    srv, alfa, zeta = producto_con_dos
    srv.proveedor_principal = zeta
    srv.save(update_fields=["proveedor_principal"])
    l1 = _linea(_proyecto(cliente, "Gorras Kari"), srv, proveedor=alfa)
    l2 = _linea(_proyecto(cliente, "Playeras Kari"), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))

    html = client.get(f"/catalogo/{srv.pk}/propagar-proveedor", {"anterior": alfa.pk},
                      HTTP_HX_REQUEST="true").content.decode()
    assert "¿También en estos proyectos?" in html
    for linea in (l1, l2):
        assert f'name="lineas" value="{linea.pk}" checked' in html
    assert "Gorras Kari" in html and "Playeras Kari" in html


def test_al_confirmar_solo_cambian_las_marcadas(
        client, usuario_factory, cliente, producto_con_dos):
    srv, alfa, zeta = producto_con_dos
    srv.proveedor_principal = zeta
    srv.save(update_fields=["proveedor_principal"])
    marcada = _linea(_proyecto(cliente, "Sí"), srv, proveedor=alfa)
    desmarcada = _linea(_proyecto(cliente, "No"), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))

    resp = client.post(f"/catalogo/{srv.pk}/propagar-proveedor",
                       {"anterior": alfa.pk, "lineas": [str(marcada.pk)]},
                       HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == f"/catalogo/{srv.pk}/editar"
    marcada.refresh_from_db()
    desmarcada.refresh_from_db()
    assert marcada.proveedor_id == zeta.pk
    assert desmarcada.proveedor_id == alfa.pk


def test_el_post_vuelve_a_validar_cada_linea(
        client, usuario_factory, cliente, producto_con_dos):
    """Un id que llega del navegador no se cree: una línea cerrada, una con otro
    proveedor o una de otro producto se saltan aunque vengan marcadas."""
    from apps.el_catalogo.models import Servicio

    srv, alfa, zeta = producto_con_dos
    srv.proveedor_principal = zeta
    srv.save(update_fields=["proveedor_principal"])
    cerrada = _linea(_proyecto(cliente, "Cerrado", estado="cerrado"), srv, proveedor=alfa)
    ajena_srv = Servicio.objects.create(nombre="Gorra", categoria=srv.categoria,
                                        costo=10, precio_base=20)
    ajena = _linea(_proyecto(cliente, "Ajeno"), ajena_srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="super_admin"))

    client.post(f"/catalogo/{srv.pk}/propagar-proveedor",
                {"anterior": alfa.pk, "lineas": [str(cerrada.pk), str(ajena.pk)]},
                HTTP_HX_REQUEST="true")
    for linea in (cerrada, ajena):
        linea.refresh_from_db()
        assert linea.proveedor_id == alfa.pk


def test_sin_permiso_de_proyectos_no_se_aplica(
        client, usuario_factory, cliente, producto_con_dos):
    srv, alfa, zeta = producto_con_dos
    srv.proveedor_principal = zeta
    srv.save(update_fields=["proveedor_principal"])
    linea = _linea(_proyecto(cliente), srv, proveedor=alfa)
    client.force_login(usuario_factory(rol="disenador"))
    resp = client.post(f"/catalogo/{srv.pk}/propagar-proveedor",
                       {"anterior": alfa.pk, "lineas": [str(linea.pk)]})
    assert resp.status_code in (302, 403)
    linea.refresh_from_db()
    assert linea.proveedor_id == alfa.pk


def test_el_evento_esta_tipado():
    from typing import get_args

    from lib.portavoz_eventos import EventoTipo
    assert "catalogo.proveedor_propagado" in get_args(EventoTipo)


# ═════════════════════════════════════════════════════════════════════════════
# 2. Color de la tarjeta: sólo alias y catálogo
# ═════════════════════════════════════════════════════════════════════════════

from pathlib import Path  # noqa: E402

TPL_JS_TARJETA = Path("el-taller/templates/proyectos/_form_productos_js.html")


def test_la_descripcion_ya_no_pinta_la_tarjeta(cliente, categoria):
    """Oscar: «sólo alias y catálogo». Una especificación que menciona «roja» no
    pinta de rojo un producto que no lo es."""
    from apps.el_catalogo.models import Servicio

    srv = Servicio.objects.create(nombre="Playera", categoria=categoria, precio_base=100)
    linea = _linea(_proyecto(cliente), srv, nota="Impresión sobre la playera roja de siempre")
    assert linea.color_efectivo == linea.color_asignado
    assert linea.color_efectivo != "#e11d48"


def test_el_alias_y_el_catalogo_siguen_mandando(cliente, categoria):
    from apps.el_catalogo.models import Servicio

    srv = Servicio.objects.create(nombre="Playera negra", categoria=categoria, precio_base=100)
    linea = _linea(_proyecto(cliente), srv, nota="Color: verde")
    assert linea.color_efectivo == "#1f2937"          # el catálogo dice negra
    linea.nombre_proyecto = "Números Azules"
    assert linea.color_efectivo == "#465fff"          # y el alias manda sobre él


def test_la_descripcion_de_una_hermana_no_ocupa_su_color(cliente, categoria):
    """Al repartir, una hermana cuya DESCRIPCIÓN dice «azul» ya no se lleva el
    azul: lo que ocupa es el color que de verdad se ve."""
    from apps.el_catalogo.models import Servicio

    proyecto = _proyecto(cliente)
    srv = Servicio.objects.create(nombre="Gorra", categoria=categoria, precio_base=100)
    primera = _linea(proyecto, srv, nota="Bordado azul marino")
    otra = Servicio.objects.create(nombre="Tote", categoria=categoria, precio_base=100)
    segunda = _linea(proyecto, otra)
    assert primera.color == "#465fff"                  # le tocó el primero libre
    assert segunda.color != primera.color              # y el siguiente no lo repite


def test_la_version_congelada_tambien_ignora_la_descripcion():
    from apps.los_proyectos.models.producto_version import ProyectoProductoVersion

    # Sin producto ligado el nombre del catálogo es «Producto» (sin color), así
    # que sólo la descripción podría pintarla — y ya no cuenta.
    snap = ProyectoProductoVersion(nombre_proyecto="", nota="Tinta roja", color="#059669")
    assert snap.color_efectivo == "#059669"


def test_el_js_espejo_no_lee_la_descripcion():
    src = TPL_JS_TARJETA.read_text(encoding="utf-8")
    ini = src.index("function colorDeLaTarjeta")
    cuerpo = src[ini:src.index("function repintarColor")]
    assert "-nota" not in cuerpo
    assert "nombreCatalogo(card)" in cuerpo and "data-alias-input" in cuerpo


def test_la_migracion_arregla_solo_las_que_pintaba_la_descripcion(cliente, categoria):
    """0038: la línea que se pintaba por su descripción recibe un color libre;
    las demás no se mueven. Y correrla dos veces deja lo mismo."""
    import importlib

    from apps.el_catalogo.models import Servicio
    from apps.los_proyectos.models import ProyectoProducto
    from django.apps import apps as registro

    migracion = importlib.import_module(
        "apps.los_proyectos.migrations.0038_recolorear_sin_descripcion")

    proyecto = _proyecto(cliente, "Viejito")
    s1 = Servicio.objects.create(nombre="Uno", categoria=categoria, precio_base=100)
    s2 = Servicio.objects.create(nombre="Dos", categoria=categoria, precio_base=100)
    s3 = Servicio.objects.create(nombre="Tres", categoria=categoria, precio_base=100)
    a = _linea(proyecto, s1, orden=0)
    b = _linea(proyecto, s2, orden=1, nota="Estampado rojo")
    c = _linea(proyecto, s3, orden=2)
    # Como la dejaba el reparto viejo: la de la descripción, con el color de A.
    ProyectoProducto.objects.filter(pk=b.pk).update(color=a.color)
    antes_a, antes_c = a.color, c.color

    migracion._recolorear(registro, None)
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert (a.color, c.color) == (antes_a, antes_c)     # las demás, quietas
    assert b.color not in {a.color, c.color}             # la arreglada, sin choque

    primera = b.color
    migracion._recolorear(registro, None)
    b.refresh_from_db()
    assert b.color == primera                            # idempotente


# ═════════════════════════════════════════════════════════════════════════════
# 3. HEIC → JPEG
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def almacen_tmp(settings, tmp_path):
    from lib import almacen
    settings.MEDIOS_DIR = str(tmp_path / "medios")
    almacen.olvidar_meta()
    yield almacen
    almacen.olvidar_meta()


def _heic(ancho=320, alto=200, color=(200, 30, 30)) -> bytes:
    """Un HEIC DE VERDAD, codificado con pillow-heif (no un JPEG renombrado)."""
    import io

    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new("RGB", (ancho, alto), color).save(buf, format="HEIF", quality=80)
    datos = buf.getvalue()
    assert datos[4:12] == b"ftypheic"
    return datos


def test_la_dependencia_esta_fijada_y_se_puede_decodificar():
    reqs = Path("requirements.txt").read_text(encoding="utf-8")
    assert "pillow-heif==" in reqs
    from lib import almacen
    assert almacen.hay_decodificador_heic() is True


def test_un_heic_se_guarda_ya_como_jpeg_con_sus_derivados(almacen_tmp):
    almacen = almacen_tmp
    datos = almacen.guardar_bytes(_heic(), mime="image/heic", nombre="IMG_0042.HEIC")
    clave = datos["id"]

    guardado = almacen.meta(clave)
    assert guardado["mime"] == "image/jpeg"
    assert guardado["nombre"] == "IMG_0042.jpg"
    assert guardado["convertido_de"] == "image/heic"
    assert (guardado["ancho"], guardado["alto"]) == (320, 200)
    original = (almacen._dir_orig(clave) / "archivo").read_bytes()
    assert original[:2] == b"\xff\xd8"                     # bytes de JPEG
    assert guardado["bytes"] == len(original)
    assert guardado["variantes"] == {"w400": "w400.jpg", "w1000": "w1000.jpg"}
    assert almacen.url(clave).startswith("/medios/")        # se pinta por El Mostrador
    contenido, mime, _nombre = almacen.leer(clave)           # y el original también es JPEG
    assert mime == "image/jpeg" and contenido[:2] == b"\xff\xd8"


@pytest.mark.parametrize(("mime", "nombre"), [
    ("", "foto.heic"),                       # Chrome en Windows: tipo vacío
    ("application/octet-stream", "foto"),    # ni tipo ni extensión: la marca del archivo
])
def test_se_reconoce_aunque_el_navegador_no_diga_que_es_heic(almacen_tmp, mime, nombre):
    datos = almacen_tmp.guardar_bytes(_heic(), mime=mime, nombre=nombre)
    guardado = almacen_tmp.meta(datos["id"])
    assert guardado["mime"] == "image/jpeg"
    assert guardado["variantes"], "sin derivado, el navegador no la pinta"


def test_la_misma_foto_heic_dos_veces_sigue_siendo_un_archivo(almacen_tmp):
    a = almacen_tmp.guardar_bytes(_heic(), mime="image/heic", nombre="a.heic")
    b = almacen_tmp.guardar_bytes(_heic(), mime="image/heic", nombre="b.heic")
    assert a["id"] == b["id"] and b.get("duplicado") is True


def test_un_jpeg_no_se_toca(almacen_tmp):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (100, 80), "blue").save(buf, format="JPEG", quality=70)
    jpeg = buf.getvalue()
    datos = almacen_tmp.guardar_bytes(jpeg, mime="image/jpeg", nombre="x.jpg")
    guardado = almacen_tmp.meta(datos["id"])
    assert "convertido_de" not in guardado
    assert (almacen_tmp._dir_orig(datos["id"]) / "archivo").read_bytes() == jpeg


def test_la_subida_devuelve_y_espeja_el_jpeg(almacen_tmp, monkeypatch):
    """`lib.adjuntos.subir` es por donde pasan TODAS las subidas: el dato que le
    devuelve a la vista y la copia de Drive tienen que decir JPEG."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from lib import adjuntos

    visto = {}

    def _espejo(archivo, subcarpeta, *, nombre, mime, ruta_local):
        visto.update(nombre=nombre, mime=mime, ruta_local=ruta_local)
        return None, "sin Drive en pruebas"

    monkeypatch.setattr(adjuntos, "_espejar_en_drive", _espejo)
    archivo = SimpleUploadedFile("IMG_1.heic", _heic(), content_type="image/heic")
    res = adjuntos.subir(archivo, subcarpeta="Pruebas")
    assert res.ok
    assert res.data["mimeType"] == "image/jpeg" and res.data["name"] == "IMG_1.jpg"
    assert (visto["nombre"], visto["mime"]) == ("IMG_1.jpg", "image/jpeg")
    assert Path(visto["ruta_local"]).read_bytes()[:2] == b"\xff\xd8"


def test_a_un_chalan_con_vision_le_llega_jpeg():
    """Las APIs de visión no aceptan HEIC: el único punto por donde pasan las
    imágenes rumbo a un Chalán lo convierte."""
    import base64

    from lib.analistas.multimodal import normalizar_imagenes

    b64 = base64.b64encode(_heic()).decode()
    [img] = normalizar_imagenes([{"base64": b64, "media_type": "image/heic"}])
    assert img["media_type"] == "image/jpeg"
    assert base64.b64decode(img["base64"])[:2] == b"\xff\xd8"
