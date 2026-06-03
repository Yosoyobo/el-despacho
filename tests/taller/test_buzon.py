"""El Buzón — vista del empleado (El Taller)."""

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


def test_anonimo_redirigido(client):
    resp = client.get("/buzon/nuevo")
    assert resp.status_code in (302, 403)


def test_empleado_envia_mensaje(client, usuario_factory):
    from buzon.models import MensajeBuzon
    u = usuario_factory(rol="disenador")
    client.force_login(u)
    resp = client.post("/buzon/nuevo", {
        "tipo": "sugerencia",
        "asunto": "Mejorar el filtro de Proyectos",
        "cuerpo": "Sería útil filtrar por cliente y por estado al mismo tiempo.",
        "prioridad": "5",
    })
    assert resp.status_code == 302
    msg = MensajeBuzon.objects.get(autor=u)
    assert msg.asunto.startswith("Mejorar")
    assert msg.tipo == "sugerencia"
    assert msg.estado == "nuevo"


def test_problema_se_pasa_por_el_colador(client, usuario_factory):
    """Reportes de tipo 'problema' tienen el cuerpo saneado por El Colador
    (paths absolutos, API keys, etc., quedan redactados)."""
    from buzon.models import MensajeBuzon
    u = usuario_factory(rol="contador")
    client.force_login(u)
    cuerpo = "Error en /opt/el-despacho/.env con key sk-ant-test-abcdefghijklmnopqrstuvwxyz01234567"
    client.post("/buzon/nuevo", {"tipo": "problema", "asunto": "Bug", "cuerpo": cuerpo, "prioridad": "7"})
    msg = MensajeBuzon.objects.get(autor=u)
    assert "/opt/el-despacho/.env" not in msg.cuerpo
    assert "sk-ant-test-" not in msg.cuerpo
    assert "REDACTED" in msg.cuerpo


def test_mios_solo_ve_los_propios(client, usuario_factory):
    """Pre-S2b.2: URL unificada es /buzon/. Legacy /buzon/mios/ redirige."""
    from buzon.models import MensajeBuzon
    u1 = usuario_factory(rol="disenador")
    u2 = usuario_factory(rol="disenador")
    MensajeBuzon.objects.create(autor=u1, tipo="otro", asunto="A1", cuerpo="x"*20)
    MensajeBuzon.objects.create(autor=u2, tipo="otro", asunto="A2", cuerpo="y"*20)
    client.force_login(u1)
    resp = client.get("/buzon/")
    assert resp.status_code == 200
    assert b"A1" in resp.content
    assert b"A2" not in resp.content
    # URL vieja redirige a la nueva.
    resp_legacy = client.get("/buzon/mios/")
    assert resp_legacy.status_code == 302


def test_detalle_ajeno_404(client, usuario_factory):
    """Pre-S2b.2: detalle unificado en /buzon/<id>/."""
    from buzon.models import MensajeBuzon
    u1 = usuario_factory(rol="disenador")
    u2 = usuario_factory(rol="disenador")
    m = MensajeBuzon.objects.create(autor=u2, tipo="otro", asunto="A", cuerpo="z"*20)
    client.force_login(u1)
    resp = client.get(f"/buzon/{m.pk}/")
    assert resp.status_code == 404


def test_prioridad_orden_descendente(client, usuario_factory):
    """Con ?orden=prioridad ordena por prioridad desc y luego fecha desc.

    C1 S-LC-Feedback-V6: el default del listado cambió a 'fecha', por eso el
    orden por prioridad se pide explícitamente.
    """
    from buzon.models import MensajeBuzon
    u = usuario_factory(rol="super_admin")
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="baja", cuerpo="x"*20, prioridad=1)
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="urgente", cuerpo="y"*20, prioridad=9)
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="media", cuerpo="z"*20, prioridad=5)
    client.force_login(u)
    resp = client.get("/buzon/?orden=prioridad")
    assert resp.status_code == 200
    body = resp.content.decode()
    # urgente (9) debe aparecer antes que media (5) antes que baja (1).
    assert body.index("urgente") < body.index("media") < body.index("baja")


