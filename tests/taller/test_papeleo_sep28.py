"""El papeleo, Sep28: aviso al entrar, ligado tras el OCR, unir PDFs y Office→PDF.

Decisiones de Oscar (9 rondas, `docs/SPRINT-Pendientes-Sep28.md`):

- **Aviso** a quien puede VER el papeleo (push, opt-out), sólo si está prendido.
- **Ligado automático** cada 15 min, sólo lo de las últimas 48 h sin dueño, con
  el mismo criterio cobarde de siempre.
- **Unir PDFs** en la pantalla del Papeleo; el resultado se baja y se ofrece
  archivar.
- **Word/Excel se convierten al subir**; si el convertidor no contesta, se
  archiva el original y se avisa.

Paperless y Gotenberg no existen aquí: se simulan en la frontera (`lib.paperless`
y `lib.gotenberg`), igual que los tests del papeleo que ya había.
"""

from __future__ import annotations

import io

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


# ── Ayudas ──────────────────────────────────────────────────────────────────


def _dar_permiso(usuario, modulo, permiso):
    from cuentas.models.permiso_usuario import PermisoUsuario
    from lib.permisos import invalidar_cache_permisos

    PermisoUsuario.objects.update_or_create(
        usuario=usuario, modulo=modulo, permiso=permiso, defaults={"activo": True})
    invalidar_cache_permisos()


def _cfg(**campos):
    from ajustes.models import ConfiguracionPapeleo

    cfg = ConfiguracionPapeleo.obtener()
    for k, v in campos.items():
        setattr(cfg, k, v)
    cfg.save()
    return cfg


