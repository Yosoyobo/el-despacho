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


# ═════════════════════════════════════════════════════════════════════════════
# 4. @persona crea una tarea ligada al producto (directo, sin IA)
# ═════════════════════════════════════════════════════════════════════════════

TPL_TAREAS = Path("el-taller/templates/proyectos/_producto_tareas.html")
LUNES = dt.date(2026, 9, 28)   # un lunes, para que los días de la semana se lean


@pytest.mark.parametrize(("texto", "fecha", "resto"), [
    ("revisar el bordado el viernes", dt.date(2026, 10, 2), "revisar el bordado"),
    ("manda el arte mañana", dt.date(2026, 9, 29), "manda el arte"),
    ("para pasado mañana entregar", dt.date(2026, 9, 30), "entregar"),
    ("el próximo miércoles junta", dt.date(2026, 9, 30), "junta"),
    ("el lunes cotizar", dt.date(2026, 10, 5), "cotizar"),      # dicho en lunes: el que entra
    ("hoy mismo", LUNES, "mismo"),
    ("revisar 15/10", dt.date(2026, 10, 15), "revisar"),
    ("revisar 15/10/27", dt.date(2027, 10, 15), "revisar"),
    ("antes del 3/1 entregar", dt.date(2027, 1, 3), "entregar"),  # ya pasó: el año que entra
    ("el 5 de octubre junta", dt.date(2026, 10, 5), "junta"),
    ("15-10-2026 x", dt.date(2026, 10, 15), "x"),
])
def test_la_fecha_escrita_se_reconoce_y_se_quita_del_titulo(texto, fecha, resto):
    from lib.fecha import fecha_en_texto
    assert fecha_en_texto(texto, LUNES) == (fecha, resto)


@pytest.mark.parametrize("texto", [
    "por la mañana llamar",   # la hora del día, no el día de mañana
    "31/02 revisar",          # no es fecha real
    "LC-0044 revisar",        # un código no es fecha
    "10-20 piezas",           # un rango tampoco
    "sin fecha",
])
def test_lo_que_no_es_fecha_se_queda_en_el_titulo(texto):
    from lib.fecha import fecha_en_texto
    fecha, resto = fecha_en_texto(texto, LUNES)
    assert fecha is None and resto == texto


@pytest.fixture
def equipo(usuario_factory):
    from cuentas.models.usuario import Usuario

    def _u(email, nombre):
        u = usuario_factory(rol="super_admin", email=email)
        Usuario.objects.filter(pk=u.pk).update(nombre_completo=nombre)
        u.refresh_from_db()
        return u

    return {
        "jorge": _u("jorgeberebichez@gmail.com", "Jorge Berebichez"),
        "karla_a": _u("karla.a@lc.mx", "Karla Alvarez"),
        "karla_m": _u("karla.m@lc.mx", "Karla Mendoza"),
    }


def test_la_mencion_se_resuelve_sin_adivinar(equipo):
    from apps.los_proyectos.tarea_rapida import resolver_mencion

    assert resolver_mencion("jorgeberebichez") == (equipo["jorge"], "")
    assert resolver_mencion("jorge")[0] == equipo["jorge"]            # nombre de pila único
    persona, error = resolver_mencion("karla")                        # dos Karlas
    assert persona is None and "2 personas" in error
    persona, error = resolver_mencion("nadie")
    assert persona is None and "No encontré" in error


@pytest.fixture
def linea_viva(cliente, categoria):
    from apps.el_catalogo.models import Servicio
    from django.utils import timezone

    entrega = timezone.make_aware(dt.datetime(2026, 10, 20, 12, 0))
    proyecto = _proyecto(cliente, "Gorras Kari", fecha_compromiso=entrega)
    srv = Servicio.objects.create(nombre="Gorra", categoria=categoria, precio_base=100)
    return _linea(proyecto, srv)


def _url(linea):
    return f"/proyectos/{linea.proyecto_id}/producto/{linea.pk}/tarea-rapida"


