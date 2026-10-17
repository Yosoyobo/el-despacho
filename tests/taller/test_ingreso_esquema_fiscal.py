"""Oscar 2026-10-14: «Nuevo ingreso» sólo calculaba con IVA 16%; la operación real
es RESICO con retenciones. El modal ofrece IVA 16% / RESICO / sin IVA, el cálculo
en vivo y el guardado salen de la MISMA función, y el esquema nace del proyecto.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

D = Decimal


def _post(client, proyecto, **extra):
    datos = {"fecha": date.today().isoformat(), "metodo": "transferencia",
             "descripcion": "Cobro", "proyecto": str(proyecto.pk)}
    datos.update(extra)
    return client.post("/tesoreria/ingresos/nuevo/", datos, HTTP_HX_REQUEST="true")


@pytest.fixture
def admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    return u


def test_desglose_resico_invierte_el_calculo_de_honorarios():
    from apps.tesoreria.forms import desglosar_ingreso
    from lib.fiscal import desglose_honorarios
    # 16,653.33 es el total real de una base de 16,000 (docstring de lib/fiscal)
    d = desglosar_ingreso(D("16653.33"), "honorarios")
    assert d["subtotal"] == D("16000.00")
    assert d["iva"] == D("2560.00") and d["ret_isr"] == D("200.00") and d["ret_iva"] == D("1706.67")
    # el total siempre cuadra EXACTO con lo capturado (8,326.67 = mitad de 16,653.33)
    d2 = desglosar_ingreso(D("8326.67"), "honorarios")
    assert d2["monto"] == D("8326.67")
    assert desglose_honorarios(d2["subtotal"])["total"] == D("8326.67")


def test_desglose_iva_y_exento_siguen_igual():
    from apps.tesoreria.forms import desglosar_ingreso
    d = desglosar_ingreso(D("8326.67"), "iva")
    assert (d["subtotal"], d["iva"]) == (D("7178.16"), D("1148.51"))  # el ticket
    assert d["retenciones"] == D("0.00")
    e = desglosar_ingreso(D("8326.67"), "exento")
    assert (e["subtotal"], e["iva"]) == (D("8326.67"), D("0.00"))


def test_guardar_resico_persiste_base_total_y_esquema(client, admin, proyecto_factory):
    from apps.tesoreria.models import Ingreso
    p = proyecto_factory()
    resp = _post(client, p, subtotal="16653.33", regimen_fiscal="honorarios")
    assert resp.status_code == 204
    i = Ingreso.objects.get()
    assert (i.monto, i.subtotal) == (D("16653.33"), D("16000.00"))
    assert i.regimen_fiscal == "honorarios" and i.incluye_iva is True
    assert i.regimen_efectivo == "honorarios"


def test_guardar_exento_y_legado_sin_esquema(client, admin, proyecto_factory):
    from apps.tesoreria.models import Ingreso
    p = proyecto_factory()
    _post(client, p, subtotal="500.00", regimen_fiscal="exento")
    # formulario viejo: sólo el checkbox de IVA, sin `regimen_fiscal`
    _post(client, p, subtotal="1160.00", incluye_iva="on")
    _post(client, p, subtotal="300.00")
    ex, viejo_iva, viejo_sin = (Ingreso.objects.get(monto=D(m)) for m in ("500.00", "1160.00", "300.00"))
    assert (ex.regimen_fiscal, ex.incluye_iva, ex.subtotal) == ("exento", False, D("500.00"))
    assert (viejo_iva.regimen_fiscal, viejo_iva.incluye_iva, viejo_iva.subtotal) == ("iva", True, D("1000.00"))
    assert (viejo_sin.regimen_fiscal, viejo_sin.incluye_iva) == ("exento", False)


def test_api_en_vivo_coincide_con_lo_que_se_guarda(client, admin, proyecto_factory):
    from apps.tesoreria.models import Ingreso
    p = proyecto_factory()
    for total, reg in (("8326.67", "honorarios"), ("8326.67", "iva"), ("8326.67", "exento"),
                       ("16653.33", "honorarios")):
        vivo = client.get("/tesoreria/api/desglose-ingreso/", {"total": total, "regimen": reg}).json()
        Ingreso.objects.all().delete()
        _post(client, p, subtotal=total, regimen_fiscal=reg)
        guardado = Ingreso.objects.get()
        assert D(vivo["subtotal"]) == guardado.subtotal, reg
        assert D(vivo["monto"]) == guardado.monto, reg


def test_api_valida_esquema_y_permiso(client, usuario_factory):
    client.force_login(usuario_factory(rol="super_admin"))
    assert client.get("/tesoreria/api/desglose-ingreso/", {"total": "1", "regimen": "x"}).status_code == 400
    assert client.get("/tesoreria/api/desglose-ingreso/", {"total": "abc", "regimen": "iva"}).status_code == 200
    client.logout()
    assert client.get("/tesoreria/api/desglose-ingreso/", {"total": "1", "regimen": "iva"}).status_code in (302, 403)


def test_esquema_nace_del_proyecto(client, admin, proyecto_factory):
    resico = proyecto_factory(regimen_fiscal="honorarios")
    con_iva = proyecto_factory(regimen_fiscal="iva")
    exento = proyecto_factory(regimen_fiscal="iva", iva_exento=True)
    for p, esperado in ((resico, "honorarios"), (con_iva, "iva"), (exento, "exento")):
        html = client.get(f"/tesoreria/ingresos/nuevo/?proyecto={p.pk}&desde=proyecto",
                          HTTP_HX_REQUEST="true").content.decode()
        marcado = [ln for ln in html.splitlines()
                   if 'name="regimen_fiscal"' in ln and "checked" in ln]
        assert len(marcado) == 1 and f'value="{esperado}"' in marcado[0], (esperado, marcado)
        assert client.get(f"/tesoreria/api/proyecto/{p.pk}/datos/").json()["regimen_fiscal"] == esperado


def test_editar_conserva_el_esquema(client, admin, proyecto_factory):
    from apps.tesoreria.models import Ingreso
    p = proyecto_factory()
    _post(client, p, subtotal="16653.33", regimen_fiscal="honorarios")
    i = Ingreso.objects.get()
    html = client.get(f"/tesoreria/ingresos/{i.pk}/editar/").content.decode()
    marcado = [ln for ln in html.splitlines() if 'name="regimen_fiscal"' in ln and "checked" in ln]
    assert len(marcado) == 1 and 'value="honorarios"' in marcado[0]