@pytest.fixture
def jefe(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    return u


@pytest.fixture
def archivo_conectado(monkeypatch):
    from lib import paperless

    monkeypatch.setattr(paperless, "esta_configurado", lambda: True)
    monkeypatch.setattr(paperless, "llave", lambda: "k")
    monkeypatch.setattr(paperless, "id_de_etiqueta", lambda n: None)
    return paperless


@pytest.fixture
def puerta_abierta(monkeypatch, archivo_conectado):
    """La puerta del robot con token bueno y un Paperless que acepta todo."""
    from papeleo import entrada

    monkeypatch.setattr(entrada, "_tokens", lambda: ["bueno"])
    subidos = []
    monkeypatch.setattr(archivo_conectado, "subir",
                        lambda c, n, **k: subidos.append((c, n, k)) or "tarea-9")
    return subidos


def _entrar(client, nombre="remision.pdf", contenido=b"%PDF-1.4 hola", titulo=""):
    archivo = io.BytesIO(contenido)
    archivo.name = nombre
    datos = {"archivo": archivo}
    if titulo:
        datos["titulo"] = titulo
    return client.post("/papeleo/entra", datos, HTTP_X_PAPELEO_TOKEN="bueno")


# ── 1. El aviso al entrar ────────────────────────────────────────────────────


def test_apagado_no_avisa_a_nadie(client, usuario_factory, puerta_abierta,  # noqa: ARG001
                                  django_capture_on_commit_callbacks):
    """Nace apagado: veinte remisiones un lunes serían veinte avisos."""
    from interfono.models import InterfonoEntrega

    usuario_factory(rol="super_admin")
    with django_capture_on_commit_callbacks(execute=True):
        r = _entrar(client)
    assert r.status_code == 202
    assert not InterfonoEntrega.objects.filter(categoria="papeleo").exists()


def test_prendido_avisa_a_quien_puede_ver_el_papeleo_y_a_nadie_mas(
        client, usuario_factory, puerta_abierta, django_capture_on_commit_callbacks):  # noqa: ARG001
    """El destinatario se decide por PERMISO (§4 #20), no por rol."""
    from interfono.models import InterfonoEntrega

    _cfg(avisar_al_entrar=True)
    ve = usuario_factory(rol="miembro")
    _dar_permiso(ve, "papeleo", "ver")
    no_ve = usuario_factory(rol="miembro")

    with django_capture_on_commit_callbacks(execute=True):
        _entrar(client, nombre="contrato-optimist.pdf", titulo="Contrato Optimist")

    avisos = InterfonoEntrega.objects.filter(categoria="papeleo")
    assert avisos.filter(usuario=ve).exists()
    assert not avisos.filter(usuario=no_ve).exists()
    aviso = avisos.get(usuario=ve)
    assert "Contrato Optimist" in aviso.cuerpo
    assert aviso.url == "/papeleo/"


def test_el_aviso_no_sale_hasta_confirmar(client, usuario_factory, puerta_abierta,  # noqa: ARG001
                                          django_capture_on_commit_callbacks):
    """Va con `on_commit`: no se avisa de algo que se deshizo."""
    from interfono.models import InterfonoEntrega

    _cfg(avisar_al_entrar=True)
    ve = usuario_factory(rol="miembro")
    _dar_permiso(ve, "papeleo", "ver")
    with django_capture_on_commit_callbacks(execute=False) as pendientes:
        _entrar(client)
    assert pendientes, "el aviso debe esperar a que la transacción confirme"
    assert not InterfonoEntrega.objects.filter(categoria="papeleo").exists()


def test_si_paperless_rechaza_no_se_avisa(client, usuario_factory, monkeypatch,
                                          archivo_conectado,
                                          django_capture_on_commit_callbacks):
    """No se anuncia un documento que no entró."""
    from interfono.models import InterfonoEntrega
    from papeleo import entrada

    _cfg(avisar_al_entrar=True)
    ve = usuario_factory(rol="miembro")
    _dar_permiso(ve, "papeleo", "ver")
    monkeypatch.setattr(entrada, "_tokens", lambda: ["bueno"])
    monkeypatch.setattr(archivo_conectado, "subir", lambda c, n, **k: None)
    with django_capture_on_commit_callbacks(execute=True):
        r = _entrar(client)
    assert r.status_code == 502
    assert not InterfonoEntrega.objects.filter(categoria="papeleo").exists()


def test_la_categoria_se_ofrece_solo_a_quien_puede_ver_el_papeleo(usuario_factory):
    """Nadie ve un interruptor de un aviso que nunca le va a llegar."""
    from apps.perfil_notificaciones.views import _categorias_para

    ve = usuario_factory(rol="miembro")
    _dar_permiso(ve, "papeleo", "ver")
    no_ve = usuario_factory(rol="miembro")

    assert "papeleo" in {s for s, _n, _d in _categorias_para(ve)}
    assert "papeleo" not in {s for s, _n, _d in _categorias_para(no_ve)}


def test_la_categoria_del_aviso_y_la_del_perfil_son_la_misma():
    """Si se escribieran distinto, apagarla en el perfil no silenciaría nada."""
    from apps.perfil_notificaciones.views import CATEGORIAS

    from papeleo.avisos import CATEGORIA

    assert CATEGORIA in {c[0] for c in CATEGORIAS}


def test_usuarios_con_permiso_respeta_la_revocacion_individual(usuario_factory):
    """Una fila individual apagada revoca aunque el rol lo dé: `puede()` es la
    única definición, y el reparto del aviso pasa por ella."""
    from cuentas.models.permiso_usuario import PermisoUsuario
    from lib.permisos import invalidar_cache_permisos, usuarios_con_permiso

    jefe = usuario_factory(rol="super_admin")
    assert jefe in usuarios_con_permiso("papeleo", "ver")
    PermisoUsuario.objects.filter(usuario=jefe, modulo="papeleo",
                                  permiso="ver").update(activo=False)
    invalidar_cache_permisos()
    assert jefe not in usuarios_con_permiso("papeleo", "ver")


# ── 2. Word y Excel entran como PDF ──────────────────────────────────────────


def test_un_word_se_convierte_antes_de_archivarse_y_conserva_su_nombre(monkeypatch):
    from lib import a_pdf, gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)
    monkeypatch.setattr(gotenberg, "office_a_pdf", lambda c, n: b"%PDF convertido")
    p = a_pdf.preparar(b"PK\x03\x04 docx", "Contrato Optimist.docx")
    assert p.convertido is True
    assert p.nombre == "Contrato Optimist.pdf"
    assert p.contenido == b"%PDF convertido"
    assert not p.aviso


@pytest.mark.parametrize("nombre", ["a.doc", "a.docx", "a.xls", "a.xlsx", "a.odt", "a.ods"])
def test_las_extensiones_que_pidio_oscar_se_convierten(nombre):
    from lib import a_pdf

    assert a_pdf.es_convertible(nombre)


def test_un_pdf_no_se_toca():
    from lib import a_pdf

    p = a_pdf.preparar(b"%PDF-1.4", "remision.pdf")
    assert p.convertido is False
    assert p.nombre == "remision.pdf"