def test_arroba_mas_texto_crea_la_tarea_ligada_al_producto(client, equipo, linea_viva, monkeypatch):
    from apps.el_pizarron.models import Tarea

    monkeypatch.setattr("lib.fecha.ahora_mx", lambda: dt.datetime(2026, 9, 28, 10, 0))
    client.force_login(equipo["jorge"])
    resp = client.post(_url(linea_viva), {"texto": "@jorge revisar el bordado el viernes"},
                       HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    tarea = Tarea.objects.get(producto=linea_viva)
    assert tarea.titulo == "Revisar el bordado"
    assert tarea.asignada_a == equipo["jorge"]
    assert tarea.fecha_compromiso == dt.date(2026, 10, 2)
    assert tarea.proyecto_id == linea_viva.proyecto_id
    html = resp.content.decode()
    assert f'id="tareas-producto-{linea_viva.pk}"' in html       # el bloque repintado…
    assert "Revisar el bordado" in html                          # …con la tarea nueva
    assert "></textarea>" in html                                # …y el campo limpio


def test_sin_fecha_toma_la_entrega_del_proyecto(client, equipo, linea_viva):
    from apps.el_pizarron.models import Tarea

    client.force_login(equipo["jorge"])
    resp = client.post(_url(linea_viva), {"texto": "@jorge mandar el arte"})
    tarea = Tarea.objects.get(producto=linea_viva)
    assert tarea.fecha_compromiso == dt.date(2026, 10, 20)
    assert "la entrega del proyecto" in resp.content.decode()


def test_dos_menciones_la_segunda_queda_de_corresponsable(client, equipo, linea_viva):
    from apps.el_pizarron.models import Tarea

    client.force_login(equipo["jorge"])
    client.post(_url(linea_viva), {"texto": "@jorge @karla.m cotizar el bordado"})
    tarea = Tarea.objects.get(producto=linea_viva)
    assert tarea.asignada_a == equipo["jorge"]
    assert list(tarea.responsables.all()) == [equipo["karla_m"]]
    assert tarea.titulo == "Cotizar el bordado"


@pytest.mark.parametrize(("texto", "pista"), [
    ("@karla revisar", "2 personas"),       # dos con ese nombre: no se adivina
    ("@nadie revisar", "No encontré"),
    ("revisar el bordado", "Escribe @"),    # sin mención no hay a quién
    ("@jorge", "¿Qué hay que hacer?"),      # sin tarea no hay qué
])
def test_lo_dudoso_no_crea_nada_y_conserva_lo_escrito(client, equipo, linea_viva, texto, pista):
    from apps.el_pizarron.models import Tarea

    client.force_login(equipo["jorge"])
    html = client.post(_url(linea_viva), {"texto": texto}).content.decode()
    assert not Tarea.objects.filter(producto=linea_viva).exists()
    assert pista in html
    assert f">{texto}</textarea>" in html


def test_sin_permiso_de_editar_el_proyecto_no_se_crea(client, usuario_factory, linea_viva):
    from apps.el_pizarron.models import Tarea

    client.force_login(usuario_factory(rol="disenador"))
    resp = client.post(_url(linea_viva), {"texto": "@jorge revisar"})
    assert resp.status_code == 403
    assert not Tarea.objects.exists()


def test_la_linea_tiene_que_ser_de_ese_proyecto(client, equipo, linea_viva, cliente):
    otro = _proyecto(cliente, "Ajeno")
    client.force_login(equipo["jorge"])
    resp = client.post(f"/proyectos/{otro.pk}/producto/{linea_viva.pk}/tarea-rapida",
                       {"texto": "@jorge revisar"})
    assert resp.status_code == 404


def test_el_campo_no_viaja_en_el_autoguardado_y_la_lista_blanca_conserva_el_texto():
    """Las dos trampas documentadas del bloque: el campo sin `name` y
    `hx-params="none"`, que se llevaría el `hx-vals` y mandaría el cuerpo vacío."""
    import re

    src = TPL_TAREAS.read_text(encoding="utf-8")
    campo = re.search(r"<textarea[^>]*data-tarea-rapida-campo[^>]*>", src, re.S).group(0)
    assert " name=" not in campo
    assert "data-referencias" in campo                   # la lista de personas al teclear @
    boton = re.search(r"<button[^>]*data-tarea-rapida=[^>]*>", src, re.S).group(0)
    assert 'hx-params="texto"' in boton
    assert "hx-vals='js:{texto:" in boton
    assert 'type="button"' in boton


def test_el_enter_solo_crea_con_mencion_y_nunca_a_media_letra():
    js = TPL_JS_TARJETA.read_text(encoding="utf-8")
    ini = js.index("textarea[data-tarea-rapida-campo]")
    bloque = js[ini - 400:ini + 900]
    assert "e.isComposing" in bloque and "e.shiftKey" in bloque
    assert "RE_MENCION.test" in bloque


def test_la_tarjeta_del_detalle_trae_el_bloque(client, equipo, linea_viva):
    client.force_login(equipo["jorge"])
    html = client.get(f"/proyectos/{linea_viva.proyecto_id}/").content.decode()
    assert f'data-tarea-rapida-campo="{linea_viva.pk}"' in html
    assert f"/producto/{linea_viva.pk}/tarea-rapida" in html


# ═════════════════════════════════════════════════════════════════════════════
# 5. Plegado móvil: ficha del cliente y ficha del producto
# ═════════════════════════════════════════════════════════════════════════════
# Contrato de `input.css` / `ui.js` (ver `tests/taller/test_plegado_movil.py`):
# `[data-movil-plegable]:not([data-abierto]) > [data-movil-cuerpo]` se esconde
# en el celular. Tres cosas fallan EN SILENCIO y sólo se ven en un teléfono:
# - un cuerpo que no es HIJO DIRECTO de su plegable no se pliega;
# - un plegable sin asa (o con el asa DENTRO del cuerpo) no se puede volver a
#   abrir: su contenido queda inalcanzable;
# - un asa o un cuerpo sueltos, sin plegable arriba, son basura que confunde al
#   siguiente que lea la plantilla.
# En escritorio no cambia nada: la media query no aplica y la flecha es
# `md:hidden`.


class _Plegables:
    """Recorre el HTML y anota, por cada plegable, si su cuerpo es hijo directo
    y si tiene un asa fuera del cuerpo. También junta asas/cuerpos sueltos."""

    VACIOS = {"br", "hr", "img", "input", "meta", "link", "path", "circle",
              "rect", "source", "col", "wbr"}

    def __init__(self, html: str):
        import re
        from html.parser import HTMLParser

        self.secciones: dict[str, dict] = {}
        self.sueltos: list[str] = []
        self.flechas_sin_md_hidden: list[str] = []
        pila: list[tuple[str, dict]] = []
        yo = self

        class _P(HTMLParser):
            def handle_starttag(self, tag, attrs):
                d = dict(attrs)
                plegable_arriba = next(
                    (a for _t, a in reversed(pila) if "data-movil-plegable" in a), None)
                if "data-movil-plegable" in d:
                    yo.secciones[d["data-movil-plegable"]] = {
                        "cuerpo_directo": False, "asa": False,
                        "abierto": "data-movil-abierto" in d,
                    }
                if "data-movil-cuerpo" in d:
                    padre = pila[-1][1] if pila else {}
                    if "data-movil-plegable" in padre:
                        yo.secciones[padre["data-movil-plegable"]]["cuerpo_directo"] = True
                    else:
                        yo.sueltos.append(f"cuerpo bajo <{pila[-1][0] if pila else ''}>")
                if "data-movil-asa" in d:
                    dentro_del_cuerpo = any("data-movil-cuerpo" in a for _t, a in pila)
                    if plegable_arriba is None:
                        yo.sueltos.append("asa sin plegable")
                    elif not dentro_del_cuerpo:
                        yo.secciones[plegable_arriba["data-movil-plegable"]]["asa"] = True
                if "data-movil-flecha" in d and "md:hidden" not in (d.get("class") or ""):
                    yo.flechas_sin_md_hidden.append(tag)
                texto = self.get_starttag_text() or ""
                if tag not in _Plegables.VACIOS and not texto.endswith("/>"):
                    pila.append((tag, d))

            def handle_endtag(self, tag):
                for i in range(len(pila) - 1, -1, -1):
                    if pila[i][0] == tag:
                        del pila[i:]
                        return

        p = _P(convert_charrefs=True)
        p.feed(re.sub(r"<script.*?</script>", "", html, flags=re.S))

    def rotos(self) -> list[str]:
        malos = [f"{k}: cuerpo no es hijo directo" for k, v in self.secciones.items()
                 if not v["cuerpo_directo"]]
        malos += [f"{k}: sin asa fuera del cuerpo" for k, v in self.secciones.items()
                  if not v["asa"]]
        return malos + self.sueltos + [f"flecha visible en escritorio <{t}>"
                                       for t in self.flechas_sin_md_hidden]


@pytest.fixture
def admin(db, usuario_factory):
    return usuario_factory(rol="super_admin")


@pytest.mark.django_db
def test_la_ficha_del_cliente_pliega_lo_de_consulta_y_deja_a_la_vista_lo_demas(
        client, admin, cliente):
    """Oscar: en el celular la ficha del cliente nace con lo que se consulta de
    vez en cuando plegado. Las notas, los proyectos y el contacto —lo que se
    busca al entrar— quedan a la vista."""
    cliente.notas = "Paga a 30 días"
    cliente.save()
    client.force_login(admin)
    resp = client.get(f"/cartera/{cliente.pk}/")
    assert resp.status_code == 200
    html = resp.content.decode()
    p = _Plegables(html)
    assert not p.rotos(), p.rotos()
    # «portal» (La Recepción, S5): quién del cliente entra al portal — se consulta
    # de vez en cuando, así que nace plegado como el papeleo.
    assert set(p.secciones) == {"cotizaciones", "facturas", "ingresos", "ubicacion",
                                "papeleo", "portal", "identificacion"}
    assert "Paga a 30 días" in html


@pytest.mark.django_db
def test_la_ficha_del_producto_al_editar_se_pliega_bien(client, admin, producto_con_dos):
    srv, *_ = producto_con_dos
    client.force_login(admin)
    resp = client.get(f"/catalogo/{srv.pk}/editar")
    assert resp.status_code == 200
    p = _Plegables(resp.content.decode())
    assert not p.rotos(), p.rotos()
    assert set(p.secciones) == {"imagen", "descripcion", "proveedores", "procesos", "usos"}
    # Sin errores, nada nace abierto.
    assert not any(v["abierto"] for v in p.secciones.values())


@pytest.mark.django_db
def test_en_el_alta_del_producto_no_se_pliega_nada(client, admin, categoria):
    """En el alta se llena todo: esconder campos sería esconder el trabajo. Y
    sin plegable no quedan asas ni cuerpos sueltos."""
    client.force_login(admin)
    resp = client.get("/catalogo/nuevo")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "data-movil-" not in html


@pytest.mark.django_db
def test_un_recuadro_con_error_nace_abierto(client, admin, producto_con_dos, categoria):
    """Plegar el recuadro que trae el error sería esconder por qué no se guardó."""
    srv, alfa, _zeta = producto_con_dos
    client.force_login(admin)
    resp = client.post(f"/catalogo/{srv.pk}/editar", {
        "nombre": srv.nombre, "descripcion_default": "", "costo": "50",
        "precio_base": "100", "categoria": categoria.pk,
        "proveedores": [str(alfa.pk), "999999"],
        "proveedores_orden": f"{alfa.pk},999999",
    })
    assert resp.status_code == 200          # re-render con el error, no redirect
    p = _Plegables(resp.content.decode())
    assert not p.rotos(), p.rotos()
    assert p.secciones["proveedores"]["abierto"]
    assert not p.secciones["descripcion"]["abierto"]


@pytest.mark.django_db
def test_los_recuadros_compartidos_no_se_pliegan_donde_no_se_pidio(client, admin):
    """`_ubicacion.html` y `papeleo/_recuadro.html` también viven en la ficha
    del proveedor: ahí no se pidió plegar y no se pliega."""
    client.force_login(admin)
    prov = _prov("Proveedor Suelto")
    resp = client.get(f"/catalogo/proveedores/{prov.pk}/")
    assert resp.status_code == 200
    html = resp.content.decode()
    # Los dos recuadros compartidos SÍ se pintaron (si no, el candado de abajo
    # pasaría por la razón equivocada)…
    assert "Ubicación y dirección" in html and "Buscar en el archivo" in html
    # …y sin plegar.
    assert "data-movil-" not in html
