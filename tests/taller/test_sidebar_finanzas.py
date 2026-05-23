"""S-LC-Feedback-V2: grupo 'Finanzas' colapsable en la sidebar del Taller."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_grupo_finanzas_aparece_para_admin(client, usuario_factory):
    """super_admin tiene permisos a Tesorería/Facturación/Contaduría → grupo visible."""
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'data-sidebar-group="finanzas"' in body
    assert "Tesorería" in body
    assert "Facturación" in body
    assert "Contaduría" in body


def test_grupo_finanzas_no_aparece_sin_permisos(client, usuario_factory):
    """Diseñador no tiene permisos a finanzas → el grupo NO se renderiza."""
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # El botón del grupo no debe estar presente.
    assert 'data-sidebar-group="finanzas"' not in body


def test_grupo_expandido_si_ruta_activa(client, usuario_factory):
    """Si estás en /tesoreria/, el grupo se renderiza expandido (sin hidden)."""
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.get("/tesoreria/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # El panel del grupo no debe tener 'hidden' cuando la ruta está activa.
    # Busco la línea del panel:
    import re
    m = re.search(r'data-sidebar-group-panel="finanzas"[^>]*class="([^"]*)"', body)
    assert m, "No se encontró el panel del grupo"
    clases = m.group(1)
    assert "hidden" not in clases
