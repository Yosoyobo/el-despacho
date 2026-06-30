"""S-LC-Feedback-V13 — Bug Oscar 2026-06-29: "agregué una tarea con fecha del
lunes a un proyecto SIN fecha de compromiso y el sistema tomó esa fecha como
compromiso del proyecto".

Tras rastrear todo el flujo NO existe código que copie la fecha de la tarea al
proyecto. Este test blinda esa invariante: crear una tarea con fecha vía el
modal del detalle NO debe tocar `Proyecto.fecha_compromiso`.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_crear_tarea_con_fecha_no_cambia_compromiso_del_proyecto(
    client, usuario_factory, proyecto_factory,
):
    from apps.el_pizarron.models import Tarea
    from apps.el_pizarron.models.estado_tarea import EstadoTarea

    admin = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="por_cotizar")  # sin fecha_compromiso
    assert p.fecha_compromiso is None

    estado = EstadoTarea.objects.filter(activo=True).first().slug
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{p.pk}/agregar-tarea",
        data={
            "titulo": "Entregar el lunes",
            "estado": estado,
            "prioridad": "media",
            "tipo": "tarea",
            "asignada_a": admin.pk,
            "fecha_compromiso": "2026-07-06",  # un lunes
        },
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code in (200, 204)

    # La tarea se creó con SU fecha…
    t = Tarea.objects.get(proyecto=p)
    assert str(t.fecha_compromiso) == "2026-07-06"
    # …pero el proyecto SIGUE sin fecha de compromiso (no se contaminó).
    p.refresh_from_db()
    assert p.fecha_compromiso is None
