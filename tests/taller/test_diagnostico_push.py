"""S-LC-Feedback-V12 — el comando diagnostico_push corre y reporta el estado de
VAPID, suscripciones, categoría y entregas (ayuda a explicar por qué no llega
un push de novedades). Smoke test: no truena y produce reporte."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_diagnostico_push_corre(usuario_factory):
    usuario_factory(rol="disenador")
    out = StringIO()
    call_command("diagnostico_push", stdout=out)
    texto = out.getvalue()
    assert "VAPID" in texto
    assert "Suscripciones" in texto
    # Sin VAPID configurado en tests, debe avisarlo claramente.
    assert "NO configurado" in texto
