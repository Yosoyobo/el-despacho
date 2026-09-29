"""Los anexos de la cotización (Sep28): fichas técnicas al final del PDF.

Decisión de Oscar: «anexos de la cotización (se unen al final del PDF)». Lo que
se cuida aquí:

1. **Entrar**: PDF tal cual; Word/Excel convertidos a PDF; si el convertidor no
   contesta se guarda el original y se reintenta al armar el documento.
2. **El orden**: ↑/↓, y es el orden en que se pegan.
3. **El documento**: se pegan AL FINAL, antes de guardar en Drive — lo que se
   guarda es lo que se descarga y se manda por correo. Un anexo roto no tumba el
   documento: sale sin él y se avisa.
4. **La herencia**: la versión siguiente y un duplicado se los llevan.
5. **Las puertas**: permiso de editar + cotización viva; y El Chalán, que anexa
   un documento del papeleo pidiendo DOS permisos.

Gotenberg, Drive y Paperless se simulan en su frontera.
"""

from __future__ import annotations

import io
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def jefe(usuario_factory):
    return usuario_factory(rol="super_admin")


@pytest.fixture
def cot(cliente_factory, jefe):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem

    c = Cotizacion.objects.create(cliente=cliente_factory(creado_por=jefe),
                                  titulo="Termos Optimist", creado_por=jefe,
                                  estado="generada")
    CotizacionItem.objects.create(cotizacion=c, orden=0, concepto="Termo",
                                  cantidad=Decimal("10"), precio_unitario=Decimal("100"))
    return c


@pytest.fixture
def gotenberg_vivo(monkeypatch):
    """Un Gotenberg que convierte y une, sin red."""
    from lib import gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)
    monkeypatch.setattr(gotenberg, "office_a_pdf",
                        lambda c, n: b"%PDF-1.4 convertido de " + n.encode())
    uniones = []

    def _unir(pdfs):
        uniones.append(list(pdfs))
        return b"%PDF-1.4 UNIDO " + b"|".join(pdfs)

    monkeypatch.setattr(gotenberg, "unir", _unir)
    return uniones


@pytest.fixture
def gotenberg_caido(monkeypatch):
    from lib import gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: False)


def _pdf(txt="ficha"):
    return b"%PDF-1.4 " + txt.encode()


# ── 1. Entrar ────────────────────────────────────────────────────────────────


def test_un_pdf_entra_tal_cual_al_final(cot, jefe):
    from apps.cotizaciones import anexos

    r1 = anexos.agregar(cot, _pdf("uno"), "Ficha termo.pdf", jefe)
    r2 = anexos.agregar(cot, _pdf("dos"), "Garantia.pdf", jefe)
    assert r1.ok and r2.ok
    assert [a.nombre for a in cot.anexos.all()] == ["Ficha termo.pdf", "Garantia.pdf"]
    assert [a.orden for a in cot.anexos.all()] == [0, 1]
    assert all(a.es_pdf for a in cot.anexos.all())


def test_un_word_entra_convertido_con_su_nombre(cot, jefe, gotenberg_vivo):  # noqa: ARG001
    from apps.cotizaciones import anexos

    from lib import almacen

    r = anexos.agregar(cot, b"PK word", "Tabla de tallas.docx", jefe)
    assert r.ok
    a = cot.anexos.get()
    assert a.nombre == "Tabla de tallas.pdf"
    assert a.nombre_original == "Tabla de tallas.docx"
    assert a.es_pdf is True
    assert almacen.leer(a.archivo_clave)[0].startswith(b"%PDF")


def test_convertidor_caido_guarda_el_original_y_avisa(cot, jefe, gotenberg_caido):  # noqa: ARG001
    """La ficha no se pierde por un servicio caído."""
    from apps.cotizaciones import anexos

    r = anexos.agregar(cot, b"PK excel", "Precios.xlsx", jefe)
    assert r.ok
    assert r.nivel == "warning"
    a = cot.anexos.get()
    assert a.es_pdf is False
    assert a.nombre == "Precios.xlsx"


def test_lo_que_dice_pdf_y_no_lo_es_se_rechaza(cot, jefe):
    """Si se aceptara, al unirlo la cotización saldría sin sus anexos."""
    from apps.cotizaciones import anexos

    r = anexos.agregar(cot, b"<html>hola</html>", "ficha.pdf", jefe)
    assert not r.ok
    assert not cot.anexos.exists()


def test_otros_tipos_no_se_anexan(cot, jefe):
    from apps.cotizaciones import anexos

    r = anexos.agregar(cot, b"\xff\xd8\xff", "foto.jpg", jefe)
    assert not r.ok
    assert "PDF, Word o Excel" in r.mensaje


