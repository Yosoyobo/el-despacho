"""Oscar 2026-10-14: «Registrar pago» de un proveedor permite pagar sólo una PARTE:
casilla por concepto (varios pedidos en una tienda) y «¿cuánto pagas ahora?»
(todo / anticipo 50% / otro monto). Lo que queda pendiente sigue como pago
pendiente; nunca se marca pagado todo el grupo ni se duplican egresos.

Caso de Oscar (captura): Plastitienda — Números Rojos 435.40, A-Frame · Impresión
1,096.50, Caja de propinas 181.22 = 1,713.12 + IVA 274.10 = 1,987.22.
"""

from __future__ import annotations

import random
from datetime import date
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

D = Decimal


# ── repartir_proporcional (función pura) ─────────────────────────────────────

def test_reparto_proporcional_suma_exacta_y_no_excede_lo_que_falta():
    from apps.los_proyectos.gastos import repartir_proporcional
    rnd = random.Random(2026)
    for _ in range(500):
        n = rnd.randint(1, 6)
        restantes = [D(rnd.randint(1, 500000)) / 100 for _ in range(n)]
        total = sum(restantes)
        monto = (D(rnd.randint(1, int(total * 100) - 1 if total > D("0.01") else 1)) / 100
                 if total > D("0.01") else total)
        monto = min(monto, total)
        partes = repartir_proporcional(monto, restantes)
        assert sum(partes) == monto, (monto, restantes, partes)
        assert all(0 <= p <= r for p, r in zip(partes, restantes, strict=True)), (monto, restantes, partes)


def test_reparto_caso_de_oscar_y_extremos():
    from apps.los_proyectos.gastos import repartir_proporcional
    r = [D("435.40"), D("1096.50"), D("181.22")]
    assert repartir_proporcional(D("856.56"), r) == [D("217.70"), D("548.25"), D("90.61")]
    assert repartir_proporcional(D("1713.12"), r) == r          # cubre todo → cada quien lo suyo
    assert repartir_proporcional(D("0.01"), r) == [D("0.00"), D("0.01"), D("0.00")]  # el mayor resto
    assert repartir_proporcional(D("100.00"), [D("100.00")]) == [D("100.00")]


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture
def entorno(client, usuario_factory, proyecto_factory):
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    from apps.los_proyectos.models import ProyectoProducto
    from apps.tesoreria.models import CentroDeCosto

    CentroDeCosto.objects.get_or_create(slug="insumos-de-proyecto",
                                        defaults={"nombre": "Insumos de proyecto"})
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    cat = CategoriaServicio.objects.create(nombre="Plastitienda cat", color="#465fff", orden=1)
    prov = Proveedor.objects.create(razon_social="Plastitienda", activo=True)
    p = proyecto_factory(estado="en_proceso_produccion")
    pps = []
    for nombre, costo in (("Números Rojos", "435.40"), ("A-Frame · Impresión", "1096.50"),
                          ("Caja de propinas", "181.22")):
        serv = Servicio.objects.create(nombre=nombre, categoria=cat, precio_base=1000,
                                       costo=1, unidad="pieza", activo=True)
        pps.append(ProyectoProducto.objects.create(
            proyecto=p, servicio=serv, cantidad=1, proveedor=prov,
            precio_unitario=D("1000"), costo_unitario=D(costo), incluir_en_calculo=True))
    return {"p": p, "prov": prov, "pps": pps, "admin": admin}


def _pagar(client, e, **extra):
    from apps.los_proyectos import gastos
    visto = gastos.grupo_pago_de(e["p"], e["prov"].pk)
    datos = {"fecha": date.today().isoformat(), "proveedor": str(e["prov"].pk),
             "metodo": "transferencia", "estado_pago": "pagado"}
    if visto is not None and "pendiente_visto" not in extra:
        datos["pendiente_visto"] = f"{visto['monto']:.2f}"
    datos.update(extra)
    return client.post(f"/proyectos/{e['p'].pk}/pago-proveedor/{e['prov'].pk}/registrar",
                       datos, HTTP_HX_REQUEST="true")


def _pendiente(e) -> Decimal:
    from apps.los_proyectos import gastos
    return sum((u["monto"] for u in gastos.pagos_pendientes_de(e["p"])), D("0.00"))


# ── Anticipo 50% ─────────────────────────────────────────────────────────────