def test_convertidor_caido_se_queda_el_original_y_se_avisa(monkeypatch):
    """Perder el documento por un servicio caído sería peor que tenerlo sin
    convertir. Y no se llega a llamar a la conversión: esperaría un minuto."""
    from lib import a_pdf, gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: False)

    def _no_llamar(*a, **k):
        raise AssertionError("no se debe intentar convertir con el servicio caído")

    monkeypatch.setattr(gotenberg, "office_a_pdf", _no_llamar)
    p = a_pdf.preparar(b"PK docx", "Tabla.xlsx")
    assert p.convertido is False
    assert p.nombre == "Tabla.xlsx"
    assert p.contenido == b"PK docx"
    assert "no se pudo pasar a PDF" in p.aviso


def test_el_buzon_convierte_el_word_que_le_llega(client, monkeypatch, puerta_abierta):
    from lib import gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)
    monkeypatch.setattr(gotenberg, "office_a_pdf", lambda c, n: b"%PDF del word")
    r = _entrar(client, nombre="Garantia.docx", contenido=b"PK word")
    assert r.status_code == 202
    assert r.json()["convertido"] is True
    contenido, nombre, _k = puerta_abierta[0]
    assert nombre == "Garantia.pdf"
    assert contenido == b"%PDF del word"


def test_el_buzon_con_convertidor_caido_archiva_el_original_y_lo_dice(
        client, monkeypatch, puerta_abierta):
    from lib import gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: False)
    r = _entrar(client, nombre="Garantia.docx", contenido=b"PK word")
    assert r.status_code == 202
    assert r.json()["convertido"] is False
    assert "no se pudo pasar a PDF" in r.json()["aviso"]
    assert puerta_abierta[0][1] == "Garantia.docx"


def test_la_subida_desde_el_taller_tambien_convierte(client, jefe, monkeypatch,  # noqa: ARG001
                                                     archivo_conectado):
    from lib import gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)
    monkeypatch.setattr(gotenberg, "office_a_pdf", lambda c, n: b"%PDF del excel")
    visto = {}
    monkeypatch.setattr(archivo_conectado, "subir",
                        lambda c, n, **k: visto.update(c=c, n=n) or "t-1")
    archivo = io.BytesIO(b"PK excel")
    archivo.name = "Precios.xlsx"
    r = client.post("/papeleo/subir", {"archivo": archivo}, follow=True)
    assert visto == {"c": b"%PDF del excel", "n": "Precios.pdf"}
    assert "se convirtió a PDF" in r.content.decode()


# ── 3. El ligado automático tras el OCR ──────────────────────────────────────


@pytest.fixture
def optimist(db):
    from apps.la_cartera.models import Cliente

    return Cliente.objects.create(razon_social="Optimist Studio")


def _correr(*args):
    from django.core.management import call_command

    salida = io.StringIO()
    call_command("papeleo_ligar_pendientes", *args, stdout=salida)
    return salida.getvalue()


def test_apagado_no_repasa_nada(monkeypatch, archivo_conectado):
    """Con el ligado apagado ni se le pregunta al archivo: serían llamadas cada
    15 minutos para no guardar nada."""
    def _no_llamar(**k):
        raise AssertionError("no se debe consultar el archivo con el ligado apagado")

    monkeypatch.setattr(archivo_conectado, "recientes", _no_llamar)
    assert "apagado" in _correr()


def test_liga_lo_reciente_sin_dueno_y_deja_lo_dudoso(monkeypatch, archivo_conectado,
                                                     optimist):
    from apps.la_cartera.models import Cliente

    from papeleo.models import PapeleoLigado

    _cfg(ligar_automatico=True)
    Cliente.objects.create(razon_social="Optimist Marketing")
    Cliente.objects.create(razon_social="Heladeria Polar")
    monkeypatch.setattr(archivo_conectado, "recientes", lambda horas=48: [
        {"id": 1, "titulo": "Remisión", "texto": "Entregado a Heladeria Polar"},
        {"id": 2, "titulo": "Contrato",
         "texto": "Entre Optimist Studio y Optimist Marketing"},
        {"id": 3, "titulo": "scan_0042", "texto": ""},
    ])

    salida = _correr()
    assert PapeleoLigado.objects.filter(documento_id=1).exists()
    assert not PapeleoLigado.objects.filter(documento_id=2).exists()
    assert "varios" in salida, "debe decir POR QUÉ no ligó el dudoso"
    assert "todavía sin texto" in salida


def test_lo_que_ya_tiene_dueno_no_se_vuelve_a_tocar(monkeypatch, archivo_conectado,
                                                    optimist):
    from apps.los_proyectos.models import Proyecto

    from papeleo import ligado
    from papeleo.models import PapeleoLigado

    _cfg(ligar_automatico=True)
    pr = Proyecto.objects.create(nombre="Gorras", cliente=optimist)
    ligado.ligar(7, titulo="Contrato", proyecto=pr)
    monkeypatch.setattr(archivo_conectado, "recientes", lambda horas=48: [
        {"id": 7, "titulo": "Contrato", "texto": "Para Optimist Studio"},
    ])
    _correr()
    # Sigue ligado SÓLO al proyecto: no se le agregó también el cliente.
    assert PapeleoLigado.objects.filter(documento_id=7).count() == 1


