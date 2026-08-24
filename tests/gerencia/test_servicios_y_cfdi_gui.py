"""Las pantallas de Servicios y CFDI recibidos (S-NUC-Servicios, 2026-08-24).

Oscar, dos veces en la misma sesión: «todo lo que estamos integrando debe tener
su GUI y sus ajustes en el sidebar». Un servicio que corre pero no se ve desde
la interfaz es peor que uno que no está — nadie sabe si responde, nadie puede
ajustarlo, y el día que falle nadie sabe por dónde empezar.

Lo que cuidan estas pruebas:

1. Que **cada pieza integrada tenga su renglón** en el menú. Es la regla, y lo
   que se olvida es justamente esto.
2. Que **el estado sea el real**, no una suposición del archivo de
   configuración.
3. Que **abrir una sub-pantalla no marque dos renglones activos**.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_gerencia(usuario_factory):
    return usuario_factory(rol="super_admin")


# ── Que existan y estén gateadas ───────────────────────────────────────────


def test_la_pantalla_de_servicios_abre(client, admin_gerencia, monkeypatch):
    from lib.site import servicios

    monkeypatch.setattr(servicios, "_http", lambda url, **k: True)
    client.force_login(admin_gerencia)
    r = client.get(reverse("ajustes-servicios"))
    assert r.status_code == 200
    for nombre in (b"Gotenberg", b"n8n", b"Paperless"):
        assert nombre in r.content, f"falta {nombre!r} en la pantalla"


def test_la_pantalla_de_cfdi_abre(client, admin_gerencia):
    client.force_login(admin_gerencia)
    r = client.get(reverse("ajustes-cfdi"))
    assert r.status_code == 200


def test_las_dos_estan_gateadas(client, usuario_factory):
    client.force_login(usuario_factory(rol="miembro"))
    for ruta in ("ajustes-servicios", "ajustes-cfdi"):
        r = client.get(reverse(ruta))
        assert r.status_code in (302, 403), f"{ruta} dejó entrar a quien no debe"


# ── La regla: cada pieza integrada, con su renglón ─────────────────────────


def test_cada_pieza_integrada_tiene_su_renglon_en_el_menu():
    """La regla de Oscar. Lo que se olvida es justamente esto.

    Se lee el archivo por su ruta y NO de una respuesta del cliente: el `DIRS`
    de las pruebas resuelve `sidebar.html` al de El Taller, así que mirar el
    HTML servido daría verde sin haber tocado el menú de La Gerencia.
    """
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent.parent
    menu = (raiz / "la-gerencia/templates/_componentes_tailadmin/sidebar.html").read_text()

    for ruta in ("ajustes-documentos", "ajustes-rutas", "ajustes-servicios", "ajustes-cfdi"):
        assert ruta in menu, f"«{ruta}» no tiene renglón en el menú de La Gerencia"


def test_ninguna_subpantalla_prende_tambien_los_ajustes():
    """Sin la excepción se ven dos renglones activos a la vez."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent.parent
    menu = (raiz / "la-gerencia/templates/_componentes_tailadmin/sidebar.html").read_text()

    for ruta in ("/ajustes/documentos", "/ajustes/servicios", "/ajustes/cfdi"):
        assert f"'{ruta}' in request.path" in menu, (
            f"abrir {ruta} marcaría también «Los Ajustes» como activo"
        )


# ── El estado tiene que ser el de verdad ───────────────────────────────────


def test_lo_que_no_responde_se_marca(client, admin_gerencia, monkeypatch):
    """No se da por vivo porque el archivo de configuración lo declare."""
    from lib.site import servicios

    monkeypatch.setattr(servicios, "_http", lambda url, **k: False)
    client.force_login(admin_gerencia)
    r = client.get(reverse("ajustes-servicios"))
    assert b"No responde" in r.content
    assert b"0 de 4" in r.content


def test_un_401_cuenta_como_que_si_esta(monkeypatch):
    """n8n contesta 401 sin credencial: eso significa que ESTÁ, no que falta."""
    import urllib.request

    from lib.site import servicios

    class _Http401(Exception):
        code = 401

    def _explota(*a, **k):
        raise _Http401()

    monkeypatch.setattr(urllib.request, "urlopen", _explota)
    assert servicios._http("http://n8n:5678/healthz") is True


def test_un_servicio_caido_de_verdad_da_falso(monkeypatch):
    import urllib.request

    from lib.site import servicios

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("refused")))
    assert servicios._http("http://gotenberg:3000/health") is False


# ── Resolver un pendiente ──────────────────────────────────────────────────


def test_se_puede_ignorar_un_pendiente(client, admin_gerencia):
    from apps.facturacion.models import ESTADO_IGNORADO, CfdiEntrante

    c = CfdiEntrante.objects.create(uuid="AAAA-BBBB", emisor_nombre="Proveedor X",
                                    motivo="No se encontró factura")
    client.force_login(admin_gerencia)
    r = client.post(reverse("ajustes-cfdi"), {"pk": c.pk, "accion": "ignorar"})
    assert r.status_code == 302
    c.refresh_from_db()
    assert c.estado == ESTADO_IGNORADO
    assert c.resuelto_por == admin_gerencia


def test_el_filtro_por_defecto_muestra_los_pendientes(client, admin_gerencia):
    """Es a lo que se entra: lo resuelto no necesita atención."""
    from apps.facturacion.models import ESTADO_IGNORADO, CfdiEntrante

    CfdiEntrante.objects.create(uuid="PEND-1", emisor_nombre="Espera turno")
    CfdiEntrante.objects.create(uuid="IGN-1", emisor_nombre="Ya resuelto",
                                estado=ESTADO_IGNORADO)
    client.force_login(admin_gerencia)
    r = client.get(reverse("ajustes-cfdi"))
    assert b"Espera turno" in r.content
    assert b"Ya resuelto" not in r.content
