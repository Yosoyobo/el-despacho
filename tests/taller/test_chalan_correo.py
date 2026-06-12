"""S-LC-Feedback-V6 Bloque 7A/7B: plantillas nuevas, auto-envío y ejecutor
enviar_correo del Chalán. Mockea El Cartero — nunca pega a SMTP real."""

from unittest import mock

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


class _ResultadoOK:
    ok = True
    error = ""


class _ResultadoFalla:
    ok = False
    error = "smtp caído"


@pytest.fixture()
def cliente_con_email(cliente_factory, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin, razon_social="Optimist")
    cli.email_contacto = "hola@optimist.mx"
    cli.nombre_contacto = "Juan"
    cli.save()
    return admin, cli


# ── 7A: plantillas nuevas ────────────────────────────────────────────────────

def test_plantillas_pago_y_bienvenida_existen():
    from ajustes.plantillas_correo_default import PLANTILLAS_DEFAULT, SLUGS_PLANTILLA
    assert "pago" in PLANTILLAS_DEFAULT and "bienvenida" in PLANTILLAS_DEFAULT
    assert "pago" in SLUGS_PLANTILLA and "bienvenida" in SLUGS_PLANTILLA


def test_render_plantilla_pago():
    from ajustes.models.plantilla_correo import PlantillaCorreo
    asunto, html = PlantillaCorreo.obtener("pago").render({
        "cliente": "Juan", "monto": "1,000.00", "moneda": "MXN",
        "referencia": "ING-2026-0001", "metodo": "Transferencia", "fecha": "12/06/2026",
    })
    assert "ING-2026-0001" in asunto
    assert "1,000.00" in html and "Juan" in html


# ── 7A: auto-envío (apagado por default, signals best-effort) ────────────────

def test_auto_bienvenida_apagada_no_envia(cliente_con_email):
    """El flag arranca apagado: crear cliente NO debe llamar a El Cartero."""
    admin, _ = cliente_con_email
    from apps.la_cartera.models import Cliente
    with mock.patch("lib.cartero.enviar", return_value=_ResultadoOK()) as m:
        from lib.correos_auto import enviar_bienvenida
        cli = Cliente.objects.create(razon_social="Nuevo", email_contacto="x@y.mx",
                                     creado_por=admin)
        assert enviar_bienvenida(cli) is False
        m.assert_not_called()


def test_auto_bienvenida_activada_envia(cliente_con_email):
    admin, _ = cliente_con_email
    from apps.la_cartera.models import Cliente

    from ajustes.models.cartero import ConfiguracionCorreo
    cfg = ConfiguracionCorreo.obtener()
    cfg.auto_bienvenida = True
    cfg.save()
    cli = Cliente.objects.create(razon_social="Activo", email_contacto="a@b.mx",
                                 nombre_contacto="Ana", creado_por=admin)
    with mock.patch("lib.cartero.enviar", return_value=_ResultadoOK()) as m:
        from lib.correos_auto import enviar_bienvenida
        assert enviar_bienvenida(cli) is True
        m.assert_called_once()
        assert m.call_args.kwargs["destinatario"] == "a@b.mx"


def test_auto_pago_nunca_lanza(cliente_con_email):
    """Best-effort: si El Cartero truena, el helper regresa False sin levantar."""
    admin, cli = cliente_con_email
    from apps.tesoreria.models import Ingreso

    from ajustes.models.cartero import ConfiguracionCorreo
    cfg = ConfiguracionCorreo.obtener()
    cfg.auto_pago = True
    cfg.save()
    from datetime import date
    ing = Ingreso.objects.create(monto="500.00", descripcion="Pago", cliente=cli,
                                 fecha=date.today(), creado_por=admin)
    with mock.patch("lib.cartero.enviar", side_effect=RuntimeError("boom")):
        from lib.correos_auto import enviar_confirmacion_pago
        assert enviar_confirmacion_pago(ing) is False  # no levanta


# ── 7B: ejecutor enviar_correo (gating + sanear + solo email registrado) ─────

def _accion(payload):
    class _A:
        entidad_tipo = None
        entidad_id = None
    a = _A()
    a.payload = payload
    return a


def test_ejecutor_enviar_correo_gating(usuario_factory, cliente_con_email):
    """Sin permiso (comunicacion, enviar_correo) el ejecutor rechaza."""
    from apps.el_dictado.ejecutores.avanzados import enviar_correo
    _, cli = cliente_con_email
    disenador = usuario_factory(rol="disenador")
    with pytest.raises(ValueError, match="permiso"):
        enviar_correo(_accion({"cliente_slug": cli.slug, "tipo_plantilla": "generico",
                               "mensaje": "hola"}), disenador)


def test_ejecutor_enviar_correo_ok(cliente_con_email):
    from apps.el_dictado.ejecutores.avanzados import enviar_correo

    from cuentas.models.permiso_usuario import PermisoUsuario
    admin, cli = cliente_con_email
    PermisoUsuario.objects.get_or_create(usuario=admin, modulo="comunicacion",
                                         permiso="enviar_correo", defaults={"activo": True})
    accion = _accion({"cliente_slug": cli.slug, "tipo_plantilla": "generico",
                      "mensaje": "Su pedido está listo <script>alert(1)</script>"})
    with mock.patch("lib.cartero.enviar", return_value=_ResultadoOK()) as m:
        enviar_correo(accion, admin)
    m.assert_called_once()
    assert m.call_args.kwargs["destinatario"] == "hola@optimist.mx"
    # sanear_contexto removió el script del mensaje.
    assert "<script>" not in m.call_args.kwargs["html"]
    assert accion.entidad_tipo == "correo"


def test_ejecutor_sin_email_registrado_falla(usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores.avanzados import enviar_correo

    from cuentas.models.permiso_usuario import PermisoUsuario
    admin = usuario_factory(rol="super_admin")
    PermisoUsuario.objects.get_or_create(usuario=admin, modulo="comunicacion",
                                         permiso="enviar_correo", defaults={"activo": True})
    cli = cliente_factory(creado_por=admin)  # sin email
    with pytest.raises(ValueError, match="email"):
        enviar_correo(_accion({"cliente_slug": cli.slug, "tipo_plantilla": "generico",
                               "mensaje": "x"}), admin)


def test_ejecutor_cartero_caido_falla_legible(cliente_con_email):
    from apps.el_dictado.ejecutores.avanzados import enviar_correo

    from cuentas.models.permiso_usuario import PermisoUsuario
    admin, cli = cliente_con_email
    PermisoUsuario.objects.get_or_create(usuario=admin, modulo="comunicacion",
                                         permiso="enviar_correo", defaults={"activo": True})
    with mock.patch("lib.cartero.enviar", return_value=_ResultadoFalla()), \
         pytest.raises(ValueError, match="Cartero"):
        enviar_correo(_accion({"cliente_slug": cli.slug,
                               "tipo_plantilla": "generico", "mensaje": "x"}), admin)


def test_catalogo_dictado_incluye_enviar_correo(usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario
    from lib.dictado_catalogo import comandos_para
    admin = usuario_factory(rol="super_admin")
    PermisoUsuario.objects.get_or_create(usuario=admin, modulo="comunicacion",
                                         permiso="enviar_correo", defaults={"activo": True})
    tipos = {c["tipo"] for c in comandos_para(admin)}
    assert "enviar_correo" in tipos
    disenador = usuario_factory(rol="disenador")
    assert "enviar_correo" not in {c["tipo"] for c in comandos_para(disenador)}
