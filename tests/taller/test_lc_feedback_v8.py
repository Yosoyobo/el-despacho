"""S-LC-Feedback-V8 — impersonación, avatar, gastos (gate+IVA+modal)."""

from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


# ───────────────────────── Impersonación ─────────────────────────

def test_superadmin_impersona_y_sale(client, usuario_factory):
    sa = usuario_factory(rol="super_admin")
    target = usuario_factory(rol="miembro")
    client.force_login(sa)
    r = client.post(f"/impersonar/{target.pk}", follow=True)
    assert r.status_code == 200
    assert client.session.get("impersonate_id") == target.pk
    # Una página del Taller muestra el banner de impersonación.
    body = client.get("/").content.decode()
    assert "viendo el sistema como" in body.lower()
    # Salir limpia la sesión.
    client.post("/impersonar/salir", follow=True)
    assert client.session.get("impersonate_id") is None


def test_no_superadmin_no_impersona(client, usuario_factory):
    u = usuario_factory(rol="miembro")
    otro = usuario_factory(rol="miembro")
    client.force_login(u)
    client.post(f"/impersonar/{otro.pk}", follow=True)
    assert client.session.get("impersonate_id") is None


def test_no_impersona_a_otro_superadmin(client, usuario_factory):
    sa = usuario_factory(rol="super_admin")
    sa2 = usuario_factory(rol="super_admin")
    client.force_login(sa)
    client.post(f"/impersonar/{sa2.pk}", follow=True)
    assert client.session.get("impersonate_id") is None


# ───────────────────────── Avatar ─────────────────────────

def test_avatar_img_404_si_no_es_avatar(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    r = client.get("/perfil/avatar-img/archivo-arbitrario-123")
    assert r.status_code == 404  # no es el avatar de nadie → no se sirve


def test_avatar_guardar_sube_a_drive(client, usuario_factory, monkeypatch):
    import io

    from lib import adjuntos
    u = usuario_factory(rol="miembro")
    client.force_login(u)

    class _Res:
        ok = True
        data = {"id": "DRIVE_FILE_X"}
        error = ""

    monkeypatch.setattr(adjuntos, "subir", lambda archivo, subcarpeta=None: _Res())
    img = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
    img.name = "foto.png"
    r = client.post("/perfil/avatar/", {"avatar": img}, HTTP_HX_REQUEST="true")
    assert r.status_code in (200, 204)
    u.refresh_from_db()
    assert u.avatar_drive_id == "DRIVE_FILE_X"
    assert "DRIVE_FILE_X" in u.avatar_url


# ───────────────────────── Gastos: gate por estado + IVA ─────────────────────────

def _proyecto_con_gasto(proyecto_factory, estado):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    p = proyecto_factory(estado=estado)
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Diseño")
    serv = Servicio.objects.create(nombre="Insumo", precio_base="100.00", costo="50.00", categoria=cat)
    ProyectoProducto.objects.create(proyecto=p, servicio=serv, cantidad=2, costo_unitario="50.00", merma=1)
    return p


def test_gastos_no_se_muestran_antes_de_diseno(proyecto_factory):
    from apps.los_proyectos import gastos
    p = _proyecto_con_gasto(proyecto_factory, "por_cotizar")
    assert gastos.debe_mostrar_gastos(p) is False


def test_gastos_se_muestran_desde_diseno(proyecto_factory):
    from apps.los_proyectos import gastos
    p = _proyecto_con_gasto(proyecto_factory, "en_proceso_diseno")
    assert gastos.debe_mostrar_gastos(p) is True
    pend = gastos.pendientes_de(p)
    assert pend
    # merma incluida: costo 50 × (2 + 1) = 150.
    assert pend[0]["monto"] == Decimal("150.00")


def test_desglose_iva(proyecto_factory):
    from apps.los_proyectos import gastos
    p = _proyecto_con_gasto(proyecto_factory, "en_proceso_diseno")
    d = gastos.desglose_iva(p, gastos.pendientes_de(p))
    assert d["subtotal"] == Decimal("150.00")
    assert d["iva"] == Decimal("24.00")  # 16%
    assert d["total"] == Decimal("174.00")


# ───────────────────────── Registrar gasto: modal ─────────────────────────

def test_registrar_gasto_modal_get_y_post(client, usuario_factory, proyecto_factory):
    from apps.tesoreria.models import CentroDeCosto
    sa = usuario_factory(rol="super_admin")
    p = _proyecto_con_gasto(proyecto_factory, "en_proceso_produccion")
    centro = CentroDeCosto.objects.filter(slug="insumos-de-proyecto").first()
    assert centro is not None  # seedeado por migración
    from apps.los_proyectos.models import ProyectoProducto
    prod = ProyectoProducto.objects.filter(proyecto=p).first()
    client.force_login(sa)
    # GET muestra el modal.
    r = client.get(f"/proyectos/{p.pk}/gasto/producto/{prod.pk}/registrar-modal", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert b"Categor" in r.content
    # POST registra el egreso con quién pagó/solicitó.
    r = client.post(
        f"/proyectos/{p.pk}/gasto/producto/{prod.pk}/registrar-modal",
        {"centro_de_costo": centro.pk, "metodo": "efectivo", "estado_pago": "pagado",
         "pagado_por": sa.pk, "solicitado_por": sa.pk},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code in (200, 204)
    prod.refresh_from_db()
    assert prod.egreso is not None
    assert prod.egreso.metodo == "efectivo"
    assert prod.egreso.pagado_por_id == sa.pk