def test_hay_un_tope_de_anexos(cot, jefe):
    from apps.cotizaciones import anexos

    for i in range(anexos.MAX_ANEXOS):
        assert anexos.agregar(cot, _pdf(str(i)), f"f{i}.pdf", jefe).ok
    assert not anexos.agregar(cot, _pdf("x"), "sobra.pdf", jefe).ok


# ── 2. El orden ──────────────────────────────────────────────────────────────


def test_subir_y_bajar_cambia_el_orden(cot, jefe):
    from apps.cotizaciones import anexos

    for n in ("a", "b", "c"):
        anexos.agregar(cot, _pdf(n), f"{n}.pdf", jefe)
    c = cot.anexos.get(nombre="c.pdf")
    assert anexos.mover(c, "arriba")
    assert [a.nombre for a in cot.anexos.all()] == ["a.pdf", "c.pdf", "b.pdf"]
    a = cot.anexos.get(nombre="a.pdf")
    assert not anexos.mover(a, "arriba"), "el primero no sube más"


def test_quitar_no_borra_el_archivo_del_almacen(cot, jefe):
    """La misma llave puede estar en otra versión o en una cotización enviada."""
    from apps.cotizaciones import anexos

    from lib import almacen

    anexos.agregar(cot, _pdf("a"), "a.pdf", jefe)
    anexos.agregar(cot, _pdf("b"), "b.pdf", jefe)
    a = cot.anexos.get(nombre="a.pdf")
    clave = a.archivo_clave
    anexos.quitar(a)
    assert almacen.existe(clave)
    assert [(x.nombre, x.orden) for x in cot.anexos.all()] == [("b.pdf", 0)]


# ── 3. El documento ──────────────────────────────────────────────────────────


def test_el_pdf_se_arma_con_los_anexos_al_final_y_en_orden(cot, jefe, monkeypatch):
    from apps.cotizaciones import anexos, services

    anexos.agregar(cot, _pdf("uno"), "uno.pdf", jefe)
    anexos.agregar(cot, _pdf("dos"), "dos.pdf", jefe)
    anexos.mover(cot.anexos.get(nombre="dos.pdf"), "arriba")
    capturado = {}

    class _Res:
        ok = False
        error = "sin Drive"
        avisos: list = []

    def _falso(**kw):
        capturado.update(kw)
        return _Res()

    monkeypatch.setattr("lib.documentos.generar_pdf", _falso)
    services.generar_pdf(cot, jefe)
    assert capturado["anexos"] == [_pdf("dos"), _pdf("uno")]


def test_sin_anexos_el_documento_se_pide_como_siempre(cot, jefe, monkeypatch):
    """Nada cambia para las cotizaciones sin fichas."""
    from apps.cotizaciones import services

    capturado = {}

    class _Res:
        ok = False
        error = "sin Drive"

    monkeypatch.setattr("lib.documentos.generar_pdf",
                        lambda **kw: capturado.update(kw) or _Res())
    services.generar_pdf(cot, jefe)
    assert "anexos" not in capturado


def test_los_anexos_se_pegan_ANTES_de_guardar_en_drive(monkeypatch, gotenberg_vivo):
    """Lo guardado tiene que ser lo que se descarga y se manda por correo."""
    from lib import documentos, gotenberg
    from lib.google_drive import drive

    monkeypatch.setattr(gotenberg, "html_a_pdf", lambda html, pagina=None: b"%PDF-1.4 cot")
    monkeypatch.setattr(documentos, "motor_preferido", lambda: "auto")
    subido = {}
    monkeypatch.setattr(drive, "esta_configurado", lambda: True)
    monkeypatch.setattr(drive, "obtener_o_crear_subcarpeta", lambda s: "carpeta")
    monkeypatch.setattr(drive, "_subir_contenido",
                        lambda c, n, carp, mime: subido.update(c=c) or {"id": "D1"})
    res = documentos.generar_pdf(html="<p>x</p>", nombre="COT", anexos=[_pdf("ficha")])
    assert res.ok
    assert gotenberg_vivo[0] == [b"%PDF-1.4 cot", _pdf("ficha")]
    assert subido["c"].startswith(b"%PDF-1.4 UNIDO"), "Drive recibió la versión SIN anexos"
    assert res.pdf_bytes == subido["c"]