def test_en_seco_no_guarda_nada(monkeypatch, archivo_conectado, optimist):  # noqa: ARG001
    from papeleo.models import PapeleoLigado

    _cfg(ligar_automatico=True)
    monkeypatch.setattr(archivo_conectado, "recientes", lambda horas=48: [
        {"id": 5, "titulo": "Remisión", "texto": "Entregado a Optimist Studio"},
    ])
    salida = _correr("--dry-run")
    assert "se ligaría a Optimist Studio" in salida
    assert not PapeleoLigado.objects.exists()


def test_el_archivo_caido_no_revienta_el_cron(monkeypatch, archivo_conectado):
    _cfg(ligar_automatico=True)
    monkeypatch.setattr(archivo_conectado, "recientes", lambda horas=48: None)
    assert "no contestó" in _correr()


def test_recientes_pide_lo_que_ENTRO_no_lo_que_dice_el_documento(monkeypatch):
    """Se filtra por `added` (cuándo llegó al archivo): un contrato de 2019
    escaneado hoy es de hoy para el ligado."""
    from lib import paperless

    pedidas = []

    def _falso(ruta, **k):
        pedidas.append(ruta)
        return {"results": [{"id": 4, "title": "Remisión", "content": "x" * 30000}]}

    monkeypatch.setattr(paperless, "_pedir", _falso)
    docs = paperless.recientes(horas=48)
    assert "added__gt=" in pedidas[0]
    assert "ordering=-added" in pedidas[0]
    # El texto viene completo hasta su tope (para encontrar un nombre en la
    # hoja dos), no recortado a lo que se le enseña a una persona.
    assert len(docs[0]["texto"]) == paperless.TOPE_TEXTO_LIGADO


def test_el_cron_esta_programado_cada_15_minutos():
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent.parent
    cron = (raiz / "infra/cron/el-despacho.cron").read_text()
    linea = next(ln for ln in cron.splitlines() if "papeleo_ligar_pendientes" in ln)
    assert linea.startswith("*/15 ")
    # Dentro del bloque que reinstala el deploy, no después.
    assert cron.index("papeleo_ligar_pendientes") < cron.index("# <<< El Despacho <<<")


# ── 4. Unir varios en un PDF ────────────────────────────────────────────────


@pytest.fixture
def union(monkeypatch, archivo_conectado):
    """Un archivo con tres documentos (dos PDF y una foto) y un Gotenberg que une."""
    from lib import gotenberg

    docs = {1: b"%PDF-1.4 uno", 2: b"%PDF-1.4 dos", 3: b"\xff\xd8\xff foto"}
    monkeypatch.setattr(archivo_conectado, "archivo",
                        lambda i, cara="preview": (docs[int(i)], "application/pdf")
                        if int(i) in docs else None)
    monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)
    unidos = []

    def _unir(pdfs):
        unidos.append(list(pdfs))
        return b"%PDF-1.4 UNIDO " + b"|".join(pdfs)

    monkeypatch.setattr(gotenberg, "unir", _unir)
    return unidos


def _clave_de(r):
    return r["Location"].rstrip("/").split("/")[-1]


def test_une_en_el_orden_en_que_se_marcaron(client, jefe, union):  # noqa: ARG001
    """El orden de la página (lo más reciente primero) casi nunca es el del
    expediente: manda el de los clics."""
    r = client.post("/papeleo/unir", {"doc": ["1", "2"], "orden": "2,1",
                                      "titulo_1": "Uno", "titulo_2": "Dos"})
    assert r.status_code == 302
    assert union[0] == [b"%PDF-1.4 dos", b"%PDF-1.4 uno"]
    pagina = client.get(r["Location"])
    assert pagina.status_code == 200
    cuerpo = pagina.content.decode()
    assert cuerpo.index("Dos") < cuerpo.index("Uno")


def test_lo_que_no_es_pdf_se_salta_y_se_dice(client, jefe, union):  # noqa: ARG001
    r = client.post("/papeleo/unir", {"doc": ["1", "2", "3"], "titulo_3": "La foto"})
    assert r.status_code == 302
    assert len(union[0]) == 2
    cuerpo = client.get(r["Location"]).content.decode()
    assert "La foto" in cuerpo
    assert "no es PDF" in cuerpo


