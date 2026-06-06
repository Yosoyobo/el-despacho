"""S2b.2.1 — UI de gestión de aprendizajes del Chalán en La Gerencia.

CRUD bajo `/chalanes/aprendizajes/`. super_admin lee y modifica; dueño
sólo lee; otros roles 403/redirect.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.gerencia, pytest.mark.django_db]


def _crear_aprendizaje(autor=None, **kwargs):
    from chalanes.models import Aprendizaje
    defaults = dict(
        frase_o_patron="la heladería",
        interpretacion_correcta="$heladeria-michoacana",
        peso=1.0,
        activo=True,
    )
    defaults.update(kwargs)
    return Aprendizaje.objects.create(autor=autor, **defaults)


def test_lista_aprendizajes_visible_para_super_admin(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    _crear_aprendizaje(autor=u, frase_o_patron="la heladería del centro")
    resp = client.get("/chalanes/aprendizajes/")
    assert resp.status_code == 200
    assert b"la helader" in resp.content


def test_lista_visible_dueno_pero_no_modifica(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    _crear_aprendizaje()
    resp = client.get("/chalanes/aprendizajes/")
    assert resp.status_code == 200
    # El botón "+ Enseñar al Chalán" no debe aparecer para dueno.
    body = resp.content.decode()
    assert "Enseñar al Chalán" not in body or "aprendizaje-nuevo" not in body


def test_lista_403_para_disenador(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.get("/chalanes/aprendizajes/")
    assert resp.status_code in (302, 403)


def test_crear_aprendizaje_setea_autor(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    resp = client.post("/chalanes/aprendizajes/nuevo", {
        "frase_o_patron": "el cliente principal",
        "interpretacion_correcta": "$heladeria-michoacana",
        "peso": "1.0",
        "activo": "on",
    })
    assert resp.status_code == 302
    from chalanes.models import Aprendizaje
    ap = Aprendizaje.objects.get(frase_o_patron="el cliente principal")
    assert ap.autor_id == u.pk
    assert ap.activo is True


def test_editar_aprendizaje_actualiza(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    ap = _crear_aprendizaje(autor=u, frase_o_patron="vieja")
    resp = client.post(f"/chalanes/aprendizajes/{ap.pk}/editar", {
        "frase_o_patron": "nueva",
        "interpretacion_correcta": ap.interpretacion_correcta,
        "peso": "0.8",
        "activo": "on",
    })
    assert resp.status_code == 302
    ap.refresh_from_db()
    assert ap.frase_o_patron == "nueva"
    assert abs(ap.peso - 0.8) < 0.001


def test_toggle_desactiva_y_guarda_motivo(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    ap = _crear_aprendizaje(autor=u)
    resp = client.post(f"/chalanes/aprendizajes/{ap.pk}/toggle", {"motivo": "ya no aplica"})
    assert resp.status_code == 302
    ap.refresh_from_db()
    assert ap.activo is False
    assert ap.desactivado_por_id == u.pk
    assert "ya no aplica" in ap.motivo_desactivacion
    # Re-activar limpia.
    client.post(f"/chalanes/aprendizajes/{ap.pk}/toggle")
    ap.refresh_from_db()
    assert ap.activo is True
    assert ap.motivo_desactivacion == ""


def test_filtro_activos_inactivos(client, usuario_factory):
    from chalanes.models import Aprendizaje
    # `el_dictado_aprendizaje` es managed=False y compartida con tests de Taller;
    # en la suite completa pueden quedar filas comiteadas de otros tests que,
    # acumuladas, empujan "iI" fuera del slice [:200] del view. Partimos de
    # tabla limpia para que este test (sobre SUS dos filas) sea determinista;
    # el rollback de django_db restaura el estado al terminar.
    Aprendizaje.objects.all().delete()
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    _crear_aprendizaje(autor=u, frase_o_patron="aA", activo=True)
    _crear_aprendizaje(autor=u, frase_o_patron="iI", activo=False)
    resp = client.get("/chalanes/aprendizajes/?filtro=activos")
    assert b"aA" in resp.content and b"iI" not in resp.content
    resp = client.get("/chalanes/aprendizajes/?filtro=inactivos")
    assert b"iI" in resp.content and b"aA" not in resp.content


def test_modelo_compartido_visible_desde_taller(usuario_factory):
    """Garantiza que `chalanes.Aprendizaje` y `el_dictado.DictadoAprendizaje`
    leen y escriben la MISMA tabla (managed=False shadow)."""
    from apps.el_dictado.models import DictadoAprendizaje

    from chalanes.models import Aprendizaje
    u = usuario_factory(rol="super_admin")
    ap = Aprendizaje.objects.create(
        autor=u, frase_o_patron="cross-app",
        interpretacion_correcta="ok", peso=1.0,
    )
    # Visible desde el modelo de Taller.
    assert DictadoAprendizaje.objects.filter(pk=ap.pk, frase_o_patron="cross-app").exists()
