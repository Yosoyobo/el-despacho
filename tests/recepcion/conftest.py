"""Fixtures de La Recepción (el portal de clientes).

Las pruebas corren con el settings común (`tests.django_settings`), así que aquí
se le pone a cada test la forma de La Recepción: su urlconf, su cadena de
middleware (con la puerta `SesionClienteMiddleware` y SIN `AuthenticationMiddleware`),
su cookie y sus context processors. `test_infra_recepcion` comprueba que esta
cadena es la misma que declara `la_recepcion/settings.py`.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

MIDDLEWARE_RECEPCION = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.portal_cliente.middleware.SesionClienteMiddleware",
]

CONTEXT_PROCESSORS_RECEPCION = [
    "django.template.context_processors.request",
    "django.template.context_processors.csrf",
    "django.contrib.messages.context_processors.messages",
    "lib.aviso_deploy.contexto_aviso_deploy",
    "lib.version.contexto_version",
    "apps.portal_cliente.context_processors.portal",
]


@pytest.fixture(autouse=True)
def _forma_de_recepcion(settings, monkeypatch):
    settings.ROOT_URLCONF = "la_recepcion.urls"
    settings.MIDDLEWARE = MIDDLEWARE_RECEPCION
    settings.SESSION_COOKIE_NAME = "recepcion_session"
    settings.CSRF_COOKIE_NAME = "recepcion_csrftoken"
    settings.MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
    settings.RECEPCION_URL = "https://recepcion.ejemplo.mx"
    settings.TEMPLATES = [{
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [RAIZ / "la-recepcion" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": CONTEXT_PROCESSORS_RECEPCION},
    }]
    # El rate-limit usa Redis: en las pruebas es un contador en memoria (las que
    # prueban el límite lo reemplazan por uno propio).
    monkeypatch.setattr("apps.portal_cliente.views.intentar", lambda *a, **k: 1)


@pytest.fixture
def correos(monkeypatch):
    """Lo que El Cartero habría mandado: [(destinatario, asunto, html)]."""
    from lib import cartero

    enviados: list[tuple[str, str, str]] = []

    def _falso(*, destinatario, asunto, html, **kw):
        enviados.append((destinatario, asunto, html))
        return cartero.ResultadoCorreo(ok=True, proveedor="pruebas")

    monkeypatch.setattr(cartero, "enviar", _falso)
    return enviados


def token_del_correo(html: str) -> str:
    import re

    m = re.search(r"/entrar/([A-Za-z0-9_\-]+)/", html)
    assert m, "el correo no trae el enlace de entrada"
    return m.group(1)


@pytest.fixture
def servicio(db):
    from apps.el_catalogo.models import CategoriaServicio, Servicio

    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    return Servicio.objects.create(nombre="Playera base", categoria=cat, precio_base=Decimal("100.00"))


@pytest.fixture
def armar_cliente(db, cliente_factory, proyecto_factory, servicio, usuario_factory):
    """Un cliente con UN contacto, un proyecto en producción con un producto,
    una cotización enviada (con PDF) y una factura emitida (con PDF y XML).

    Cada pieza lleva el `sufijo` en su nombre para que las pruebas de
    aislamiento busquen en el HTML el del OTRO cliente.
    """
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    from apps.facturacion.models import Factura, FacturaItem
    from apps.la_cartera.models import ClienteContacto
    from apps.los_proyectos.models import ProyectoProducto

    def _armar(sufijo: str, email: str):
        cliente = cliente_factory(razon_social=f"EMPRESA-{sufijo}")
        contacto = ClienteContacto.objects.create(cliente=cliente, nombre=f"Contacto {sufijo}",
                                                  email=email, principal=True)
        proyecto = proyecto_factory(cliente=cliente, nombre=f"PROYECTO-{sufijo}",
                                    estado="en_proceso_produccion",
                                    fecha_compromiso=dt.date.today() + dt.timedelta(days=10))
        ProyectoProducto.objects.create(proyecto=proyecto, servicio=servicio, cantidad=150,
                                        nombre_proyecto=f"PRODUCTO-{sufijo}",
                                        nota=f"NOTA-INTERNA-{sufijo}",
                                        costo_unitario=Decimal("37.00"))
        cot = Cotizacion.objects.create(cliente=cliente, proyecto=proyecto, titulo=f"COTIZACION-{sufijo}",
                                        estado="enviada", enviada_en=dt.datetime.now(dt.UTC),
                                        pdf_file_id=f"drive-cot-{sufijo}",
                                        notas=f"NOTAS-COT-{sufijo}")
        CotizacionItem.objects.create(cotizacion=cot, concepto="Playeras", cantidad=Decimal("10"),
                                      precio_unitario=Decimal("100.00"))
        fac = Factura.objects.create(cliente=cliente, proyecto=proyecto, estado="emitida",
                                     concepto=f"FACTURA-{sufijo}", pdf_file_id=f"drive-fac-{sufijo}",
                                     xml_file_id=f"drive-xml-{sufijo}")
        FacturaItem.objects.create(factura=fac, descripcion="Trabajo", cantidad=1,
                                   precio_unitario=Decimal("1000.00"))
        return {"cliente": cliente, "contacto": contacto, "proyecto": proyecto,
                "cotizacion": cot, "factura": fac}

    return _armar


@pytest.fixture
def acceso_de(db):
    """Da de alta el acceso sin pasar por el correo (para las pruebas del portal)."""
    from portal.models import AccesoCliente

    def _dar(datos, email=None):
        c = datos["contacto"]
        return AccesoCliente.objects.create(cliente=datos["cliente"], contacto=c,
                                            email=email or c.email, nombre=c.nombre)

    return _dar


@pytest.fixture
def entrar_como(client):
    """Abre la sesión del acceso por el camino de verdad: un enlace canjeado."""
    from portal import servicios

    def _entrar(acceso, cliente_http=None):
        http = cliente_http or client
        token = servicios._crear_enlace(acceso, "entrada")
        r = http.post(f"/entrar/{token}/")
        assert r.status_code == 302 and r["Location"] == "/", r.content[:300]
        return http

    return _entrar
