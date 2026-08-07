"""LC 2026-08-07 — catálogo de Motivos de cancelación en La Gerencia.

Oscar pidió poder cambiar las etiquetas «en algún lado fácil» y eligió que
vivieran junto a los demás catálogos configurables. Es el ÚNICO punto de este
sprint que toca La Gerencia.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


@pytest.fixture
def super_admin(django_user_model):
    return django_user_model.objects.create_user(
        email="jefa@lc.mx", password="x", rol="super_admin", nombre_completo="Jefa LC",
    )


@pytest.fixture
def miembro(django_user_model):
    return django_user_model.objects.create_user(
        email="dani@lc.mx", password="x", rol="miembro", nombre_completo="Dani",
    )


def test_la_lista_muestra_los_motivos_sembrados(client, super_admin):
    client.force_login(super_admin)
    resp = client.get("/catalogos/motivos-cancelacion/")
    assert resp.status_code == 200
    cuerpo = resp.content.decode()
    for label in ("Precio", "Cliente desistió", "Tiempos", "Otro"):
        assert label in cuerpo


def test_renombrar_un_motivo(client, super_admin):
    from apps.los_proyectos.models import MotivoCancelacion
    client.force_login(super_admin)
    resp = client.post("/catalogos/motivos-cancelacion/precio/editar/",
                       {"label": "Presupuesto del cliente", "orden": 10, "activo": "on"})
    assert resp.status_code == 302
    m = MotivoCancelacion.objects.get(slug="precio")
    assert m.label == "Presupuesto del cliente"
    assert m.slug == "precio", "el slug es la identidad: no cambia al renombrar"


def test_crear_un_motivo_propio(client, super_admin):
    from apps.los_proyectos.models import MotivoCancelacion
    client.force_login(super_admin)
    client.post("/catalogos/motivos-cancelacion/nuevo/",
                {"slug": "", "label": "Se pospuso", "orden": 40, "activo": "on"})
    m = MotivoCancelacion.objects.get(label="Se pospuso")
    assert m.slug == "se_pospuso"
    assert m.sistema is False


def test_un_motivo_del_sistema_no_se_borra(client, super_admin):
    from apps.los_proyectos.models import MotivoCancelacion
    client.force_login(super_admin)
    client.post("/catalogos/motivos-cancelacion/precio/borrar/")
    assert MotivoCancelacion.objects.filter(slug="precio").exists()


def test_ocultar_un_motivo_lo_saca_de_las_pastillas(client, super_admin):
    from apps.los_proyectos.models import MotivoCancelacion, motivos_activos
    client.force_login(super_admin)
    client.post("/catalogos/motivos-cancelacion/tiempos/toggle/")
    assert MotivoCancelacion.objects.get(slug="tiempos").activo is False
    assert "tiempos" not in {m.slug for m in motivos_activos()}


def test_sin_permiso_no_entra(client, miembro):
    client.force_login(miembro)
    assert client.get("/catalogos/motivos-cancelacion/").status_code == 403