def test_anticipo_50_crea_un_egreso_y_deja_el_resto_pendiente(client, entorno):
    from apps.los_proyectos import gastos
    from apps.los_proyectos.models import PagoGasto
    from apps.tesoreria.models import Egreso
    e = entorno
    assert _pendiente(e) == D("1713.12")
    resp = _pagar(client, e, modo="anticipo")
    assert resp.status_code == 204
    eg = Egreso.objects.get()
    assert eg.monto == D("856.56") and eg.estado_pago == "pagado" and eg.origen == "proyecto"
    assert eg.creado_por_id == e["admin"].pk and "Anticipo 50%" in eg.descripcion
    # abonos repartidos en proporción y sumando EXACTO el egreso
    assert sorted(a.monto for a in PagoGasto.objects.all()) == [D("90.61"), D("217.70"), D("548.25")]
    # nada se marca pagado; el resto sigue pendiente, por concepto y por proveedor
    assert _pendiente(e) == D("856.56")
    assert len(gastos.grupos_pagos_pendientes_de(e["p"])) == 1
    for pp in e["pps"]:
        pp.refresh_from_db()
        assert pp.egreso_id is None
    pend = {u["label"]: u for u in gastos.pagos_pendientes_de(e["p"])}
    assert len(pend) == 3 and all(u["pagado_parcial"] > 0 for u in pend.values())


def test_segundo_pago_liquida_sin_duplicar_egresos(client, entorno):
    from apps.los_proyectos import gastos
    from apps.tesoreria.models import Egreso
    e = entorno
    _pagar(client, e, modo="anticipo")
    resp = _pagar(client, e, modo="total")
    assert resp.status_code == 204
    egresos = list(Egreso.objects.order_by("pk"))
    assert [x.monto for x in egresos] == [D("856.56"), D("856.56")]
    assert sum(x.monto for x in egresos) == D("1713.12")      # exacto: ni de más ni de menos
    assert "Liquidación" in egresos[1].descripcion
    assert _pendiente(e) == D("0.00") and gastos.pagos_pendientes_de(e["p"]) == []
    for pp in e["pps"]:
        pp.refresh_from_db()
        assert pp.egreso_id == egresos[1].pk                   # el pago que lo termina lo liga


def test_otro_monto_con_iva_guarda_la_base(client, entorno):
    from apps.tesoreria.models import Egreso
    e = entorno
    _pagar(client, e, modo="otro", monto_otro="500.00", incluye_iva="1")
    assert Egreso.objects.get().monto == D("431.03")           # 500 ÷ 1.16
    assert _pendiente(e) == D("1713.12") - D("431.03")


def test_otro_monto_sin_iva_y_monto_total_equivale_a_pagar_todo(client, entorno):
    from apps.tesoreria.models import Egreso
    e = entorno
    _pagar(client, e, modo="otro", monto_otro="700.00")        # sin IVA marcado
    assert Egreso.objects.get().monto == D("700.00")
    # escribir como «otro monto» todo lo que falta (con IVA) = pago completo
    faltan_con_iva = (D("1013.12") * D("1.16")).quantize(D("0.01"))
    _pagar(client, e, modo="otro", monto_otro=str(faltan_con_iva), incluye_iva="1")
    assert _pendiente(e) == D("0.00")
    assert sum(x.monto for x in Egreso.objects.all()) == D("1713.12")


# ── Casilla por concepto ─────────────────────────────────────────────────────

