"""Candado: `/acerca/` es la portada pública que Google verifica.

Contexto: la verificación del cliente OAuth se rechazó con «Your home page does
not explain the purpose of your app» porque la "Application home page" apuntaba
al sitio de marketing de Learning Center, que describe los servicios al cliente
y no este sistema. La página vive ahora en El Despacho y **tiene que seguir
siendo alcanzable sin sesión**: si algún día queda detrás del login, Google no
la puede leer y la verificación se cae otra vez — pero en silencio, porque nada
más en la app se rompe.

Lo que se fija aquí es el contrato con Google, no la redacción:
  · responde 200 SIN sesión (ni redirect al login)
  · dice qué es la app y quién la usa
  · explica los permisos de Google que pide, incluido que `drive.file` no
    alcanza el resto del Drive del usuario
  · enlaza el aviso de privacidad y los términos
"""

from __future__ import annotations

import pytest
from django.test import override_settings

pytestmark = pytest.mark.django_db


def _cuerpo(client) -> str:
    resp = client.get("/acerca/")
    # 200 directo: un 302 aquí significa que la página quedó detrás del login.
    assert resp.status_code == 200, (
        f"/acerca/ devolvió {resp.status_code}. Tiene que ser pública: es la "
        f"'Application home page' del cliente OAuth y Google la lee sin sesión."
    )
    return resp.content.decode("utf-8")


@override_settings(ROOT_URLCONF="tests.urls_taller")
def test_acerca_es_publica_en_el_taller(client):
    cuerpo = _cuerpo(client)

    # Identidad de la app y de quién es.
    assert "El Despacho" in cuerpo
    assert "Learning Center" in cuerpo

    # Propósito y que no es un servicio abierto — lo que Google reclamó.
    assert "sistema de administración interna" in cuerpo
    assert "No hay registro" in cuerpo

    # Los permisos de Google, con el alcance real de drive.file.
    assert "drive.file" in cuerpo
    assert "no da acceso al resto de tu Drive" in cuerpo

    # Enlaces obligatorios de la pantalla de consentimiento.
    assert "/legal/privacidad" in cuerpo
    assert "/legal/terminos" in cuerpo


@override_settings(ROOT_URLCONF="tests.urls_taller")
def test_acerca_no_pide_sesion(client):
    """Explícito y aparte: el modo de falla que importa es el redirect al login."""
    resp = client.get("/acerca/")
    assert resp.status_code != 302, "/acerca/ redirige — quedó detrás del login."
    assert resp.status_code == 200


@override_settings(ROOT_URLCONF="tests.urls_gerencia")
def test_acerca_tambien_en_la_gerencia(client):
    """Dual-copy §18: la página existe igual en las dos apps."""
    cuerpo = _cuerpo(client)
    assert "El Despacho" in cuerpo
    assert "drive.file" in cuerpo


def test_las_dos_copias_estan_sincronizadas():
    """§18: si alguien edita una copia y no la otra, esto lo caza."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    for nombre in ("_acerca_body.html", "acerca.html"):
        taller = (raiz / "el-taller" / "templates" / "legal" / nombre).read_text(encoding="utf-8")
        gerencia = (raiz / "la-gerencia" / "templates" / "legal" / nombre).read_text(encoding="utf-8")
        assert taller == gerencia, (
            f"legal/{nombre} difiere entre El Taller y La Gerencia. "
            f"Son copias sincronizadas (regla §18): edita las dos."
        )
