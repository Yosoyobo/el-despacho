"""S-Recados-V2 (C5a): el chat y los comentarios persisten menciones @/#/$ en
la tabla Referencia (alimenta el inbox 'te taggearon')."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def test_chat_persiste_mencion(usuario_factory):
    from apps.recados.services_chat import enviar_mensaje, obtener_o_crear_directa

    from referencias.models import Referencia
    autor = usuario_factory(rol="disenador")
    mencionado = usuario_factory(rol="contador")
    conv = obtener_o_crear_directa(autor, mencionado)
    m = enviar_mensaje(conversacion=conv, autor=autor, cuerpo=f"hola @{mencionado.slug}")
    ref = Referencia.objects.filter(contenedor_tipo="mensaje_chat", contenedor_id=m.pk).first()
    assert ref is not None
    assert ref.usuario_id == mencionado.pk


def test_comentario_proyecto_persiste_mencion(client, usuario_factory, proyecto_factory):
    from referencias.models import Referencia
    admin = usuario_factory(rol="super_admin")
    mencionado = usuario_factory(rol="disenador")
    proyecto = proyecto_factory(creado_por=admin)
    client.force_login(admin)
    resp = client.post(f"/proyectos/{proyecto.pk}/comentar",
                       data={"cuerpo": f"ojo @{mencionado.slug}"})
    assert resp.status_code in (302, 200)
    ref = Referencia.objects.filter(contenedor_tipo="comentario_proyecto").first()
    assert ref is not None
    assert ref.usuario_id == mencionado.pk
