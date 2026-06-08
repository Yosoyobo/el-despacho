"""S-Buzon-Estados-V1: lado El Taller (helpers, filtro, badge, form)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _ticket(autor, estado="nuevo"):
    from buzon.models import MensajeBuzon
    return MensajeBuzon.objects.create(
        autor=autor, tipo="otro", asunto="Asunto", cuerpo="Cuerpo largo.", estado=estado,
    )


def test_estados_activos_incluye_custom_y_color(usuario_factory):
    from buzon import estados
    from buzon.models import EstadoBuzon
    EstadoBuzon.objects.create(
        slug="en_seguimiento", label="En seguimiento", color="#7a5af8",
        orden=25, terminal=False, activo=True, sistema=False,
    )
    slugs = {e["slug"] for e in estados.estados_activos()}
    assert "en_seguimiento" in slugs
    # El signal invalidó el cache, así que el color refleja la DB.
    assert estados.color_de("en_seguimiento") == "#7a5af8"
    assert estados.label_de("en_seguimiento") == "En seguimiento"


def test_estado_inactivo_no_aparece_en_filtro(usuario_factory):
    from buzon import estados
    from buzon.models import EstadoBuzon
    EstadoBuzon.objects.create(
        slug="oculto_x", label="Oculto", color="#667085",
        orden=99, terminal=False, activo=False, sistema=False,
    )
    slugs = {e["slug"] for e in estados.estados_activos()}
    assert "oculto_x" not in slugs


def test_lista_filtro_muestra_estados_configurados(client, usuario_factory):
    from buzon.models import EstadoBuzon
    EstadoBuzon.objects.create(
        slug="en_seguimiento2", label="Seguimiento LC", color="#fb6514",
        orden=25, terminal=False, activo=True, sistema=False,
    )
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/buzon/")
    assert resp.status_code == 200
    assert b"Seguimiento LC" in resp.content


def test_form_respuesta_ofrece_estado_custom(usuario_factory):
    from apps.buzon_empleado.forms import RespuestaAdminForm
    from buzon.models import EstadoBuzon
    EstadoBuzon.objects.create(
        slug="en_seguimiento3", label="Seguimiento", color="#465fff",
        orden=25, terminal=False, activo=True, sistema=False,
    )
    admin = usuario_factory(rol="super_admin")
    msg = _ticket(admin, estado="nuevo")
    form = RespuestaAdminForm(instance=msg)
    slugs = {valor for valor, _ in form.fields["estado"].choices}
    assert "en_seguimiento3" in slugs
    assert "nuevo" in slugs


def test_form_conserva_estado_actual_si_inactivo(usuario_factory):
    """Si el ticket está en un estado que ya no está activo, el dropdown lo
    conserva para no perderlo al guardar."""
    from apps.buzon_empleado.forms import RespuestaAdminForm
    from buzon.models import EstadoBuzon
    EstadoBuzon.objects.create(
        slug="viejo_x", label="Viejo", color="#667085",
        orden=99, terminal=False, activo=False, sistema=False,
    )
    admin = usuario_factory(rol="super_admin")
    msg = _ticket(admin, estado="viejo_x")
    form = RespuestaAdminForm(instance=msg)
    slugs = {valor for valor, _ in form.fields["estado"].choices}
    assert "viejo_x" in slugs


def test_badge_hex_en_lista(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    _ticket(admin, estado="nuevo")
    client.force_login(admin)
    resp = client.get("/buzon/")
    assert resp.status_code == 200
    # El badge usa la custom property --ec con el color del estado "nuevo".
    assert b"badge-hex" in resp.content
    assert b"#0ba5ec" in resp.content
