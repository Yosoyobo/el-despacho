"""La Gerencia → Portal de clientes: la papelería que se pide y los días de la
constancia fiscal (decisión de Oscar, 2026-09-29: «ese tiempo es configurable
en la gerencia»)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def test_la_gerencia_guarda_lo_que_se_pide_y_los_dias(client, usuario_factory):
    from portal.models import ConfiguracionPortal

    client.force_login(usuario_factory(rol="super_admin"))
    r = client.get("/ajustes/portal/")
    html = r.content.decode()
    assert r.status_code == 200 and "Antigüedad máxima de la constancia fiscal" in html
    assert "no caduca" in html and "un solo uso" not in html
    client.post("/ajustes/portal/", {"documentos_activo": "1",
                                     "requeridos": ["csf", "acta_constitutiva", "inventado"],
                                     "csf_vigencia_dias": "90"})
    cfg = ConfiguracionPortal.obtener()
    assert cfg.documentos_activo and cfg.csf_vigencia_dias == 90
    assert cfg.documentos_requeridos == ["csf", "acta_constitutiva"]
    # Fuera de rango no se guarda.
    client.post("/ajustes/portal/", {"csf_vigencia_dias": "0"})
    assert ConfiguracionPortal.obtener().csf_vigencia_dias == 90


def test_la_pantalla_dice_si_el_chalan_puede_leer_constancias(client, usuario_factory, monkeypatch):
    client.force_login(usuario_factory(rol="super_admin"))
    monkeypatch.setattr("apps.los_ajustes.views._chalan_lee_csf", lambda: False)
    assert "no tiene llaves para leer constancias" in client.get("/ajustes/portal/").content.decode()
    monkeypatch.setattr("apps.los_ajustes.views._chalan_lee_csf", lambda: True)
    assert "listo para leer constancias" in client.get("/ajustes/portal/").content.decode()


def test_sin_permiso_de_ajustes_no_entra(client, usuario_factory):
    client.force_login(usuario_factory(rol="disenador"))
    assert client.get("/ajustes/portal/").status_code in (302, 403)
