"""El Dashboard exige sesión — candado tras el susto del 2026-08-24.

Qué pasó: al agregar un helper JUSTO ENCIMA de `def home(request)`, el
`@login_required` que era de la vista quedó aplicado al helper. La vista se
quedó sin él y el Dashboard respondió 200 a cualquiera durante unos cuarenta
minutos. No hubo fuga —sin sesión todas las consultas fallan y el código las
captura devolviendo listas vacías, así que la página salía como un cascarón—
pero no debía ser alcanzable.

Es la SEGUNDA vez que este error aparece en el repo: en agosto pasó igual con
`_primer_error` en el detalle de proyecto. La forma de que no haya una tercera
no es acordarse, es esto.

Estas pruebas miran lo que de verdad importa: que la vista responda pidiendo
identificación. Da igual cómo esté escrito el decorador — se comprueba el
comportamiento, no el código.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_el_dashboard_no_abre_sin_sesion(client):
    """Lo que falló. Un 200 aquí significa que la vista perdió su decorador."""
    r = client.get(reverse("taller-home"))
    assert r.status_code in (301, 302), (
        f"El Dashboard respondió {r.status_code} sin sesión: se quedó sin @login_required"
    )
    assert "sign-in" in r["Location"] or "login" in r["Location"], (
        f"redirige a {r['Location']}, que no parece la pantalla de identificarse"
    )


def test_con_sesion_si_abre(client, usuario_factory):
    """La otra mitad: que el candado no deje fuera a quien sí debe entrar."""
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.get(reverse("taller-home"))
    assert r.status_code == 200


def test_el_helper_de_los_relojes_no_lleva_decorador_de_vista():
    """La causa raíz, en concreto.

    `_infra_gauges` recibe un usuario, no una petición. Si alguien vuelve a
    dejar un decorador de vista encima, revienta con «'Usuario' object has no
    attribute 'user'» — y como la llamada va envuelta en un `try`, el fallo se
    traga y los relojes simplemente no aparecen, sin decir por qué.
    """
    from apps.taller_home.views import _infra_gauges

    assert not hasattr(_infra_gauges, "__wrapped__"), (
        "_infra_gauges quedó envuelto por un decorador de vista; "
        "seguramente se lo robó a `home`"
    )
