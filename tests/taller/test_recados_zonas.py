"""S-Recados-V2 (C5c): zonas Chat / Mi Buzón / Actividad + tabs."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_bandeja_ya_no_embebe_buzon(client, usuario_factory):
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    c = client.get("/recados/").content.decode()
    # El mini-buzón embebido (botón "Enviar al Buzón") ya no está.
    assert "Enviar al Buzón" not in c
    # Las tabs sí.
    assert "Mi Buzón" in c
    assert "Actividad" in c


def test_zona_buzon_muestra_mis_envios(client, usuario_factory):
    from buzon.models import MensajeBuzon
    u = usuario_factory(rol="disenador")
    MensajeBuzon.objects.create(autor=u, tipo="sugerencia", asunto="MiIdea", cuerpo="x" * 20)
    otro = usuario_factory(rol="contador")
    MensajeBuzon.objects.create(autor=otro, tipo="otro", asunto="Ajeno", cuerpo="y" * 20)
    client.force_login(u)
    c = client.get("/recados/buzon/").content.decode()
    assert "MiIdea" in c
    assert "Ajeno" not in c


def test_zona_actividad_mencion_chat(client, usuario_factory):
    from apps.recados.services_chat import enviar_mensaje, obtener_o_crear_directa
    autor = usuario_factory(rol="disenador")
    yo = usuario_factory(rol="contador")
    conv = obtener_o_crear_directa(autor, yo)
    enviar_mensaje(conversacion=conv, autor=autor, cuerpo=f"oye @{yo.slug}")
    client.force_login(yo)
    c = client.get("/recados/actividad/").content.decode()
    assert "Te mencionaron" in c


def test_zona_actividad_feed_proyecto(client, usuario_factory, proyecto_factory):
    from apps.los_proyectos import servicios_actividad
    from apps.los_proyectos.models import ProyectoAsignacion
    admin = usuario_factory(rol="super_admin")
    lider = usuario_factory(rol="disenador")
    p = proyecto_factory(creado_por=admin)
    ProyectoAsignacion.objects.create(proyecto=p, usuario=lider, rol_en_proyecto="lider")
    servicios_actividad.registrar(proyecto=p, tipo="tarea_creada",
                                  descripcion="Nueva tarea Diseno", actor=admin,
                                  url=f"/proyectos/{p.pk}/")
    client.force_login(lider)
    c = client.get("/recados/actividad/").content.decode()
    assert "Nueva tarea" in c