def test_pagar_solo_algunos_conceptos(client, entorno):
    from apps.los_proyectos import gastos
    from apps.tesoreria.models import Egreso
    e = entorno
    n_rojos, a_frame, caja = e["pps"]
    sel = [f"producto:{n_rojos.pk}", f"producto:{a_frame.pk}"]
    resp = client.post(
        f"/proyectos/{e['p'].pk}/pago-proveedor/{e['prov'].pk}/registrar",
        {"fecha": date.today().isoformat(), "proveedor": str(e["prov"].pk),
         "metodo": "transferencia", "estado_pago": "pagado", "modo": "total",
         "unidades": sel}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert Egreso.objects.get().monto == D("1531.90")          # 435.40 + 1096.50
    n_rojos.refresh_from_db(), a_frame.refresh_from_db(), caja.refresh_from_db()
    assert n_rojos.egreso_id and a_frame.egreso_id and caja.egreso_id is None
    pend = gastos.pagos_pendientes_de(e["p"])
    assert [u["monto"] for u in pend] == [D("181.22")]          # la caja sigue pendiente
    assert len(gastos.grupos_pagos_pendientes_de(e["p"])) == 1


def test_conceptos_elegidos_mas_anticipo(client, entorno):
    from apps.tesoreria.models import Egreso
    e = entorno
    n_rojos, a_frame, _caja = e["pps"]
    _pagar(client, e, modo="anticipo",
           unidades=[f"producto:{n_rojos.pk}", f"producto:{a_frame.pk}"])
    assert Egreso.objects.get().monto == D("765.95")           # 50% de 1,531.90
    assert _pendiente(e) == D("1713.12") - D("765.95")


def test_sin_conceptos_marcados_se_rechaza(client, entorno):
    from apps.tesoreria.models import Egreso
    e = entorno
    resp = _pagar(client, e, modo="total", unidades=["producto:99999"])
    assert resp.status_code == 200 and "al menos un concepto" in resp.content.decode()
    assert Egreso.objects.count() == 0


# ── Validaciones y anti-duplicados ───────────────────────────────────────────

def test_monto_mayor_a_lo_pendiente_se_rechaza(client, entorno):
    from apps.tesoreria.models import Egreso
    e = entorno
    resp = _pagar(client, e, modo="otro", monto_otro="5000")
    assert resp.status_code == 200 and "excede" in resp.content.decode()
    resp = _pagar(client, e, modo="otro", monto_otro="")
    assert resp.status_code == 200
    resp = _pagar(client, e, modo="otro", monto_otro="0")
    assert resp.status_code == 200
    assert Egreso.objects.count() == 0


def test_doble_clic_no_paga_dos_veces_el_anticipo(client, entorno):
    """Mismo `pendiente_visto` en dos envíos: el segundo ya no coincide → se rechaza."""
    from apps.tesoreria.models import Egreso
    e = entorno
    visto = "1713.12"
    assert _pagar(client, e, modo="anticipo", pendiente_visto=visto).status_code == 204
    resp = _pagar(client, e, modo="anticipo", pendiente_visto=visto)
    assert resp.status_code == 200 and "cambió" in resp.content.decode()
    assert Egreso.objects.count() == 1


def test_anular_el_egreso_del_abono_devuelve_el_pendiente(client, entorno):
    from apps.tesoreria.models import Egreso
    from apps.tesoreria.services import anular_egreso
    e = entorno
    _pagar(client, e, modo="anticipo")
    assert _pendiente(e) == D("856.56")
    anular_egreso(Egreso.objects.get(), e["admin"], "error")
    assert _pendiente(e) == D("1713.12")


def test_concepto_que_ya_es_cuenta_por_pagar_no_se_parte(client, entorno):
    """Un concepto registrado como «pendiente» (CxP) se liquida completo."""
    from apps.los_proyectos import gastos
    from apps.tesoreria.models import Egreso
    e = entorno
    gastos.registrar_egreso(e["p"], "producto", e["pps"][0].pk, actor=e["admin"])  # CxP pendiente
    resp = _pagar(client, e, modo="anticipo")
    assert resp.status_code == 200 and "cuenta por pagar" in resp.content.decode()
    assert Egreso.objects.count() == 1                         # sólo la CxP; nada nuevo
    # desmarcándolo, el anticipo procede sobre los otros dos
    otros = [f"producto:{e['pps'][1].pk}", f"producto:{e['pps'][2].pk}"]
    assert _pagar(client, e, modo="anticipo", unidades=otros).status_code == 204
    # y pagar TODO liquida la CxP en lugar de duplicarla
    assert _pagar(client, e, modo="total").status_code == 204
    pend = [x for x in Egreso.objects.all() if x.estado_pago == "pendiente"]
    assert pend == []


def test_registrar_gasto_suelto_tras_abonos_solo_registra_lo_que_falta(client, entorno):
    from apps.los_proyectos import gastos
    e = entorno
    _pagar(client, e, modo="anticipo")
    eg = gastos.registrar_egreso(e["p"], "producto", e["pps"][1].pk, actor=e["admin"])
    assert eg.monto == D("1096.50") - D("548.25")


def test_tesoreria_gastos_no_registrados_usa_lo_pendiente(client, entorno):
    from apps.los_proyectos import gastos
    e = entorno
    _pagar(client, e, modo="anticipo")
    assert gastos.conteo_no_registrados()["total"] == D("856.56")


# ── Compatibilidad y pantalla ────────────────────────────────────────────────

def test_post_antiguo_sin_campos_nuevos_paga_todo(client, entorno):
    """El formulario de antes (sin modo/unidades/token) sigue pagando todo."""
    from apps.tesoreria.models import Egreso
    e = entorno
    resp = client.post(f"/proyectos/{e['p'].pk}/pago-proveedor/{e['prov'].pk}/registrar", {
        "fecha": date.today().isoformat(), "proveedor": str(e["prov"].pk),
        "metodo": "transferencia", "estado_pago": "pagado"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert Egreso.objects.get().monto == D("1713.12") and _pendiente(e) == D("0.00")


def test_modal_ofrece_casillas_y_modos(client, entorno):
    e = entorno
    html = client.get(f"/proyectos/{e['p'].pk}/pago-proveedor/{e['prov'].pk}/registrar",
                      HTTP_HX_REQUEST="true").content.decode()
    assert html.count('name="unidades"') == 3                   # una casilla por concepto
    assert 'name="modo"' in html and "Anticipo 50%" in html and "Otro monto" in html
    assert 'name="monto_otro"' in html and 'name="pendiente_visto" value="1713.12"' in html
    # el modal de UN solo gasto no cambia
    pp = e["pps"][0]
    solo = client.get(f"/proyectos/{e['p'].pk}/gasto/producto/{pp.pk}/registrar-modal",
                      HTTP_HX_REQUEST="true").content.decode()
    assert 'name="unidades"' not in solo and 'name="modo"' not in solo


def test_la_caja_amarilla_muestra_lo_ya_pagado(client, entorno):
    e = entorno
    _pagar(client, e, modo="anticipo")
    html = client.get(f"/proyectos/{e['p'].pk}/").content.decode()
    assert "ya se pagó" in html
