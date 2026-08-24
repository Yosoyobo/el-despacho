"""Un campo del formulario renderizado DOS veces se guarda vacío, en silencio.

Oscar, 2026-08-23 (tercer reporte del mismo síntoma): «las tareas y mandados
siguen sin actualizar la ubicación». Sus capturas dieron el diagnóstico: el
formulario mostraba «Destino lat» y «Destino lng» como campos con etiqueta —
siendo `HiddenInput` — y el geo-picker sí había resuelto el punto
(`19.350339, -99.297987`, con el pin en el mapa). Aun así la tarea se guardaba
«Sin ubicación fijada todavía».

La causa: el loop `{% for f in form %}` de `form_tarea.html` sólo saltaba
`destino_etiqueta`, así que `destino_lat`/`destino_lng` se pintaban ahí Y otra
vez junto al picker. Con dos inputs del mismo `name`:

  · `getElementById` devuelve el PRIMERO → el picker le escribe a ese;
  · el POST manda los dos valores;
  · y **Django se queda con el ÚLTIMO**, que iba vacío.

Nada falla, nada avisa: el dato simplemente no llega. Por eso el candado mira el
HTML RENDERIZADO y cuenta, en vez de revisar la plantilla a ojo.
"""

from __future__ import annotations

import datetime as dt
import re

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]

CAMPOS = ("destino_etiqueta", "destino_lat", "destino_lng")


@pytest.fixture
def proyecto(usuario_factory):
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto

    autor = usuario_factory(rol="super_admin")
    cli = Cliente.objects.create(razon_social="ACME")
    return Proyecto.objects.create(nombre="P", cliente=cli, creado_por=autor)


def _duplicados(html: str) -> dict[str, int]:
    """Cuántas veces aparece cada `name=` del destino. Más de una = bug."""
    return {
        c: len(re.findall(rf'name="{c}"', html))
        for c in CAMPOS
        if len(re.findall(rf'name="{c}"', html)) > 1
    }


@pytest.mark.parametrize(
    "ruta",
    [
        "/proyectos/{p}/tareas/nueva",    # el form del proyecto — el de la captura
        "/tareas/nueva/",                 # el modal global
    ],
)
def test_ningun_campo_del_destino_se_renderiza_dos_veces(client, usuario_factory, proyecto, ruta):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    r = client.get(ruta.format(p=proyecto.pk), HTTP_HX_REQUEST="true")
    assert r.status_code == 200, f"{ruta} devolvió {r.status_code}"
    dup = _duplicados(r.content.decode())
    assert not dup, (
        f"campos duplicados en {ruta}: {dup}. Con dos inputs del mismo name, "
        "Django se queda con el último y el dato se pierde sin avisar."
    )


def test_editar_una_tarea_tampoco_los_duplica(client, usuario_factory, proyecto):
    from apps.el_pizarron.models import Tarea

    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    t = Tarea.objects.create(proyecto=proyecto, titulo="Entrega", tipo="entrega",
                             creado_por=admin, fecha_compromiso=dt.date.today())
    r = client.get(f"/tareas/{t.pk}/editar")
    assert r.status_code == 200
    assert not _duplicados(r.content.decode())


def test_el_pin_llega_a_la_base_desde_el_form_del_proyecto(client, usuario_factory, proyecto):
    """La prueba de punta a punta del síntoma que Oscar reportó."""
    from apps.el_pizarron.models import Tarea

    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    r = client.post(f"/proyectos/{proyecto.pk}/tareas/nueva", {
        "titulo": "Entrega con pin", "tipo": "entrega", "estado": "pendiente",
        "prioridad": "media", "asignada_a": admin.pk, "responsables": [admin.pk],
        "fecha_compromiso": dt.date.today().isoformat(),
        "destino_etiqueta": "Stampa",
        "destino_lat": "19.350339", "destino_lng": "-99.297987",
    })
    assert r.status_code in (200, 302), r.status_code
    t = Tarea.objects.filter(titulo="Entrega con pin").first()
    assert t is not None, "no se creó la tarea"
    assert t.destino_etiqueta == "Stampa"
    assert t.destino_lat == pytest.approx(19.350339), (
        "el pin no llegó a la base — es el bug del campo duplicado"
    )
    assert t.destino_lng == pytest.approx(-99.297987)


def test_asi_se_perdia_el_dato_cuando_el_campo_iba_dos_veces(client, usuario_factory, proyecto):
    """Reproduce el MECANISMO, no sólo el síntoma.

    Un navegador con el campo renderizado dos veces manda los dos valores: el
    que llenó el picker y el vacío. Django se queda con el último. Este test
    documenta ese comportamiento para que nadie vuelva a suponer que «mandar el
    campo» basta.
    """
    from django.http import QueryDict

    q = QueryDict(mutable=True)
    q.update({"destino_lat": "19.350339"})
    q.appendlist("destino_lat", "")          # el segundo input, vacío
    assert q["destino_lat"] == "", (
        "si esto cambiara, el bug del duplicado dejaría de perder el dato — "
        "pero mientras Django tome el último valor, un campo repetido lo borra"
    )
    assert q.getlist("destino_lat") == ["19.350339", ""]


# ── El mismo candado en los OTROS formularios con geo-picker ─────────────────
#
# El olvido fue exclusivo de `form_tarea.html`; cliente y proveedor sí excluyen
# `lat`/`lng` de su loop. Se cubren igual porque el modo de falla es silencioso y
# el siguiente que agregue un campo oculto a uno de estos forms no tiene por qué
# conocer esta historia.

@pytest.mark.parametrize("nombre_url,campos", [
    ("cartera-nuevo", ("lat", "lng")),
    ("catalogo-proveedor-nuevo", ("lat", "lng")),
])
def test_los_forms_con_mapa_no_duplican_sus_coordenadas(client, usuario_factory, nombre_url, campos):
    from django.urls import reverse

    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    ruta = reverse(nombre_url)
    r = client.get(ruta)
    assert r.status_code == 200, f"{ruta} devolvió {r.status_code}"
    html = r.content.decode()
    dup = {c: len(re.findall(rf'name="{c}"', html))
           for c in campos if len(re.findall(rf'name="{c}"', html)) > 1}
    assert not dup, f"campos duplicados en {ruta}: {dup}"
