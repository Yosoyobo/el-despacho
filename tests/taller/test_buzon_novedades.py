"""S-LC-Feedback-V11 — estado «implementado» con push a TODO el equipo +
acción masiva por estado dinámico (decisión Oscar: "que todos sepan" las
novedades y poder aplicar cualquier estado a varios mensajes)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


def _ticket(autor, estado="leido"):
    from buzon.models import MensajeBuzon
    return MensajeBuzon.objects.create(
        autor=autor, tipo="sugerencia", asunto="Mejora X", cuerpo="Cuerpo.", estado=estado,
    )


def test_estado_notificar_todos_push_a_todo_el_equipo(usuario_factory):
    """Mover un mensaje a un estado con acción `notificar_todos` deja entrega del
    Interfón a TODOS los usuarios activos."""
    from apps.taller_home.push_handlers import notificar_buzon_estado

    from buzon.models import EstadoBuzon
    from interfono.models import InterfonoEntrega

    EstadoBuzon.objects.create(
        slug="implementado", label="Implementado", color="#12b76a",
        orden=50, terminal=True, activo=True, sistema=False, accion="notificar_todos",
    )
    admin = usuario_factory(rol="super_admin")
    autor = usuario_factory(rol="disenador")
    otro = usuario_factory(rol="contador")
    msg = _ticket(autor, estado="implementado")

    notificar_buzon_estado(msg, admin)

    # Todos los activos (admin, autor, otro) reciben la novedad.
    destinatarios = set(InterfonoEntrega.objects.values_list("usuario_id", flat=True))
    assert {admin.pk, autor.pk, otro.pk} <= destinatarios


def test_accion_masiva_estado_destino_aplica_estado_dinamico(client, usuario_factory):
    """La barra de acciones masivas aplica CUALQUIER estado activo vía
    `estado_destino` (no solo leído/respondido/archivado)."""
    from buzon.models import EstadoBuzon, MensajeBuzon
    EstadoBuzon.objects.create(
        slug="ignorado", label="Ignorado", color="#667085",
        orden=60, terminal=True, activo=True, sistema=False, accion="ninguna",
    )
    admin = usuario_factory(rol="super_admin")
    a = _ticket(usuario_factory(rol="disenador"))
    b = _ticket(usuario_factory(rol="disenador"))
    client.force_login(admin)
    resp = client.post("/buzon/masivo", {
        "accion": "estado_destino", "estado_destino": "ignorado",
        "ids": [a.pk, b.pk],
    })
    assert resp.status_code in (302, 200)
    assert MensajeBuzon.objects.get(pk=a.pk).estado == "ignorado"
    assert MensajeBuzon.objects.get(pk=b.pk).estado == "ignorado"
