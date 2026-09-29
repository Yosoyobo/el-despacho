"""Los documentos del cliente vistos desde El Taller, y El Chalán leyendo la CSF.

- La ficha: el recuadro, el permiso `recepcion.documentos`, revisar/rechazar,
  subir en nombre del cliente, ver el archivo.
- La CSF: El Chalán sólo propone, lo inventado se descarta contra el texto del
  PDF, la vigencia se mide con los días de La Gerencia, y aplicar a la ficha
  pide además `cartera.editar`.
- Las migraciones: revivir la última llave y sembrar el permiso.
- La Gerencia, El Chalán y el MCP.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


def pdf_con_texto(lineas: list[str]) -> bytes:
    """Un PDF mínimo con texto de verdad (pypdf lo lee), armado a mano."""
    contenido = "BT /F1 10 Tf 40 800 Td 12 TL " + " ".join(
        "(" + ln.replace("(", "").replace(")", "") + ") '" for ln in lineas) + " ET"
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(contenido.encode('latin-1'))} >>\nstream\n{contenido}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    salida = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objetos, start=1):
        offsets.append(len(salida))
        salida += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for o in offsets:
        salida += f"{o:010d} 00000 n \n".encode()
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return salida


HOY = dt.date.today()
EMISION = HOY - dt.timedelta(days=10)
MESES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
         "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
TEXTO_CSF = [
    "CONSTANCIA DE SITUACION FISCAL",
    f"CUAUHTEMOC , CIUDAD DE MEXICO A {EMISION.day:02d} DE {MESES[EMISION.month - 1]} DE {EMISION.year}",
    "RFC: HLN190101AB1",
    "Denominacion/Razon Social: HELADERIA LA NIEVE",
    "Codigo Postal:06600",
    "Regimen General de Ley Personas Morales",
]


def _respuesta(**cambios) -> str:
    base = {"es_csf": True, "rfc": "HLN190101AB1", "razon_social": "HELADERIA LA NIEVE",
            "regimen_fiscal": "601 · General de Ley Personas Morales", "codigo_postal": "06600",
            "fecha_emision": EMISION.isoformat(), "confianza": 0.93}
    base.update(cambios)
    return json.dumps(base)


@pytest.fixture
def cliente(cliente_factory):
    return cliente_factory(razon_social="HELADERIA LA NIEVE")


@pytest.fixture
def admin(usuario_factory):
    return usuario_factory(rol="super_admin")


def _subir_csf(cliente, contenido, monkeypatch, respuesta: str | Exception, usuario=None):
    """Sube una CSF y deja que El Chalán (de mentiras) la lea al momento."""
    from django.db import transaction

    from portal import csf, documentos

    monkeypatch.setattr(transaction, "on_commit", lambda fn, using=None, robust=False: fn())
    monkeypatch.setattr("lib.tareas_fondo.ejecutar_en_fondo", lambda fn, *a, **k: fn(*a, **k))

    def _llamar(prompt, imagenes=None):
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(csf, "_llamar", _llamar)
    d = documentos.subir(cliente, "csf", SimpleUploadedFile("csf.pdf", contenido, "application/pdf"),
                         usuario=usuario)
    d.refresh_from_db()
    return d


# ── La CSF con El Chalán ────────────────────────────────────────────────────


def test_el_pdf_de_prueba_trae_texto():
    from portal.csf import texto_de_pdf

    assert "HLN190101AB1" in texto_de_pdf(pdf_con_texto(TEXTO_CSF))


def test_el_chalan_lee_la_csf_y_la_marca_vigente(cliente, monkeypatch):
    d = _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch, _respuesta())
    assert d.ia_estado == "lista"
    assert d.csf == {"rfc": "HLN190101AB1", "razon_social": "HELADERIA LA NIEVE",
                     "regimen_fiscal": "601 · General de Ley Personas Morales",
                     "codigo_postal": "06600", "fecha_emision": EMISION.isoformat()}
    assert d.vigencia["vigente"] is True and d.vigencia["dias"] == 10 and d.vigencia["limite"] == 30
    # Sólo propone: la ficha no cambió.
    cliente.refresh_from_db()
    assert cliente.rfc == "" and not cliente.razones_sociales.exists()


def test_lo_que_no_esta_en_el_pdf_se_descarta(cliente, monkeypatch):
    """El candado contra la IA que inventa: RFC, CP o fecha que no aparecen."""
    d = _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch,
                   _respuesta(rfc="XXX990101XX9", codigo_postal="11000", fecha_emision="2026-01-02"))
    assert "rfc" not in d.csf and "codigo_postal" not in d.csf and "fecha_emision" not in d.csf
    assert len(d.ia["descartados"]) == 3
    assert d.vigencia["vigente"] is None


def test_un_rfc_sin_la_forma_del_sat_se_descarta():
    from portal.csf import limpiar

    datos, fuera = limpiar({"rfc": "NO-ES-RFC", "codigo_postal": "123"}, "")
    assert datos == {} and len(fuera) == 2


def test_la_vigencia_se_mide_con_los_dias_de_la_gerencia(cliente, monkeypatch):
    from portal.csf import revisar_vigencia
    from portal.models import ConfiguracionPortal

    cfg = ConfiguracionPortal.obtener()
    cfg.csf_vigencia_dias = 7
    cfg.save()
    d = _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch, _respuesta())
    assert d.vigencia["vigente"] is False and d.vigencia["limite"] == 7
    assert "máximo 7" in d.vigencia["motivo"]
    futura = revisar_vigencia((HOY + dt.timedelta(days=3)).isoformat(), 30)
    assert futura["vigente"] is None and "posterior" in futura["motivo"]


def test_sin_chalan_o_pdf_escaneado_queda_para_una_persona(cliente, monkeypatch):
    d = _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch, RuntimeError("sin llaves"))
    assert d.ia_estado == "sin_leer" and "no está disponible" in d.ia["motivo"]
    escaneado = _subir_csf(cliente, b"%PDF-1.4\n%%EOF\n", monkeypatch, _respuesta())
    assert escaneado.ia_estado == "sin_leer"


def test_si_no_es_una_csf_lo_dice(cliente, monkeypatch):
    d = _subir_csf(cliente, pdf_con_texto(["FACTURA 123"]), monkeypatch, json.dumps({"es_csf": False}))
    assert d.ia["es_csf"] is False and d.csf == {}


def test_una_foto_de_la_csf_va_con_vision(cliente, monkeypatch):
    from django.db import transaction

    from portal import csf, documentos

    monkeypatch.setattr(transaction, "on_commit", lambda fn, using=None, robust=False: fn())
    monkeypatch.setattr("lib.tareas_fondo.ejecutar_en_fondo", lambda fn, *a, **k: fn(*a, **k))
    vistas = []
    monkeypatch.setattr(csf, "_llamar", lambda prompt, imagenes=None: vistas.append(imagenes) or _respuesta())
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    documentos.subir(cliente, "csf", SimpleUploadedFile("csf.png", png, "image/png"))
    assert vistas and vistas[0][0]["media_type"] == "image/png"


def test_aplicar_crea_la_razon_social_y_la_espeja_al_cliente(cliente, admin, monkeypatch):
    from portal import csf

    d = _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch, _respuesta())
    cambios = {c["campo"] for c in csf.cambios_propuestos(d)}
    assert cambios == {"rfc", "razon_social", "regimen_fiscal", "codigo_postal"}
    aviso = csf.aplicar(d, admin)
    assert "se agregó" in aviso
    r = cliente.razones_sociales.get()
    assert (r.rfc, r.codigo_postal, r.principal) == ("HLN190101AB1", "06600", True)
    assert r.regimen_fiscal.startswith("601")
    cliente.refresh_from_db()
    assert cliente.rfc == "HLN190101AB1" and cliente.razon_social_fiscal == "HELADERIA LA NIEVE"
    d.refresh_from_db()
    assert d.aplicado_por == admin and csf.cambios_propuestos(d) == []


def test_aplicar_actualiza_la_razon_social_del_mismo_rfc(cliente, admin, monkeypatch):
    from apps.la_cartera.models import ClienteRazonSocial

    from portal import csf

    ClienteRazonSocial.objects.create(cliente=cliente, razon_social="OTRA", rfc="OTR010101AA1", principal=True)
    vieja = ClienteRazonSocial.objects.create(cliente=cliente, razon_social="NIEVE VIEJA", rfc="HLN190101AB1")
    d = _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch, _respuesta())
    csf.aplicar(d, admin)
    vieja.refresh_from_db()
    assert vieja.razon_social == "HELADERIA LA NIEVE" and vieja.codigo_postal == "06600"
    assert cliente.razones_sociales.count() == 2 and not vieja.principal


# ── La ficha del cliente en El Taller ───────────────────────────────────────


def test_la_ficha_muestra_los_documentos_y_lo_que_leyo_el_chalan(client, cliente, admin, monkeypatch):
    _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch, _respuesta())
    client.force_login(admin)
    html = client.get(f"/cartera/{cliente.pk}/").content.decode()
    assert 'id="documentos-cliente"' in html
    assert "HLN190101AB1" in html and "Vigente" in html and "Aplicar a la ficha" in html
    assert "1 por revisar" in html


def test_sin_permiso_no_hay_recuadro_ni_puertas(client, cliente, usuario_factory, monkeypatch):
    from cuentas.models import PermisoUsuario

    d = _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch, _respuesta())
    u = usuario_factory(rol="contador")
    PermisoUsuario.objects.filter(usuario=u, modulo="recepcion").delete()
    client.force_login(u)
    assert 'id="documentos-cliente"' not in client.get(f"/cartera/{cliente.pk}/").content.decode()
    assert client.get(f"/recepcion/documento/{d.pk}/archivo/").status_code == 403
    assert client.post(f"/recepcion/documento/{d.pk}/revisar/", {"aprobar": "1"}).status_code == 403
    assert client.post(f"/recepcion/documento/{d.pk}/aplicar-csf/").status_code == 403


def test_sin_sesion_no_se_ve_el_archivo(client, cliente, monkeypatch):
    d = _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch, _respuesta())
    r = client.get(f"/recepcion/documento/{d.pk}/archivo/")
    assert r.status_code == 302 and "next=/recepcion/documento/" in r["Location"]


def test_ver_el_archivo(client, cliente, admin, monkeypatch):
    contenido = pdf_con_texto(TEXTO_CSF)
    d = _subir_csf(cliente, contenido, monkeypatch, _respuesta())
    client.force_login(admin)
    r = client.get(f"/recepcion/documento/{d.pk}/archivo/")
    assert r.status_code == 200 and r.content == contenido
    assert r["Content-Type"] == "application/pdf" and r["X-Content-Type-Options"] == "nosniff"
    assert r["Content-Disposition"].startswith("inline")
    assert client.get(f"/recepcion/documento/{d.pk}/archivo/?descargar=1")["Content-Disposition"].startswith("attachment")


def test_revisar_y_rechazar_con_motivo(client, cliente, admin, monkeypatch):
    d = _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch, _respuesta())
    client.force_login(admin)
    r = client.post(f"/recepcion/documento/{d.pk}/revisar/", {"aprobar": "0", "motivo": ""})
    assert "Escribe por qué".encode() in r.content
    d.refresh_from_db()
    assert d.estado == "recibido"
    client.post(f"/recepcion/documento/{d.pk}/revisar/", {"aprobar": "0", "motivo": "Está borrosa"})
    d.refresh_from_db()
    assert d.estado == "rechazado" and d.motivo_rechazo == "Está borrosa" and d.revisado_por == admin
    client.post(f"/recepcion/documento/{d.pk}/revisar/", {"aprobar": "1"})
    d.refresh_from_db()
    assert d.estado == "aprobado" and d.motivo_rechazo == ""


def test_aplicar_a_la_ficha_pide_tambien_editar_la_cartera(client, cliente, usuario_factory, monkeypatch):
    from cuentas.models import PermisoUsuario

    d = _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch, _respuesta())
    u = usuario_factory(rol="miembro")
    PermisoUsuario.objects.create(usuario=u, modulo="recepcion", permiso="documentos", activo=True)
    PermisoUsuario.objects.create(usuario=u, modulo="cartera", permiso="ver", activo=True)
    client.force_login(u)
    r = client.post(f"/recepcion/documento/{d.pk}/aplicar-csf/")
    assert b"No tienes permiso para editar" in r.content
    assert not cliente.razones_sociales.exists()
    PermisoUsuario.objects.create(usuario=u, modulo="cartera", permiso="editar", activo=True)
    from lib.permisos import invalidar_cache_permisos

    invalidar_cache_permisos(u)
    client.post(f"/recepcion/documento/{d.pk}/aplicar-csf/")
    assert cliente.razones_sociales.get().rfc == "HLN190101AB1"


def test_el_equipo_sube_en_nombre_del_cliente(client, cliente, admin, monkeypatch):
    from portal.models import DocumentoCliente

    monkeypatch.setattr("portal.documentos._leer_csf_despues", lambda doc_id: None)
    client.force_login(admin)
    r = client.post(f"/recepcion/cliente/{cliente.pk}/documentos/subir/",
                    {"tipo": "contrato", "archivo": SimpleUploadedFile("c.pdf", pdf_con_texto(["X"]), "application/pdf")})
    assert r.status_code == 200 and "se guardó".encode() in r.content
    d = DocumentoCliente.objects.get()
    assert d.subido_por == admin and d.acceso is None and d.tipo == "contrato"


# ── La llave desde la ficha: copiar y cambiar ───────────────────────────────


def test_copiar_y_cambiar_el_enlace_desde_la_ficha(client, cliente_factory, admin, monkeypatch):
    from apps.la_cartera.models import ClienteContacto

    from lib import cartero
    from portal import servicios
    from portal.models import EnlaceAcceso, EventoPortal

    monkeypatch.setattr(cartero, "enviar", lambda **kw: cartero.ResultadoCorreo(ok=True, proveedor="p"))
    c = cliente_factory(razon_social="OPTIMIST")
    ClienteContacto.objects.create(cliente=c, nombre="Ana", email="ana@op.mx")
    acceso = servicios.invitar(c, "ana@op.mx", admin).acceso
    token = servicios.llave_de(acceso)
    client.force_login(admin)
    r = client.post(f"/recepcion/acceso/{acceso.pk}/copiar-enlace/")
    assert token.encode() in r.content and b"Copiar" in r.content
    assert EventoPortal.objects.filter(tipo="copiado").exists()
    r = client.post(f"/recepcion/acceso/{acceso.pk}/cambiar-enlace/")
    assert b"ya no abre" in r.content
    assert servicios.llave_de(acceso) != token
    assert EnlaceAcceso.objects.filter(acceso=acceso, anulado_en__isnull=True).count() == 1


# ── Migraciones ─────────────────────────────────────────────────────────────


def test_la_migracion_revive_la_ultima_llave_de_cada_quien(cliente_factory):
    import importlib

    from django.apps import apps as django_apps
    from django.utils import timezone

    from portal.models import AccesoCliente, EnlaceAcceso

    mig = importlib.import_module("portal.migrations.0005_revivir_ultima_llave")
    c = cliente_factory()
    vivo = AccesoCliente.objects.create(cliente=c, email="a@x.mx")
    revocado = AccesoCliente.objects.create(cliente=c, email="b@x.mx", activo=False)
    ahora = timezone.now()
    vieja = EnlaceAcceso.objects.create(acceso=vivo, token_hash="1" * 64, creado_en=ahora - dt.timedelta(days=5),
                                        expira_en=ahora - dt.timedelta(days=4), usado_en=ahora)
    ultima = EnlaceAcceso.objects.create(acceso=vivo, token_hash="2" * 64, creado_en=ahora - dt.timedelta(days=1),
                                         expira_en=ahora - dt.timedelta(hours=1), usado_en=ahora)
    del_revocado = EnlaceAcceso.objects.create(acceso=revocado, token_hash="3" * 64,
                                               expira_en=ahora + dt.timedelta(hours=1))
    mig.revivir(django_apps, None)
    for e in (vieja, ultima, del_revocado):
        e.refresh_from_db()
    assert ultima.vigente and ultima.expira_en is None
    assert not vieja.vigente and not del_revocado.vigente


def test_la_siembra_da_documentos_a_quien_ve_el_portal(usuario_factory):
    import importlib

    from django.apps import apps as django_apps

    from cuentas.models import PermisoUsuario

    mig = importlib.import_module("portal.migrations.0006_seed_permiso_documentos")
    sa = usuario_factory(rol="super_admin")
    ve = usuario_factory(rol="miembro")
    PermisoUsuario.objects.update_or_create(usuario=ve, modulo="recepcion", permiso="ver", defaults={"activo": True})
    nada = usuario_factory(rol="disenador")
    PermisoUsuario.objects.filter(modulo="recepcion", permiso="documentos").delete()
    PermisoUsuario.objects.filter(usuario=nada, modulo="recepcion").delete()
    mig.sembrar(django_apps, None)

    def tiene(u):
        return PermisoUsuario.objects.filter(usuario=u, modulo="recepcion", permiso="documentos",
                                             activo=True).exists()

    assert tiene(sa) and tiene(ve) and not tiene(nada)


# ── La Gerencia, El Chalán y el MCP ─────────────────────────────────────────


def test_el_chalan_consulta_los_documentos_con_permiso(cliente, admin, usuario_factory, monkeypatch):
    import capacidades.lecturas  # noqa: F401 — registra
    from capacidades.gating import gate_ok
    from capacidades.registro import CAPACIDADES
    from cuentas.models import PermisoUsuario

    _subir_csf(cliente, pdf_con_texto(TEXTO_CSF), monkeypatch, _respuesta())
    cap = CAPACIDADES["documentos_del_cliente"]
    assert gate_ok(cap.gating, admin)
    sin = usuario_factory(rol="miembro")
    PermisoUsuario.objects.create(usuario=sin, modulo="recepcion", permiso="ver", activo=True)
    assert not gate_ok(cap.gating, sin)
    datos = cap.fn({"cliente": "HELADERIA LA NIEVE"}, admin)
    assert datos["documentos"][0]["lectura_chalan"]["rfc"] == "HLN190101AB1"
    todos = cap.fn({}, admin)
    assert todos["por_revisar"][0]["cliente"] == "HELADERIA LA NIEVE"


def test_documentos_del_cliente_esta_en_el_mcp_y_en_el_catalogo():
    from lib.dictado_catalogo import CONSULTAS_CHAT
    from mcp_despacho import herramientas, servidor

    assert hasattr(herramientas, "documentos_del_cliente") and hasattr(servidor, "documentos_del_cliente")
    assert any(c["nombre"] == "documentos_del_cliente" for c in CONSULTAS_CHAT)


def test_la_estacion_de_la_csf_esta_sembrada():
    from chalanes.estaciones import ESTACIONES_DICT
    from chalanes.models import CuadroChalanes

    assert ESTACIONES_DICT["documento_cliente"]["requiere_vision"] is True
    assert CuadroChalanes.objects.filter(estacion="documento_cliente").exists()