def test_si_no_se_pueden_unir_sale_sin_anexos_y_avisa(monkeypatch):
    """Una cotización sin su ficha técnica es mejor que una que no sale."""
    from lib import documentos, gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: False)
    pdf, avisos = documentos._con_anexos(b"%PDF-1.4 cot", [_pdf("ficha")])
    assert pdf == b"%PDF-1.4 cot"
    assert avisos and "sin sus anexos" in avisos[0]


def test_un_word_que_no_se_convirtio_se_reintenta_y_se_cura(cot, jefe, monkeypatch):
    """Al subir el convertidor estaba caído; al armar el documento ya contesta."""
    from apps.cotizaciones import anexos

    from lib import gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: False)
    anexos.agregar(cot, b"PK word", "Garantia.docx", jefe)
    assert cot.anexos.get().es_pdf is False

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)
    monkeypatch.setattr(gotenberg, "office_a_pdf", lambda c, n: b"%PDF-1.4 curado")
    pdfs, avisos = anexos.pdfs_para_documento(cot)
    assert pdfs == [b"%PDF-1.4 curado"]
    assert not avisos
    a = cot.anexos.get()
    assert a.es_pdf is True and a.nombre == "Garantia.pdf"


def test_un_anexo_que_no_se_puede_leer_se_salta_con_aviso(cot, jefe):
    from apps.cotizaciones import anexos
    from apps.cotizaciones.models import CotizacionAnexo

    anexos.agregar(cot, _pdf("bueno"), "bueno.pdf", jefe)
    CotizacionAnexo.objects.create(cotizacion=cot, orden=5, nombre="perdido.pdf",
                                   archivo_clave="0" * 64)
    pdfs, avisos = anexos.pdfs_para_documento(cot)
    assert pdfs == [_pdf("bueno")]
    assert any("perdido.pdf" in a for a in avisos)


# ── 4. La herencia ───────────────────────────────────────────────────────────


@pytest.fixture
def proyecto_con_producto(proyecto_factory, jefe):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto

    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción",
                                                     defaults={"orden": 10})
    srv = Servicio.objects.create(nombre="Termo", precio_base="100", costo="30",
                                  categoria=cat)
    p = proyecto_factory(nombre="Termos Optimist", creado_por=jefe)
    ProyectoProducto.objects.create(proyecto=p, servicio=srv, cantidad=3,
                                    incluir_en_calculo=True)
    return p


def test_la_version_siguiente_hereda_los_anexos(proyecto_con_producto, jefe):
    from apps.cotizaciones import anexos, services

    v1 = services.generar_desde_proyecto(proyecto_con_producto, jefe)
    anexos.agregar(v1, _pdf("ficha"), "Ficha.pdf", jefe)
    v2 = services.generar_desde_proyecto(proyecto_con_producto, jefe)
    assert v2.version == v1.version + 1
    assert [a.nombre for a in v2.anexos.all()] == ["Ficha.pdf"]
    # Misma llave: la ficha ocupa UN archivo aunque viaje en dos versiones.
    assert v2.anexos.get().archivo_clave == v1.anexos.get().archivo_clave


def test_la_vista_previa_no_deja_anexos_colgados(proyecto_con_producto, jefe, client):
    """La vista previa genera de verdad y deshace: los anexos heredados también
    se deshacen."""
    from apps.cotizaciones import anexos, services
    from apps.cotizaciones.models import CotizacionAnexo

    v1 = services.generar_desde_proyecto(proyecto_con_producto, jefe)
    anexos.agregar(v1, _pdf("ficha"), "Ficha.pdf", jefe)
    antes = CotizacionAnexo.objects.count()
    client.force_login(jefe)
    r = client.get(f"/proyectos/{proyecto_con_producto.pk}/cotizacion/vista-previa")
    assert r.status_code == 200
    assert CotizacionAnexo.objects.count() == antes


def test_duplicar_se_lleva_los_anexos(cot, jefe, monkeypatch):
    from apps.cotizaciones import anexos, services

    monkeypatch.setattr(services, "emitir", lambda evt: None)
    anexos.agregar(cot, _pdf("ficha"), "Ficha.pdf", jefe)
    copia = services.duplicar(cot, jefe)
    assert [a.nombre for a in copia.anexos.all()] == ["Ficha.pdf"]


# ── 5. Las puertas ───────────────────────────────────────────────────────────


def _subir(client, cot, nombre="Ficha.pdf", contenido=None):
    f = io.BytesIO(contenido if contenido is not None else _pdf("ficha"))
    f.name = nombre
    return client.post(f"/cotizaciones/{cot.pk}/anexos/subir/", {"archivo": f},
                       HTTP_HX_REQUEST="true")