def test_uno_solo_no_se_une(client, jefe, union):  # noqa: ARG001
    r = client.post("/papeleo/unir", {"doc": ["1"]}, follow=True)
    assert not union
    assert "al menos dos" in r.content.decode()


def test_el_convertidor_caido_lo_dice_y_no_intenta(client, jefe, monkeypatch, union):  # noqa: ARG001
    from lib import gotenberg

    monkeypatch.setattr(gotenberg, "disponible", lambda **k: False)
    r = client.post("/papeleo/unir", {"doc": ["1", "2"]}, follow=True)
    assert not union
    assert "no está contestando" in r.content.decode()


def test_el_resultado_se_baja_como_pdf(client, jefe, union):  # noqa: ARG001
    r = client.post("/papeleo/unir", {"doc": ["1", "2"]})
    clave = _clave_de(r)
    bajada = client.get(f"/papeleo/unido/{clave}/bajar")
    assert bajada.status_code == 200
    assert bajada["Content-Type"] == "application/pdf"
    assert bajada.content.startswith(b"%PDF-1.4 UNIDO")
    assert "attachment" in bajada["Content-Disposition"]


def test_otra_persona_no_puede_bajar_lo_que_uni(client, jefe, union, usuario_factory):  # noqa: ARG001
    """El candado: sin él, quien pueda ver papeleo pediría cualquier archivo del
    almacén adivinando su llave."""
    from django.test import Client

    clave = _clave_de(client.post("/papeleo/unir", {"doc": ["1", "2"]}))
    otra = usuario_factory(rol="super_admin")
    ajena = Client()
    ajena.force_login(otra)
    assert ajena.get(f"/papeleo/unido/{clave}/bajar").status_code == 404


def test_una_llave_del_almacen_ajena_no_se_sirve(client, jefe):  # noqa: ARG001
    from lib import almacen

    ajena = almacen.guardar_bytes(b"%PDF contrato ajeno", nombre="x.pdf",
                                  mime="application/pdf")["id"]
    assert client.get(f"/papeleo/unido/{ajena}/bajar").status_code == 404
    assert client.get("/papeleo/unido/no-es-hex/bajar").status_code == 404


def test_sin_permiso_de_ver_no_se_une(client, usuario_factory, union):
    client.force_login(usuario_factory(rol="miembro"))
    assert client.post("/papeleo/unir", {"doc": ["1", "2"]}).status_code == 403
    assert not union


def test_se_archiva_una_sola_vez(client, jefe, union, monkeypatch, archivo_conectado):  # noqa: ARG001
    subidos = []
    monkeypatch.setattr(archivo_conectado, "subir",
                        lambda c, n, **k: subidos.append((c, n, k)) or "t-1")
    clave = _clave_de(client.post("/papeleo/unir", {"doc": ["1", "2"]}))
    client.post(f"/papeleo/unido/{clave}/archivar", {"titulo": "Expediente Optimist"})
    client.post(f"/papeleo/unido/{clave}/archivar", {"titulo": "Expediente Optimist"})
    assert len(subidos) == 1, "dos clics no deben dejar dos copias en el archivo"
    assert subidos[0][2]["titulo"] == "Expediente Optimist"
    assert subidos[0][0].startswith(b"%PDF-1.4 UNIDO")


def test_archivar_pide_permiso_de_subir(client, usuario_factory, union):  # noqa: ARG001
    u = usuario_factory(rol="miembro")
    _dar_permiso(u, "papeleo", "ver")
    client.force_login(u)
    clave = _clave_de(client.post("/papeleo/unir", {"doc": ["1", "2"]}))
    pagina = client.get(f"/papeleo/unido/{clave}/").content.decode()
    assert "Mandar al archivo" not in pagina
    assert client.post(f"/papeleo/unido/{clave}/archivar").status_code == 403


def test_la_pantalla_ofrece_marcar_para_unir(client, jefe, archivo_conectado, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr(archivo_conectado, "listar", lambda n=20: [
        {"id": 1, "titulo": "Uno", "creado": "2026-09-01", "etiquetas": [], "paginas": 1},
        {"id": 2, "titulo": "Dos", "creado": "2026-09-02", "etiquetas": [], "paginas": 1},
    ])
    monkeypatch.setattr(archivo_conectado, "cuantos", lambda: 2)
    cuerpo = client.get("/papeleo/").content.decode()
    assert 'form="papeleo-unir"' in cuerpo
    assert "Unir en un PDF" in cuerpo
    assert 'action="/papeleo/unir"' in cuerpo
