"""Oscar 2026-10-14: `limpiar_egresos_automaticos` anula SÓLO los egresos que el
sistema generaba solo (signal retirado) y respeta todo lo que una persona registró.

Datos mixtos: automáticos vs. manuales/pagados/editados/ligados. Los manuales NO
se tocan; los automáticos se ANULAN (no se borran) con su asiento reverso.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    """Bug E de CLAUDE.md §14: el asiento de Contaduría va en `on_commit`."""
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture
def centro(db):
    from apps.tesoreria.models import CentroDeCosto
    return CentroDeCosto.objects.get(slug="insumos-de-proyecto")


@pytest.fixture
def otro_centro(db):
    from apps.tesoreria.models import CentroDeCosto
    return CentroDeCosto.objects.exclude(slug="insumos-de-proyecto").first()


def _auto(p, centro, monto="100.00", **kw):
    """Un egreso EXACTAMENTE como lo creaba el signal retirado."""
    from apps.tesoreria.models import Egreso
    datos = dict(
        monto=Decimal(monto), fecha=date.today(),
        descripcion=f"Proyecto {p.codigo} · Simil Cuero · × 10 pz",
        proveedor_nombre="Gasto de proyecto", centro_de_costo=centro, proyecto=p,
        estado_pago="pendiente", metodo="transferencia", origen="proyecto",
    )
    datos.update(kw)
    return Egreso.objects.create(**datos)


def _correr(*args):
    out = StringIO()
    call_command("limpiar_egresos_automaticos", *args, stdout=out)
    return out.getvalue()


def _estado(e):
    e.refresh_from_db()
    return e.anulado


def test_simulacro_es_el_default_y_no_escribe_nada(proyecto_factory, centro):
    p = proyecto_factory(estado="en_proceso_produccion")
    a = _auto(p, centro, "80.00")
    b = _auto(p, centro, "20.00")
    salida = _correr()
    assert "SIMULACRO" in salida
    assert "Se anularían 2 egreso(s) por $100.00" in salida
    assert p.codigo in salida
    assert _estado(a) is False and _estado(b) is False
    # ni con --dry-run explícito ni con --detalle
    _correr("--dry-run", "--detalle")
    assert _estado(a) is False


def test_aplicar_anula_automaticos_y_conserva_manuales(
        proyecto_factory, usuario_factory, centro, otro_centro):
    from apps.tesoreria.models import Egreso
    u = usuario_factory(rol="super_admin")
    p = proyecto_factory(estado="en_proceso_produccion")
    auto1 = _auto(p, centro, "435.40")
    auto2 = _auto(p, centro, "1096.50")
    # — todo lo que una persona hizo —
    manual_form = Egreso.objects.create(  # «Nuevo egreso» a mano
        monto=Decimal("500"), fecha=date.today(), descripcion="Papelería",
        centro_de_costo=otro_centro, proyecto=p, creado_por=u, origen="manual",
        estado_pago="pagado")
    registrado_modal = _auto(p, centro, "300", creado_por=u, estado_pago="pagado",
                             pagado_por=u, pagado_en=date.today())
    pendiente_con_autor = _auto(p, centro, "310", creado_por=u)  # «Registrar» de Tesorería
    liquidado = _auto(p, centro, "320", estado_pago="pagado", pagado_en=date.today())
    por_reembolsar = _auto(p, centro, "330", estado_pago="por_reembolsar")
    cfdi = _auto(p, centro, "340", origen="cfdi")
    descripcion_a_mano = _auto(p, centro, "350", descripcion="Anticipo Zittro")
    con_comprobante = _auto(p, centro, "360", tiene_comprobante=True, drive_file_id="x")
    otro_proyecto_manual = Egreso.objects.create(
        monto=Decimal("1"), fecha=date.today(), descripcion="x", centro_de_costo=centro,
        proyecto=None, origen="manual")

    salida = _correr("--aplicar")
    assert "2 egreso(s) anulados" in salida

    # automáticos → anulados (NO borrados), con motivo
    for e in (auto1, auto2):
        e.refresh_from_db()
        assert e.anulado is True and "limpieza" in e.motivo_anulacion
    # manuales / tocados → intactos
    for e in (manual_form, registrado_modal, pendiente_con_autor, liquidado,
              por_reembolsar, cfdi, descripcion_a_mano, con_comprobante,
              otro_proyecto_manual):
        assert _estado(e) is False, e.descripcion
    assert Egreso.objects.count() == 11  # nada se borró


def test_editado_despues_de_crearse_se_protege(proyecto_factory, centro):
    from apps.tesoreria.models import Egreso
    p = proyecto_factory(estado="en_proceso_produccion")
    e = _auto(p, centro)
    Egreso.objects.filter(pk=e.pk).update(
        actualizado_en=timezone.now() + timedelta(hours=2))  # alguien lo editó
    _correr("--aplicar")
    assert _estado(e) is False


def test_ligado_a_cfdi_se_protege(proyecto_factory, centro):
    """Se evalúa sobre TODAS las relaciones inversas: lo ligado a otro módulo se queda."""
    from apps.facturacion.models.cfdi_entrante import CfdiEntrante
    from apps.los_proyectos import limpieza_egresos as limp
    p = proyecto_factory(estado="en_proceso_produccion")
    e = _auto(p, centro)
    assert limp.evaluar(e).candidato  # sin ligas: candidato
    CfdiEntrante.objects.create(uuid="UUID-LIMPIEZA-1", egreso=e, estado="ligado")
    ev = limp.evaluar(e)
    assert not ev.candidato and any("cfdi_entrante" in r for r in ev.razones)
    _correr("--aplicar")
    assert _estado(e) is False


def test_con_asiento_de_pago_se_protege(proyecto_factory, centro):
    from apps.contaduria.services import crear_asiento
    from apps.los_proyectos import limpieza_egresos as limp
    p = proyecto_factory(estado="en_proceso_produccion")
    e = _auto(p, centro)
    assert limp.evaluar(e).candidato
    crear_asiento(
        descripcion="pago", fecha=date.today(), origen="manual",
        referencia_externa=f"tesoreria.egreso.pago:{e.pk}",
        partidas=[{"cuenta": _cuenta("cxp"), "cargo": Decimal("1")},
                  {"cuenta": _cuenta("banco"), "abono": Decimal("1")}])
    ev = limp.evaluar(e)
    assert not ev.candidato and any("asientos ajenos" in r for r in ev.razones)


def _cuenta(slot):
    from apps.contaduria.services import cuenta_por_slot
    return cuenta_por_slot(slot)


def test_anular_genera_asiento_reverso_y_no_deja_huerfanos(proyecto_factory, centro):
    """Se ANULA (no se borra) justo para que el libro cuadre: el hook de Contaduría
    crea el reverso del `auto_egreso` original."""
    from apps.contaduria.models import Asiento
    p = proyecto_factory(estado="en_proceso_produccion")
    e = _auto(p, centro, "435.40")
    orig = Asiento.objects.filter(referencia_externa=f"tesoreria.egreso:{e.pk}",
                                  origen="auto_egreso")
    assert orig.count() == 1, "el signal de Contaduría debe haber creado el asiento"
    _correr("--aplicar")
    rev = Asiento.objects.filter(referencia_externa=f"tesoreria.egreso.anulacion:{e.pk}",
                                 origen="auto_anulacion_egreso")
    assert rev.count() == 1
    assert rev.first().total == orig.first().total  # cuadra: lo mismo, invertido


def test_lo_anulado_vuelve_a_la_seccion_amarilla(proyecto_factory, centro):
    """Tras la limpieza, lo que faltaba pagar reaparece como pago pendiente."""
    from apps.el_catalogo.models import CategoriaServicio, Proveedor, Servicio
    from apps.los_proyectos import gastos
    from apps.los_proyectos.models import ProyectoProducto
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Limpieza Test")
    serv = Servicio.objects.create(nombre="Simil Cuero", categoria=cat,
                                   precio_base=Decimal("100"), costo=Decimal("40"), activo=True)
    prov = Proveedor.objects.create(razon_social="Oscar Serigrafía", activo=True)
    p = proyecto_factory(estado="en_proceso_produccion")
    pp = ProyectoProducto.objects.create(
        proyecto=p, servicio=serv, cantidad=2, precio_unitario=Decimal("100"),
        costo_unitario=Decimal("40"), incluir_en_calculo=True, proveedor=prov)
    e = _auto(p, centro, "80.00", proveedor=prov)
    pp.egreso = e
    pp.save(update_fields=["egreso"])
    assert gastos.pagos_pendientes_de(p) != []  # pendiente: aún no «pagado»
    _correr("--aplicar")
    assert [float(u["monto"]) for u in gastos.pagos_pendientes_de(p)] == [80.0]
    assert gastos.pendientes_de(p) != []  # y vuelve a «no registrado»
    assert not p.egresos.filter(anulado=False).exists()


def test_excluir_y_proyecto_acotan(proyecto_factory, centro):
    p1 = proyecto_factory(estado="en_proceso_produccion")
    p2 = proyecto_factory(estado="en_proceso_produccion")
    a = _auto(p1, centro, "10")
    b = _auto(p1, centro, "20")
    c = _auto(p2, centro, "30")
    _correr("--aplicar", "--proyecto", p1.codigo, "--excluir", b.codigo)
    assert _estado(a) is True
    assert _estado(b) is False   # librado con --excluir
    assert _estado(c) is False   # otro proyecto


def test_es_idempotente(proyecto_factory, centro):
    p = proyecto_factory(estado="en_proceso_produccion")
    _auto(p, centro)
    assert "1 egreso(s) anulados" in _correr("--aplicar")
    assert "No hay egresos automáticos" in _correr("--aplicar")


def test_el_script_de_ops_existe_y_es_simulacro_por_default():
    from pathlib import Path
    ruta = Path(__file__).resolve().parents[2] / "ops" / "nuc" / "limpiar-egresos-automaticos.sh"
    texto = ruta.read_text()
    assert "limpiar_egresos_automaticos" in texto
    # el simulacro es el default: sólo se aplica con --aplicar explícito + confirmación
    assert "--aplicar" in texto and "ANULAR" in texto
