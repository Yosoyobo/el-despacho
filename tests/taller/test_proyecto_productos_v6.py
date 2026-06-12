"""S-LC-Feedback-V6 Bloque 5: toggle 'incluir en el cálculo' + acordeón de
productos en el detalle del proyecto."""

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture()
def entorno(usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    admin = usuario_factory(rol="super_admin")
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    srv = Servicio.objects.create(nombre="Taza", precio_base="100", costo="30", categoria=cat)
    p = proyecto_factory(nombre="Acordeón")
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=srv, cantidad=2, incluir_en_calculo=True,
    )
    return {"admin": admin, "p": p, "pp": pp, "srv": srv}


def _post_autosave(client, p, pp, srv, incluir: bool):
    """Simula el autosave HTMX del detalle (hx-post change delay:700ms).
    Checkbox apagado = el navegador NO manda la clave."""
    data = {
        "nombre": p.nombre, "cliente": p.cliente_id, "estado": p.estado, "descripcion": "",
        "productos-TOTAL_FORMS": "1", "productos-INITIAL_FORMS": "1",
        "productos-MIN_NUM_FORMS": "0", "productos-MAX_NUM_FORMS": "1000",
        "productos-0-id": pp.pk,
        "productos-0-servicio": srv.pk,
        "productos-0-cantidad": "2",
        "productos-0-merma": "0",
        "productos-0-precio_unitario": "",
        "productos-0-costo_unitario": "",
        "productos-0-nota": "",
        "productos-0-procesos_json": "[]",
    }
    if incluir:
        data["productos-0-incluir_en_calculo"] = "on"
    return client.post(f"/proyectos/{p.pk}/", data, follow=True,
                       HTTP_HX_REQUEST="true")


def test_toggle_incluir_persiste_apagado(client, entorno):
    """Reproducción del bug reportado: apagar el toggle debe persistir False."""
    client.force_login(entorno["admin"])
    resp = _post_autosave(client, entorno["p"], entorno["pp"], entorno["srv"], incluir=False)
    assert resp.status_code == 200
    entorno["pp"].refresh_from_db()
    assert entorno["pp"].incluir_en_calculo is False
    # El monto calculado del proyecto excluye la línea.
    assert entorno["p"].monto_calculado == Decimal("0")


def test_toggle_incluir_persiste_encendido(client, entorno):
    client.force_login(entorno["admin"])
    entorno["pp"].incluir_en_calculo = False
    entorno["pp"].save(update_fields=["incluir_en_calculo"])
    _post_autosave(client, entorno["p"], entorno["pp"], entorno["srv"], incluir=True)
    entorno["pp"].refresh_from_db()
    assert entorno["pp"].incluir_en_calculo is True


def test_detalle_muestra_excluida_opaca(client, entorno):
    """Al recargar, la línea excluida se rendea con el checkbox sin marcar."""
    client.force_login(entorno["admin"])
    entorno["pp"].incluir_en_calculo = False
    entorno["pp"].save(update_fields=["incluir_en_calculo"])
    body = client.get(f"/proyectos/{entorno['p'].pk}/").content.decode()
    # El input del formset NO debe venir checked.
    import re
    m = re.search(r'name="productos-0-incluir_en_calculo"[^>]*', body)
    assert m, "checkbox de incluir no renderizado"
    assert "checked" not in m.group(0)


def test_acordeon_oculta_despues_de_dos(client, entorno):
    """V6: con >2 productos, el detalle muestra 2 y esconde el resto tras
    'Ver más (+N)'."""
    from apps.los_proyectos.models import ProyectoProducto
    for _i in range(3):
        ProyectoProducto.objects.create(
            proyecto=entorno["p"], servicio=entorno["srv"], cantidad=1,
        )
    client.force_login(entorno["admin"])
    body = client.get(f"/proyectos/{entorno['p'].pk}/").content.decode()
    assert "Ver más (+2)" in body          # 4 guardados − 2 visibles
    # 2 tarjetas ocultas (el JS usa [data-acordeon-oculto] entre corchetes,
    # por eso el marcador de tarjeta se busca con el cierre de tag).
    assert body.count("data-acordeon-oculto>") == 2


def test_acordeon_no_aparece_con_pocos(client, entorno):
    client.force_login(entorno["admin"])
    body = client.get(f"/proyectos/{entorno['p'].pk}/").content.decode()
    assert "Ver más (+" not in body
    assert body.count("data-acordeon-oculto>") == 0
