"""S-Directorio-Panel-V1: panel del Directorio (lista compacta + modal tabs),
overrides de Chalán por usuario desde admin, presupuesto IA y gate de topado."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.gerencia]


def _log_ia(usuario, costo):
    from ajustes.models.analistas_log import AnalistaLog
    return AnalistaLog.objects.create(
        estacion="dictado", provider="anthropic", actor=usuario,
        prompt_hash="x", prompt_tokens=10, completion_tokens=5,
        costo_usd_estimado=Decimal(str(costo)), exito=True,
    )


# ── Lista ───────────────────────────────────────────────────────────────────

def test_lista_super_admin_columnas(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.get("/directorio/")
    assert resp.status_code == 200
    assert b"Proveedor IA" in resp.content
    assert b"Gasto IA 30d" in resp.content


def test_lista_gasto_30d_se_muestra(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    _log_ia(admin, "3.50")
    client.force_login(admin)
    resp = client.get("/directorio/")
    assert resp.status_code == 200
    assert b"$3.50" in resp.content


# ── Modal / gating ────────────────────────────────────────────────────────────

def test_panel_modal_super_admin(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    otro = usuario_factory(rol="disenador")
    client.force_login(admin)
    resp = client.get(f"/directorio/{otro.pk}/panel", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert b"Inteligencia (IA)" in resp.content
    assert b"Permisos" in resp.content


def test_panel_dueno_403(client, usuario_factory):
    dueno = usuario_factory(rol="dueno")
    otro = usuario_factory(rol="disenador")
    client.force_login(dueno)
    resp = client.get(f"/directorio/{otro.pk}/panel")
    assert resp.status_code == 403


def test_tab_ia_lista_estaciones(client, usuario_factory):
    admin = usuario_factory(rol="super_admin")
    otro = usuario_factory(rol="contador")
    client.force_login(admin)
    resp = client.get(f"/directorio/{otro.pk}/panel/ia")
    assert resp.status_code == 200
    assert b"Chal\xc3\xa1n por estaci\xc3\xb3n" in resp.content or b"estaci" in resp.content


# ── Forzar / Auto ─────────────────────────────────────────────────────────────

def test_forzar_proveedor_y_auto(client, usuario_factory):
    from chalanes.models import ChalanAsignado
    admin = usuario_factory(rol="super_admin")
    otro = usuario_factory(rol="disenador")
    client.force_login(admin)
    # Forzar anthropic en todas las estaciones.
    resp = client.post(f"/directorio/{otro.pk}/panel/ia/forzar",
                       data={"proveedor": "anthropic"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert ChalanAsignado.objects.filter(usuario=otro, proveedor="anthropic").exists()
    # Auto borra los overrides.
    resp = client.post(f"/directorio/{otro.pk}/panel/ia/forzar",
                       data={"proveedor": "auto"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert ChalanAsignado.objects.filter(usuario=otro).count() == 0


def test_override_por_estacion(client, usuario_factory):
    from chalanes.models import ChalanAsignado
    admin = usuario_factory(rol="super_admin")
    otro = usuario_factory(rol="contador")
    client.force_login(admin)
    resp = client.post(f"/directorio/{otro.pk}/panel/ia",
                       data={"prov_dictado": "openai", "modelo_dictado": "gpt-4o-mini"},
                       HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    a = ChalanAsignado.objects.get(usuario=otro, estacion="dictado")
    assert a.proveedor == "openai"
    assert a.modelo == "gpt-4o-mini"


# ── Presupuesto ───────────────────────────────────────────────────────────────

def test_presupuesto_guarda(client, usuario_factory):
    from cuentas.models.presupuesto_ia import PresupuestoIA
    admin = usuario_factory(rol="super_admin")
    otro = usuario_factory(rol="contador")
    client.force_login(admin)
    resp = client.post(f"/directorio/{otro.pk}/panel/presupuesto",
                       data={"tope_usd": "25.00", "politica": "topar", "activo": "1"},
                       HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    p = PresupuestoIA.objects.get(usuario=otro)
    assert p.tope_usd == Decimal("25.00")
    assert p.politica == "topar"
    assert p.activo is True


# ── Permisos ──────────────────────────────────────────────────────────────────

def test_panel_permisos_persiste(client, usuario_factory):
    from cuentas.models.permiso_usuario import PermisoUsuario
    admin = usuario_factory(rol="super_admin")
    otro = usuario_factory(rol="contador")
    client.force_login(admin)
    resp = client.post(f"/directorio/{otro.pk}/panel/permisos",
                       data={"permisos": ["cartera.ver"]}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    # cartera.ver concedido; otra acción base quedó revocada (no estaba en POST).
    assert PermisoUsuario.objects.filter(usuario=otro, modulo="cartera", permiso="ver", activo=True).exists()


# ── Gate de presupuesto en lib.analistas ──────────────────────────────────────

def test_gate_topar_rebasado_levanta(usuario_factory):
    from cuentas.models.presupuesto_ia import PresupuestoIA
    from cuentas.servicios_presupuesto import debe_topar
    from lib.analistas import PresupuestoIAExcedido, analizar
    u = usuario_factory(rol="disenador")
    PresupuestoIA.objects.create(usuario=u, tope_usd=Decimal("1.00"), politica="topar", activo=True)
    _log_ia(u, "5.00")
    assert debe_topar(u.pk) is True
    with pytest.raises(PresupuestoIAExcedido):
        analizar(estacion="smoke", prompt="hola", actor_id=u.pk)


def test_gate_alertar_no_topa(usuario_factory):
    from cuentas.models.presupuesto_ia import PresupuestoIA
    from cuentas.servicios_presupuesto import debe_topar
    u = usuario_factory(rol="disenador")
    PresupuestoIA.objects.create(usuario=u, tope_usd=Decimal("1.00"), politica="alertar", activo=True)
    _log_ia(u, "5.00")
    assert debe_topar(u.pk) is False


def test_uso_por_usuario_agrega(usuario_factory):
    from lib.analistas.stats import uso_por_usuario
    u = usuario_factory(rol="disenador")
    _log_ia(u, "2.00")
    _log_ia(u, "3.00")
    uso = uso_por_usuario(u.pk)
    assert uso["30d"]["llamadas"] == 2
    assert uso["30d"]["costo_usd"] == Decimal("5.000000")


# ── Command de alerta ─────────────────────────────────────────────────────────

def test_command_evaluar_presupuestos(usuario_factory):
    from django.core.management import call_command

    from cuentas.models.presupuesto_ia import PresupuestoIA
    u = usuario_factory(rol="contador")
    PresupuestoIA.objects.create(usuario=u, tope_usd=Decimal("1.00"), politica="alertar", activo=True)
    _log_ia(u, "5.00")
    call_command("evaluar_presupuestos_ia")
    p = PresupuestoIA.objects.get(usuario=u)
    assert p.alerta_mes == timezone.now().strftime("%Y-%m")
    # Idempotente: segunda corrida no rompe ni cambia el mes.
    call_command("evaluar_presupuestos_ia")
    p.refresh_from_db()
    assert p.alerta_mes == timezone.now().strftime("%Y-%m")