def test_subir_desde_la_pagina_repinta_el_recuadro(client, cot, jefe):
    client.force_login(jefe)
    r = _subir(client, cot)
    assert r.status_code == 200
    cuerpo = r.content.decode()
    assert 'id="cot-anexos"' in cuerpo
    assert "Ficha.pdf" in cuerpo
    assert cot.anexos.count() == 1


def test_la_pagina_de_la_cotizacion_muestra_el_recuadro(client, cot, jefe):
    client.force_login(jefe)
    cuerpo = client.get(f"/cotizaciones/{cot.pk}/").content.decode()
    assert 'id="cot-anexos"' in cuerpo
    assert f"/cotizaciones/{cot.pk}/anexos/subir/" in cuerpo


def test_sin_permiso_de_editar_no_se_anexa(client, cot, usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario
    from lib.permisos import invalidar_cache_permisos

    u = usuario_factory(rol="miembro")
    PermisoUsuario.objects.create(usuario=u, modulo="cotizaciones", permiso="ver",
                                  activo=True)
    invalidar_cache_permisos()
    client.force_login(u)
    assert _subir(client, cot).status_code == 403
    assert not cot.anexos.exists()
    # Y en la página no se le ofrece el formulario.
    cuerpo = client.get(f"/cotizaciones/{cot.pk}/").content.decode()
    assert "/anexos/subir/" not in cuerpo


def test_una_cotizacion_cerrada_no_cambia_su_documento(client, cot, jefe):
    """Aprobada, es testimonio de lo que se le mandó al cliente."""
    cot.estado = "aprobada"
    cot.save(update_fields=["estado"])
    client.force_login(jefe)
    assert _subir(client, cot).status_code == 403


def test_ver_un_anexo_pide_permiso_de_ver_cotizaciones(client, cot, jefe, usuario_factory):
    from apps.cotizaciones import anexos

    anexos.agregar(cot, _pdf("secreto"), "Ficha.pdf", jefe)
    a = cot.anexos.get()
    client.force_login(jefe)
    r = client.get(f"/cotizaciones/anexos/{a.pk}/")
    assert r.status_code == 200
    assert r["Content-Type"] == "application/pdf"
    client.force_login(usuario_factory(rol="miembro"))
    r = client.get(f"/cotizaciones/anexos/{a.pk}/")
    assert r.status_code in (302, 403)
    assert b"secreto" not in r.content


def test_mover_y_quitar_por_la_pagina(client, cot, jefe):
    from apps.cotizaciones import anexos

    anexos.agregar(cot, _pdf("a"), "a.pdf", jefe)
    anexos.agregar(cot, _pdf("b"), "b.pdf", jefe)
    b = cot.anexos.get(nombre="b.pdf")
    client.force_login(jefe)
    client.post(f"/cotizaciones/anexos/{b.pk}/mover/", {"dir": "arriba"},
                HTTP_HX_REQUEST="true")
    assert [a.nombre for a in cot.anexos.all()] == ["b.pdf", "a.pdf"]
    r = client.post(f"/cotizaciones/anexos/{b.pk}/quitar/", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert [a.nombre for a in cot.anexos.all()] == ["a.pdf"]


def test_el_recuadro_no_usa_hx_params_none():
    """`hx-params="none"` se lleva también lo que manda `hx-vals`: el ↑/↓
    postearía un cuerpo vacío (lección del 28 de agosto)."""
    import re
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent.parent
    t = (raiz / "el-taller/templates/cotizaciones/_anexos.html").read_text()
    # El comentario de la plantilla lo MENCIONA para explicarlo; se mira el HTML.
    t = re.sub(r"\{% comment %\}.*?\{% endcomment %\}", "", t, flags=re.S)
    assert 'hx-params="none"' not in t
    assert 'hx-vals=\'{"dir": "arriba"}\'' in t


# ── El Chalán ────────────────────────────────────────────────────────────────


@pytest.fixture
def papeleo_con_ficha(monkeypatch):
    from lib import paperless

    monkeypatch.setattr(paperless, "esta_configurado", lambda: True)
    monkeypatch.setattr(paperless, "detalle", lambda i: {"id": int(i),
                                                         "titulo": "Ficha termo"})
    monkeypatch.setattr(paperless, "archivo",
                        lambda i, cara="preview": (_pdf("del papeleo"), "application/pdf"))


def test_el_chalan_anexa_un_documento_del_papeleo(cot, jefe, papeleo_con_ficha):  # noqa: ARG001
    from apps.el_dictado.ejecutores import EJECUTORES

    r = EJECUTORES["anexar_a_cotizacion"]({"codigo": cot.codigo, "documento_id": "#45"},
                                          jefe, {})
    assert r["entidad_id"] == cot.pk
    a = cot.anexos.get()
    assert a.nombre == "Ficha termo.pdf"


def test_aplicado_por_el_dictado_deja_el_boton_a_la_cotizacion(cot, jefe,
                                                               papeleo_con_ficha):  # noqa: ARG001
    """`services.aplicar` descarta lo que devuelve el ejecutor: el botón «Ir a
    la cotización» del resultado sale de `accion.entidad_tipo/entidad_id`."""
    from apps.el_dictado import services
    from apps.el_dictado.models import Dictado, DictadoAccion

    d = Dictado.objects.create(autor=jefe, texto_crudo="anexa la ficha",
                               estado="esperando_confirmacion")
    a = DictadoAccion.objects.create(
        dictado=d, orden=0, tipo="anexar_a_cotizacion", descripcion="Anexa",
        payload={"codigo": cot.codigo, "documento_id": 45}, confirmada=True)
    services.aplicar(dictado=d, usuario=jefe)
    a.refresh_from_db()
    assert a.aplicada, a.error_al_aplicar
    assert (a.entidad_tipo, a.entidad_id) == ("cotizacion", cot.pk)
    assert cot.anexos.count() == 1


def test_el_chalan_pide_permiso_de_ver_el_papeleo(cot, usuario_factory,
                                                  papeleo_con_ficha):  # noqa: ARG001
    """Con editar cotizaciones sin ver papeleo se podría sacar al PDF de un
    cliente un contrato que no se tiene permiso de leer."""
    from apps.el_dictado.ejecutores import EJECUTORES

    from cuentas.models.permiso_usuario import PermisoUsuario
    from lib.permisos import invalidar_cache_permisos

    u = usuario_factory(rol="miembro")
    for p in ("ver", "editar"):
        PermisoUsuario.objects.create(usuario=u, modulo="cotizaciones", permiso=p,
                                      activo=True)
    invalidar_cache_permisos()
    with pytest.raises(ValueError, match="papeleo"):
        EJECUTORES["anexar_a_cotizacion"]({"codigo": cot.codigo, "documento_id": 45},
                                          u, {})
    assert not cot.anexos.exists()


def test_la_accion_esta_en_los_tres_lugares():
    from pathlib import Path

    from apps.el_dictado.ejecutores import EJECUTORES

    from lib.dictado_catalogo import COMANDOS_DICTADO, _gating_checks

    raiz = Path(__file__).resolve().parent.parent.parent
    prompt = (raiz / "el-taller/apps/el_dictado/prompt.py").read_text()
    comando = next(c for c in COMANDOS_DICTADO if c["tipo"] == "anexar_a_cotizacion")
    assert "anexar_a_cotizacion" in EJECUTORES
    assert "anexar_a_cotizacion" in prompt
    assert comando["gating"] in _gating_checks()


def test_la_propuesta_se_ofrece_solo_con_los_dos_permisos(usuario_factory, jefe):
    from lib.dictado_catalogo import comandos_para

    solo_cot = usuario_factory(rol="miembro")
    from cuentas.models.permiso_usuario import PermisoUsuario
    from lib.permisos import invalidar_cache_permisos

    PermisoUsuario.objects.create(usuario=solo_cot, modulo="cotizaciones",
                                  permiso="editar", activo=True)
    invalidar_cache_permisos()
    assert "anexar_a_cotizacion" not in {c["tipo"] for c in comandos_para(solo_cot)}
    assert "anexar_a_cotizacion" in {c["tipo"] for c in comandos_para(jefe)}


def test_el_detalle_de_la_cotizacion_dice_sus_anexos(cot, jefe):
    """El Chalán contesta «¿ya lleva la ficha?» sin abrir el PDF."""
    from apps.cotizaciones import anexos

    import capacidades.lecturas  # noqa: F401 — importar es lo que registra
    from capacidades.registro import CAPACIDADES

    anexos.agregar(cot, _pdf("ficha"), "Ficha termo.pdf", jefe)
    r = CAPACIDADES["detalle_cotizacion"].fn({"codigo": cot.codigo}, jefe)
    assert r["anexos"] == ["Ficha termo.pdf"]


def test_unir_y_convertir_estan_declarados_como_no_de_chat():
    """La regla del repo: lo que no se pide por chat se DECLARA."""
    from lib.dictado_catalogo import CONSULTAS_CHAT

    texto = " ".join(c["que"] for c in CONSULTAS_CHAT)
    assert "Unir en un PDF" in texto
    assert "NO se pide por chat" in texto