def test_buzon_default_orden_fecha(client, usuario_factory):
    """C1: sin ?orden, el listado ordena por fecha (lo más reciente arriba)."""
    from buzon.models import MensajeBuzon
    u = usuario_factory(rol="super_admin")
    viejo = MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="viejo-msg", cuerpo="x"*20, prioridad=9)
    nuevo = MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="nuevo-msg", cuerpo="y"*20, prioridad=1)
    # `creado_en` es auto_now_add; el segundo creado es más reciente.
    client.force_login(u)
    body = client.get("/buzon/").content.decode()
    # El más reciente (nuevo-msg, prioridad baja) va arriba pese a su prioridad.
    assert body.index("nuevo-msg") < body.index("viejo-msg")


def test_buzon_preserva_filtro_al_volver(client, usuario_factory):
    """C1: las filas llevan ?volver= y el detalle reconstruye el back link."""
    from buzon.models import MensajeBuzon
    u = usuario_factory(rol="super_admin")
    m = MensajeBuzon.objects.create(autor=u, tipo="problema", asunto="con-filtro", cuerpo="z"*20)
    client.force_login(u)
    # Listado filtrado por estado=nuevo.
    body = client.get("/buzon/?estado=nuevo").content.decode()
    assert "volver=" in body
    # El detalle abierto con volver reconstruye el back_url con el filtro.
    detalle = client.get(f"/buzon/{m.pk}/?volver=estado%3Dnuevo").content.decode()
    assert "/buzon/?estado=nuevo" in detalle


def test_accion_masiva_marca_leidos(client, usuario_factory):
    """S-LC-Feedback-V3: POST /buzon/masivo con accion=estado_leido marca varios mensajes."""
    from buzon.models import MensajeBuzon
    admin = usuario_factory(rol="super_admin")
    u = usuario_factory(rol="disenador")
    m1 = MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="A", cuerpo="x"*20, estado="nuevo")
    m2 = MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="B", cuerpo="y"*20, estado="nuevo")
    client.force_login(admin)
    resp = client.post("/buzon/masivo", {
        "ids": [str(m1.pk), str(m2.pk)],
        "accion": "estado_leido",
    })
    assert resp.status_code == 302
    m1.refresh_from_db()
    m2.refresh_from_db()
    assert m1.estado == "leido"
    assert m2.estado == "leido"


def test_accion_masiva_eliminar_solo_super_admin(client, usuario_factory):
    """Eliminación masiva sólo permitida a super_admin/dueno."""
    from buzon.models import MensajeBuzon
    contador = usuario_factory(rol="contador")
    u = usuario_factory(rol="disenador")
    m = MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="X", cuerpo="x"*20)
    client.force_login(contador)
    resp = client.post("/buzon/masivo", {"ids": [str(m.pk)], "accion": "eliminar"})
    assert resp.status_code == 403
    # Mensaje debe seguir existiendo.
    assert MensajeBuzon.objects.filter(pk=m.pk).exists()


def test_orden_fecha_invierte_prioridad(client, usuario_factory):
    """S-LC-Feedback-V2: ?orden=fecha ordena cronológico descendente (más reciente arriba)
    independientemente de la prioridad."""
    from buzon.models import MensajeBuzon
    u = usuario_factory(rol="super_admin")
    # Creo en orden cronológico inverso al de prioridad.
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="urgente", cuerpo="y"*20, prioridad=9)
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="media", cuerpo="z"*20, prioridad=5)
    MensajeBuzon.objects.create(autor=u, tipo="otro", asunto="baja", cuerpo="x"*20, prioridad=1)
    client.force_login(u)
    resp = client.get("/buzon/?orden=fecha")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Más reciente (baja, creada al final) debe estar arriba.
    assert body.index("baja") < body.index("media") < body.index("urgente")
    # El segmented control debe marcar "Por fecha" activo.
    assert "Por fecha" in body
