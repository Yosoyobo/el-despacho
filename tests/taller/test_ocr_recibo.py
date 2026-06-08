"""OCR de recibos (S-Chalán-Scope-OCR, fase C3).

Mockea `lib.analistas.analizar` con respuestas canned (texto JSON) para
ejercitar el extractor y la pantalla de escaneo sin pegarle a un LLM con
visión real.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def _res(texto):
    return SimpleNamespace(
        texto=texto, provider="gemini", modelo="gemini-2.5-flash",
        prompt_tokens=10, completion_tokens=5, costo_usd=0.0001, latencia_ms=120,
    )


def _fake(texto):
    def fake(estacion, prompt, **kw):
        assert estacion == "ocr_recibo"
        assert kw.get("imagenes")  # se pasan imágenes
        return _res(texto)
    return fake


# ── Extractor ─────────────────────────────────────────────────────────────────

def test_extraer_recibo_happy(monkeypatch, usuario_factory):
    import lib.analistas as la
    from apps.tesoreria import ocr
    from apps.tesoreria.models import EgresoOcrLog
    u = usuario_factory(rol="super_admin")
    monkeypatch.setattr(la, "analizar", _fake(
        '{"total": 1160, "subtotal": 1000, "iva": 160, "fecha": "2026-06-01", '
        '"proveedor": "Office Depot", "concepto": "Papelería", "moneda": "MXN"}'
    ))
    out = ocr.extraer_recibo(contenido=b"\x89PNG...", media_type="image/png",
                             nombre_original="ticket.png", usuario=u)
    assert out["ok"]
    d = out["datos"]
    assert d["subtotal_sugerido"] == 1000.0 and d["incluye_iva"] is True
    assert d["fecha"] == "2026-06-01" and d["proveedor"] == "Office Depot"
    log = EgresoOcrLog.objects.get(pk=out["log_id"])
    assert log.chalan_usado == "gemini" and log.raw_extraccion["total"] == 1160


def test_extraer_recibo_solo_total_sin_iva(monkeypatch, usuario_factory):
    import lib.analistas as la
    from apps.tesoreria import ocr
    monkeypatch.setattr(la, "analizar", _fake('{"total": 450, "fecha": null, "proveedor": "Uber"}'))
    out = ocr.extraer_recibo(contenido=b"x", media_type="image/jpeg", usuario=usuario_factory())
    assert out["ok"]
    assert out["datos"]["subtotal_sugerido"] == 450.0
    assert out["datos"]["incluye_iva"] is False


def test_extraer_recibo_json_malo(monkeypatch, usuario_factory):
    import lib.analistas as la
    from apps.tesoreria import ocr
    from apps.tesoreria.models import EgresoOcrLog
    monkeypatch.setattr(la, "analizar", _fake("perdón, no puedo leer la imagen"))
    out = ocr.extraer_recibo(contenido=b"x", media_type="image/jpeg", usuario=usuario_factory())
    assert out["ok"] is False
    # registra el log igual (trazabilidad), aunque sin extracción
    assert EgresoOcrLog.objects.filter(pk=out["log_id"]).exists()


def test_extraer_recibo_llm_caido(monkeypatch, usuario_factory):
    import lib.analistas as la
    from apps.tesoreria import ocr

    def boom(*a, **k):
        raise RuntimeError("cadena agotada")
    monkeypatch.setattr(la, "analizar", boom)
    out = ocr.extraer_recibo(contenido=b"x", media_type="image/jpeg", usuario=usuario_factory())
    assert out["ok"] is False
    assert "recibo" in out["error"].lower()


# ── Pantalla ──────────────────────────────────────────────────────────────────

def test_escanear_requiere_finanzas(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/tesoreria/egresos/escanear/")
    assert resp.status_code == 403


def test_escanear_get_muestra_form(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/tesoreria/egresos/escanear/")
    assert resp.status_code == 200
    assert b"Escanear recibo" in resp.content


def test_escanear_post_prellena_form(client, monkeypatch, usuario_factory):
    import lib.analistas as la
    from django.core.files.uploadedfile import SimpleUploadedFile
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    monkeypatch.setattr(la, "analizar", _fake(
        '{"total": 232, "subtotal": 200, "iva": 32, "fecha": "2026-06-05", '
        '"proveedor": "Cafetería", "concepto": "Café equipo", "moneda": "MXN"}'
    ))
    archivo = SimpleUploadedFile("recibo.jpg", b"\xff\xd8\xff fake jpeg", content_type="image/jpeg")
    resp = client.post("/tesoreria/egresos/escanear/", {"comprobante": archivo})
    assert resp.status_code == 200
    assert b"Datos le" in resp.content  # banner "Datos leídos del recibo"
    assert b'name="ocr_log_id"' in resp.content


def test_egreso_nuevo_vincula_log_y_correcciones(client, monkeypatch, usuario_factory):
    from datetime import date

    from apps.tesoreria.models import CentroDeCosto, EgresoOcrLog
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    # Simula un log OCR previo con un total que el usuario corregirá.
    log = EgresoOcrLog.objects.create(
        raw_extraccion={"total": 999, "fecha": "2026-06-01"}, chalan_usado="gemini",
        creado_por=u,
    )
    centro = CentroDeCosto.objects.filter(activo=True).first()
    resp = client.post("/tesoreria/egresos/nuevo/", {
        "fecha": date.today().isoformat(), "subtotal": "500.00", "moneda": "MXN",
        "descripcion": "Gasto corregido", "centro_de_costo": centro.pk,
        "metodo": "transferencia", "estado_pago": "pagado", "ocr_log_id": log.pk,
    })
    assert resp.status_code in (302, 200)
    log.refresh_from_db()
    assert log.egreso is not None
    assert log.fue_corregido is True
    assert "monto" in log.correcciones
