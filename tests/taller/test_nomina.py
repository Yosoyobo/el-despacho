"""S-Checador-V2 — La Nómina interna quincenal de sueldo fijo.

Decisiones de Oscar (2026-09-29) que estas pruebas fijan:
- sueldo fijo por quincena; las horas del Checador sólo informan;
- el sueldo que aplica es el vigente el ÚLTIMO día de la quincena (regla
  elegida para el aumento/alta a media quincena), con aviso;
- un aumento no toca quincenas cerradas (el recibo guarda su copia);
- préstamos: el saldo baja sólo al cerrar;
- reembolsos: entran como percepción y se saldan en Tesorería al marcar pagado,
  sin duplicar si ya se pagaron por otro lado;
- nadie ve el recibo de otro sin `nomina.ver`;
- sin sueldos capturados, El Análisis cuesta EXACTAMENTE igual que antes.
"""

from __future__ import annotations

import datetime
import importlib
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]

D = Decimal
Q1_JUN = datetime.date(2026, 6, 1)   # lunes: 1ª quincena de junio 2026
Q2_JUN = datetime.date(2026, 6, 16)
Q1_JUL = datetime.date(2026, 7, 1)
HOY_DESPUES = datetime.date(2026, 9, 29)


def _aw(fecha, h, m=0):
    from django.utils import timezone
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(h, m)))


@pytest.fixture
def svc():
    from apps.checador import nomina
    return nomina


@pytest.fixture
def jefe(usuario_factory):
    return usuario_factory(rol="super_admin")


@pytest.fixture
def ana(usuario_factory):
    return usuario_factory(rol="disenador", email="ana@ejemplo.com")


@pytest.fixture
def beto(usuario_factory):
    return usuario_factory(rol="disenador", email="beto@ejemplo.com")


def _sueldo(usuario, monto, desde, en_nomina=True):
    from apps.checador.models import SueldoPersona
    return SueldoPersona.objects.create(usuario=usuario, sueldo_quincenal=D(monto),
                                        vigente_desde=desde, en_nomina=en_nomina)


def _periodo(svc, fecha, actor=None):
    return svc.abrir_periodo(fecha, actor=actor)


def _calcular(svc, periodo, actor=None):
    return svc.calcular_periodo(periodo, actor=actor, hoy=HOY_DESPUES)


def _recibo(periodo, usuario):
    from apps.checador.models import ReciboNomina
    return ReciboNomina.objects.get(periodo=periodo, usuario=usuario)


def _egreso_por_reembolsar(usuario, monto="250.00", creado_por=None):
    from apps.tesoreria.models import CentroDeCosto, Egreso
    centro = CentroDeCosto.objects.filter(activo=True).first()
    return Egreso.objects.create(
        monto=D(monto), fecha=Q1_JUN, descripcion="Taxi a cliente", centro_de_costo=centro,
        estado_pago="por_reembolsar", metodo="efectivo_personal", pagado_por=usuario,
        creado_por=creado_por or usuario,
    )


# ── Quincenas y sueldo vigente ────────────────────────────────────────────


class TestQuincenasYSueldo:
    def test_quincena_de_bordes(self):
        from apps.checador.models.nomina import quincena_de
        assert quincena_de(datetime.date(2026, 2, 15)) == (datetime.date(2026, 2, 1), datetime.date(2026, 2, 15))
        assert quincena_de(datetime.date(2026, 2, 16)) == (datetime.date(2026, 2, 16), datetime.date(2026, 2, 28))
        assert quincena_de(datetime.date(2028, 2, 20))[1] == datetime.date(2028, 2, 29)
        assert quincena_de(datetime.date(2026, 7, 31))[1] == datetime.date(2026, 7, 31)

    def test_vigente_es_el_de_mayor_fecha_que_no_se_pasa(self, svc, ana):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        _sueldo(ana, "9000", datetime.date(2026, 6, 16))
        assert svc.sueldo_vigente(ana, datetime.date(2026, 6, 15)).sueldo_quincenal == D("8000")
        assert svc.sueldo_vigente(ana, datetime.date(2026, 6, 16)).sueldo_quincenal == D("9000")
        assert svc.sueldo_vigente(ana, datetime.date(2025, 12, 31)) is None

    def test_abrir_normaliza_a_la_quincena(self, svc, jefe):
        p = _periodo(svc, datetime.date(2026, 6, 20), jefe)
        assert (p.fecha_inicio, p.fecha_fin) == (Q2_JUN, datetime.date(2026, 6, 30))
        assert _periodo(svc, datetime.date(2026, 6, 29)).pk == p.pk  # no duplica
        assert p.etiqueta == "2ª quincena de junio 2026"


# ── Cálculo ───────────────────────────────────────────────────────────────


class TestCalculo:
    def test_solo_quien_tiene_sueldo_y_copia_el_sueldo(self, svc, ana, beto):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        p.refresh_from_db()
        assert p.estado == "calculado"
        assert list(p.recibos.values_list("usuario_id", flat=True)) == [ana.pk]
        r = _recibo(p, ana)
        assert r.sueldo_aplicado == D("8000") and r.neto == D("8000")

    def test_horas_solo_informan(self, svc, ana):
        """Con el horario global L–V 9–18: 11 días, 99 h. Dos jornadas, una con
        retardo; el resto de los días laborales ya pasados son faltas. El sueldo
        no se mueve."""
        from apps.checador.models import Jornada
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        Jornada.objects.create(usuario=ana, fecha=Q1_JUN, entrada_en=_aw(Q1_JUN, 9),
                               salida_en=_aw(Q1_JUN, 18), estado="cerrada")
        d2 = Q1_JUN + datetime.timedelta(days=1)
        Jornada.objects.create(usuario=ana, fecha=d2, entrada_en=_aw(d2, 9, 40),
                               salida_en=_aw(d2, 17, 40), estado="cerrada", retardo_min=25)
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        r = _recibo(p, ana)
        assert r.dias_laborales == 11
        assert r.horas_esperadas == D("99.00")
        assert r.horas_trabajadas == D("17.00")
        assert (r.retardos, r.minutos_retardo) == (1, 25)
        assert r.faltas == 9
        assert r.sueldo_aplicado == D("8000") and r.neto == D("8000")

    def test_hoy_y_futuro_no_son_falta(self, svc, ana):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        svc.calcular_periodo(p, hoy=Q1_JUN + datetime.timedelta(days=2))  # miércoles 3
        assert _recibo(p, ana).faltas == 2

    def test_aumento_a_media_quincena_aplica_el_del_ultimo_dia_y_avisa(self, svc, ana):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        _sueldo(ana, "9000", datetime.date(2026, 6, 10))
        p = _periodo(svc, Q1_JUN)
        avisos = _calcular(svc, p)
        r = _recibo(p, ana)
        assert r.sueldo_aplicado == D("9000")
        assert r.sueldo_anterior == D("8000")
        assert r.cambio_sueldo_en_periodo is True
        assert any("cambió el 10/06" in a for a in avisos)

    def test_alta_a_media_quincena_entra_a_su_primera_nomina(self, svc, ana):
        _sueldo(ana, "6000", datetime.date(2026, 6, 8))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        r = _recibo(p, ana)
        assert r.sueldo_aplicado == D("6000") and r.sueldo_anterior is None
        assert r.cambio_sueldo_en_periodo is True

    def test_baja_saca_de_la_nomina(self, svc, ana):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        _sueldo(ana, "0", datetime.date(2026, 6, 1), en_nomina=False)
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        assert not p.recibos.exists()

    def test_aumento_despues_de_cerrar_no_toca_el_recibo(self, svc, ana):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        svc.cerrar_periodo(p)
        _sueldo(ana, "12000", datetime.date(2026, 6, 5))
        with pytest.raises(ValueError, match="cerrada"):
            _calcular(svc, p)
        assert _recibo(p, ana).sueldo_aplicado == D("8000")

    def test_recalcular_respeta_lo_capturado_a_mano(self, svc, ana):
        from apps.checador.models import ConceptoRecibo
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        r = _recibo(p, ana)
        ConceptoRecibo.objects.create(recibo=r, tipo="percepcion", clase="bono", descripcion="Comisión", monto=D("500"))
        _sueldo(ana, "8500", datetime.date(2026, 6, 1))
        _calcular(svc, p)
        r.refresh_from_db()
        assert r.sueldo_aplicado == D("8500")
        assert r.conceptos.filter(clase="bono").count() == 1
        assert r.neto == D("9000")

    def test_cerrar_exige_calcular_y_no_se_cierra_dos_veces(self, svc, ana):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        with pytest.raises(ValueError, match="calcula"):
            svc.cerrar_periodo(p)
        _calcular(svc, p)
        svc.cerrar_periodo(p)
        with pytest.raises(ValueError, match="ya está cerrada"):
            svc.cerrar_periodo(p)

    def test_neto_negativo_no_cierra(self, svc, ana):
        from apps.checador.models import ConceptoRecibo
        _sueldo(ana, "1000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        ConceptoRecibo.objects.create(recibo=_recibo(p, ana), tipo="deduccion", clase="deduccion",
                                      descripcion="Descuento", monto=D("1500"))
        with pytest.raises(ValueError, match="negativo"):
            svc.cerrar_periodo(p)
        p.refresh_from_db()
        assert p.estado == "calculado"


# ── Préstamos ─────────────────────────────────────────────────────────────


class TestPrestamos:
    def _prestamo(self, usuario, monto="1000", cuota="400"):
        from apps.checador.models import PrestamoNomina
        return PrestamoNomina.objects.create(usuario=usuario, monto=D(monto), cuota=D(cuota),
                                             saldo=D(monto), fecha=datetime.date(2026, 5, 20))

    def test_el_saldo_baja_solo_al_cerrar_y_se_salda(self, svc, ana):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        pr = self._prestamo(ana)
        esperado = [("400.00", "600.00"), ("400.00", "200.00"), ("200.00", "0.00")]
        for fecha, (abono, saldo) in zip((Q1_JUN, Q2_JUN, Q1_JUL), esperado, strict=True):
            p = _periodo(svc, fecha)
            _calcular(svc, p)
            c = _recibo(p, ana).conceptos.get(prestamo=pr)
            assert c.monto == D(abono) and c.tipo == "deduccion"
            pr.refresh_from_db()
            assert pr.saldo == D(saldo) + D(abono)  # antes de cerrar no baja
            svc.cerrar_periodo(p)
            pr.refresh_from_db()
            assert pr.saldo == D(saldo)
        assert pr.saldado
        p = _periodo(svc, datetime.date(2026, 7, 16))
        _calcular(svc, p)
        assert not _recibo(p, ana).conceptos.filter(prestamo=pr).exists()

    def test_dos_quincenas_abiertas_no_se_pasan_del_saldo(self, svc, ana):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        pr = self._prestamo(ana, monto="600", cuota="400")
        p1, p2 = _periodo(svc, Q1_JUN), _periodo(svc, Q2_JUN)
        _calcular(svc, p1)
        _calcular(svc, p2)
        assert _recibo(p1, ana).conceptos.get(prestamo=pr).monto == D("400")
        assert _recibo(p2, ana).conceptos.get(prestamo=pr).monto == D("200")

    def test_cuota_por_numero_de_quincenas(self, ana):
        from apps.checador.forms_nomina import PrestamoForm
        f = PrestamoForm(data={"usuario": ana.pk, "concepto": "Adelanto", "monto": "1000",
                               "fecha": "2026-06-01", "quincenas": "3", "notas": ""})
        assert f.is_valid(), f.errors
        pr = f.save()
        assert pr.cuota == D("333.34") and pr.saldo == D("1000")

    def test_abono_editado_a_mano_se_respeta_al_recalcular(self, svc, ana):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        pr = self._prestamo(ana)
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        c = _recibo(p, ana).conceptos.get(prestamo=pr)
        c.monto, c.automatico = D("150"), False
        c.save()
        _calcular(svc, p)
        assert _recibo(p, ana).conceptos.get(prestamo=pr).monto == D("150")


# ── Reembolsos ────────────────────────────────────────────────────────────


class TestReembolsos:
    def test_entra_como_percepcion_y_se_salda_al_pagar(self, svc, ana, jefe):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        eg = _egreso_por_reembolsar(ana)
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        r = _recibo(p, ana)
        c = r.conceptos.get(egreso=eg)
        assert (c.tipo, c.clase, c.monto) == ("percepcion", "reembolso", D("250.00"))
        assert r.neto == D("8250.00")
        svc.cerrar_periodo(p)
        eg.refresh_from_db()
        assert eg.estado_pago == "por_reembolsar"  # cerrar NO toca Tesorería
        avisos = svc.marcar_pagado(r, fecha=datetime.date(2026, 6, 16), actor=jefe)
        assert avisos == []
        eg.refresh_from_db()
        r.refresh_from_db()
        assert eg.estado_pago == "pagado" and eg.pagado_en == datetime.date(2026, 6, 16)
        assert r.estado == "pagado" and r.pagado_en == datetime.date(2026, 6, 16) and r.pagado_por == jefe

    def test_no_se_propone_en_dos_quincenas(self, svc, ana):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        eg = _egreso_por_reembolsar(ana)
        p1, p2 = _periodo(svc, Q1_JUN), _periodo(svc, Q2_JUN)
        _calcular(svc, p1)
        svc.cerrar_periodo(p1)  # cerrado pero sin pagar: el egreso sigue pendiente
        _calcular(svc, p2)
        assert _recibo(p1, ana).conceptos.filter(egreso=eg).exists()
        assert not _recibo(p2, ana).conceptos.filter(egreso=eg).exists()

    def test_pagado_por_otro_lado_antes_de_cerrar_se_saca(self, svc, ana, jefe):
        from apps.tesoreria.services import reembolsar_egreso
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        eg = _egreso_por_reembolsar(ana)
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        reembolsar_egreso(eg, metodo="transferencia", banco_o_caja="banco", actor=jefe)
        assert len(svc.reembolsos_pagados_aparte(_recibo(p, ana))) == 1
        avisos = svc.cerrar_periodo(p)
        r = _recibo(p, ana)
        assert not r.conceptos.filter(clase="reembolso").exists()
        assert r.neto == D("8000")
        assert any("ya se pagó" in a for a in avisos)

    def test_pagado_por_otro_lado_despues_de_cerrar_avisa_y_no_duplica(self, svc, ana, jefe, monkeypatch):
        from apps.tesoreria import services as teso
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        eg = _egreso_por_reembolsar(ana)
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        svc.cerrar_periodo(p)
        teso.reembolsar_egreso(eg, metodo="transferencia", banco_o_caja="banco",
                               fecha=datetime.date(2026, 6, 14), actor=jefe)
        llamadas = []
        real = teso.reembolsar_egreso
        monkeypatch.setattr(teso, "reembolsar_egreso", lambda *a, **k: llamadas.append(a) or real(*a, **k))
        avisos = svc.marcar_pagado(_recibo(p, ana), fecha=datetime.date(2026, 6, 16), actor=jefe)
        assert llamadas == []
        assert any("ya se había pagado" in a for a in avisos)
        eg.refresh_from_db()
        assert eg.pagado_en == datetime.date(2026, 6, 14)
        assert _recibo(p, ana).estado == "pagado"

    def test_quitado_a_mano_no_regresa_al_recalcular(self, client, svc, ana, jefe):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        eg = _egreso_por_reembolsar(ana)
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        r = _recibo(p, ana)
        client.force_login(jefe)
        datos = _post_recibo(client, r)
        c = r.conceptos.get(egreso=eg)
        idx = next(k.split("-")[1] for k, v in datos.items() if k.endswith("-id") and str(v) == str(c.pk))
        datos[f"conceptos-{idx}-DELETE"] = "on"
        resp = client.post(f"/nomina/recibo/{r.pk}/", datos)
        assert resp.status_code == 302, resp.content[:500]
        r.refresh_from_db()
        assert f"egreso:{eg.pk}" in r.quitados and r.neto == D("8000")
        _calcular(svc, p)
        assert not _recibo(p, ana).conceptos.filter(egreso=eg).exists()

    def test_pagar_exige_cerrar(self, svc, ana, jefe):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        with pytest.raises(ValueError, match="Cierra"):
            svc.marcar_pagado(_recibo(p, ana), fecha=datetime.date(2026, 6, 16), actor=jefe)


def _post_recibo(client, recibo) -> dict:
    """Arma el POST del formulario del recibo tal como lo pinta la pantalla."""
    import re
    html = client.get(f"/nomina/recibo/{recibo.pk}/").content.decode()
    datos = {}
    for m in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*>', html):
        tag = m.group(0)
        if 'type="checkbox"' in tag and "checked" not in tag:
            continue
        v = re.search(r'value="([^"]*)"', tag)
        datos[m.group(1)] = v.group(1) if v else ""
    for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S):
        sel = re.search(r'<option value="([^"]*)"[^>]*selected', m.group(2))
        datos[m.group(1)] = sel.group(1) if sel else ""
    for m in re.finditer(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', html, re.S):
        datos[m.group(1)] = m.group(2).strip()
    import html as _h
    return {k: _h.unescape(v) for k, v in datos.items()}


# ── Pantallas y candados ──────────────────────────────────────────────────


class TestPantallas:
    def test_flujo_completo_por_pantalla(self, client, svc, ana, jefe):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        client.force_login(jefe)
        assert client.get("/nomina/").status_code == 200
        resp = client.post("/nomina/abrir", {"fecha": "2026-06-03"})
        from apps.checador.models import PeriodoNomina
        p = PeriodoNomina.objects.get(fecha_inicio=Q1_JUN)
        assert resp.status_code == 302 and resp["Location"].endswith(f"/nomina/quincena/{p.pk}/")
        client.post(f"/nomina/quincena/{p.pk}/calcular")
        r = _recibo(p, ana)
        datos = _post_recibo(client, r)
        extra = next(k.split("-")[1] for k in datos if k.endswith("-descripcion") and not datos[k])
        datos.update({f"conceptos-{extra}-clase": "bono", f"conceptos-{extra}-descripcion": "Comisión junio",
                      f"conceptos-{extra}-monto": "700", f"conceptos-{extra}-tipo": ""})
        assert client.post(f"/nomina/recibo/{r.pk}/", datos).status_code == 302
        r.refresh_from_db()
        assert r.neto == D("8700") and r.conceptos.get(clase="bono").tipo == "percepcion"
        detalle = client.get(f"/nomina/quincena/{p.pk}/").content.decode()
        assert "data-tabla-movil" in detalle and "$8,700" in detalle
        client.post(f"/nomina/quincena/{p.pk}/cerrar")
        p.refresh_from_db()
        assert p.cerrado
        # Cerrado es inmutable también por pantalla.
        datos[f"conceptos-{extra}-monto"] = "1"
        client.post(f"/nomina/recibo/{r.pk}/", datos)
        r.refresh_from_db()
        assert r.neto == D("8700")
        resp = client.post(f"/nomina/recibo/{r.pk}/pagar", {"fecha": "2026-06-16", "metodo": "transferencia",
                                                            "banco_o_caja": "banco"})
        assert resp.status_code == 302
        r.refresh_from_db()
        assert r.pagado

    def test_edicion_pisada_avisa(self, client, svc, ana, jefe):
        from apps.checador.models import ConceptoRecibo
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        r = _recibo(p, ana)
        c = ConceptoRecibo.objects.create(recibo=r, tipo="percepcion", clase="bono", descripcion="Bono", monto=D("100"))
        client.force_login(jefe)
        datos = _post_recibo(client, r)
        ConceptoRecibo.objects.filter(pk=c.pk).update(monto=D("300"))  # otra ventana
        idx = next(k.split("-")[1] for k, v in datos.items() if k.endswith("-id") and str(v) == str(c.pk))
        datos[f"conceptos-{idx}-monto"] = "200"
        resp = client.post(f"/nomina/recibo/{r.pk}/", datos)
        assert resp.status_code == 409
        c.refresh_from_db()
        assert c.monto == D("300")

    def test_neto_negativo_no_se_guarda_por_pantalla(self, client, svc, ana, jefe):
        _sueldo(ana, "1000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        r = _recibo(p, ana)
        client.force_login(jefe)
        datos = _post_recibo(client, r)
        extra = next(k.split("-")[1] for k in datos if k.endswith("-descripcion") and not datos[k])
        datos.update({f"conceptos-{extra}-clase": "deduccion", f"conceptos-{extra}-descripcion": "Descuento",
                      f"conceptos-{extra}-monto": "2000"})
        resp = client.post(f"/nomina/recibo/{r.pk}/", datos)
        assert resp.status_code == 200 and "negativo" in resp.content.decode()
        assert not r.conceptos.exists()

    def test_csv_con_bom(self, client, svc, ana, jefe):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        client.force_login(jefe)
        resp = client.get(f"/nomina/quincena/{p.pk}/csv")
        cuerpo = resp.content.decode("utf-8")
        assert resp["Content-Type"].startswith("text/csv")
        assert cuerpo.startswith("﻿") and "Sueldo aplicado" in cuerpo.splitlines()[0]
        assert "ana@ejemplo.com" in cuerpo and "8000.00" in cuerpo

    def test_sueldos_crud(self, client, ana, jefe):
        from apps.checador.models import SueldoPersona
        client.force_login(jefe)
        assert client.get("/nomina/sueldos/").status_code == 200
        resp = client.post("/nomina/sueldos/nuevo", {"usuario": ana.pk, "sueldo_quincenal": "7500",
                                                     "vigente_desde": "2026-06-01", "en_nomina": "on", "notas": ""})
        assert resp.status_code == 302
        s = SueldoPersona.objects.get(usuario=ana)
        assert s.sueldo_quincenal == D("7500") and s.en_nomina
        dup = client.post("/nomina/sueldos/nuevo", {"usuario": ana.pk, "sueldo_quincenal": "1",
                                                    "vigente_desde": "2026-06-01", "en_nomina": "on"})
        assert dup.status_code == 200 and SueldoPersona.objects.count() == 1
        client.post(f"/nomina/sueldos/{s.pk}/borrar")
        assert not SueldoPersona.objects.exists()

    def test_prestamo_pantalla(self, client, ana, jefe):
        from apps.checador.models import PrestamoNomina
        client.force_login(jefe)
        resp = client.post("/nomina/prestamos/nuevo", {"usuario": ana.pk, "concepto": "Adelanto", "monto": "900",
                                                       "fecha": "2026-06-01", "cuota": "300", "quincenas": ""})
        pr = PrestamoNomina.objects.get(usuario=ana)
        assert resp.status_code == 302 and pr.saldo == D("900")
        assert client.get(f"/nomina/prestamos/{pr.pk}/").status_code == 200
        assert client.get("/nomina/prestamos/").status_code == 200


class TestCandados:
    def test_sin_permiso_no_entra(self, client, ana):
        client.force_login(ana)
        for url in ("/nomina/", "/nomina/sueldos/", "/nomina/prestamos/"):
            assert client.get(url).status_code == 403, url

    def test_contador_la_trae_por_default(self, client, usuario_factory):
        contador = usuario_factory(rol="contador")
        client.force_login(contador)
        assert client.get("/nomina/").status_code == 200
        assert client.get("/nomina/sueldos/").status_code == 200

    def test_ver_sin_editar_no_calcula(self, client, svc, usuario_factory):
        from cuentas.models.permiso_usuario import PermisoUsuario
        from lib.permisos import invalidar_cache_permisos
        u = usuario_factory(rol="miembro")
        PermisoUsuario.objects.create(usuario=u, modulo="nomina", permiso="ver", activo=True)
        invalidar_cache_permisos()
        p = _periodo(svc, Q1_JUN)
        client.force_login(u)
        assert client.get(f"/nomina/quincena/{p.pk}/").status_code == 200
        assert client.post(f"/nomina/quincena/{p.pk}/calcular").status_code == 403
        assert client.post(f"/nomina/quincena/{p.pk}/cerrar").status_code == 403
        assert client.get("/nomina/sueldos/").status_code == 403

    def test_mi_checador_solo_lo_mio_y_cerrado(self, client, svc, ana, beto):
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        _sueldo(beto, "9100", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        ra, rb = _recibo(p, ana), _recibo(p, beto)
        client.force_login(ana)
        # Antes de cerrar: ni el suyo.
        assert "Aún no tienes recibos" in client.get("/checador/mis-recibos/").content.decode()
        assert client.get(f"/nomina/recibo/{ra.pk}/pdf").status_code == 404
        svc.cerrar_periodo(p)
        html = client.get("/checador/mis-recibos/").content.decode()
        assert "$8,000" in html and "$9,100" not in html
        assert client.get(f"/nomina/recibo/{ra.pk}/pdf").status_code == 200
        # El de Beto: ni el PDF ni la pantalla.
        assert client.get(f"/nomina/recibo/{rb.pk}/pdf").status_code == 404
        assert client.get(f"/nomina/recibo/{rb.pk}/").status_code == 403
        client.force_login(beto)
        assert "$9,100" in client.get("/checador/mis-recibos/").content.decode()
        assert client.get(f"/nomina/recibo/{ra.pk}/pdf").status_code == 404


class TestPdf:
    def test_sin_gotenberg_sale_imprimible(self, client, svc, ana, jefe, monkeypatch):
        from lib import gotenberg
        monkeypatch.setattr(gotenberg, "disponible", lambda **k: False)
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        client.force_login(jefe)
        resp = client.get(f"/nomina/recibo/{_recibo(p, ana).pk}/pdf")
        html = resp.content.decode()
        assert resp.status_code == 200 and resp["Content-Type"].startswith("text/html")
        assert "Recibo de nómina" in html and "window.print()" in html
        assert 'href="https://devs.noko.mx"' in html and "NoKo Devs" in html

    def test_con_gotenberg_sale_pdf(self, client, svc, ana, jefe, monkeypatch):
        from lib import gotenberg
        capturado = {}
        monkeypatch.setattr(gotenberg, "disponible", lambda **k: True)
        monkeypatch.setattr(gotenberg, "html_a_pdf",
                            lambda html, pagina=None: capturado.update(html=html) or b"%PDF-1.7 prueba")
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        client.force_login(jefe)
        resp = client.get(f"/nomina/recibo/{_recibo(p, ana).pk}/pdf")
        assert resp["Content-Type"] == "application/pdf" and resp.content.startswith(b"%PDF")
        assert "$8,000.00" in capturado["html"] and "window.print()" not in capturado["html"]


# ── Costeo de El Análisis ─────────────────────────────────────────────────


def _costo_hora_viejo(usuario, cfg):
    """`mano_obra.costo_hora_de` tal como estaba ANTES de La Nómina (congelado)."""
    from ajustes.models import TarifaRol
    claves = {r.pk for r in usuario.roles_extra.all()}
    tarifas = TarifaRol.objects.filter(rol_id__in=claves, activo=True) if claves else []
    montos = [t.costo_hora for t in tarifas if t.costo_hora and t.costo_hora > 0]
    if montos:
        return max(montos)
    return cfg.tarifa_hora_default or D("0.00")


class TestCosteo:
    def _escenario(self, usuario_factory, proyecto_factory):
        from apps.checador.models import Jornada, SesionProyecto

        from ajustes.models import ConfiguracionAnalisis, TarifaRol
        from cuentas.models.rol import Rol
        cfg = ConfiguracionAnalisis.obtener()
        cfg.tarifa_hora_default = D("80.00")
        cfg.save()
        rol = Rol.objects.create(clave="impresor_prueba", nombre="Impresor", permisos={})
        TarifaRol.objects.create(rol=rol, costo_hora=D("120.00"))
        con_rol = usuario_factory(rol="miembro")
        con_rol.roles_extra.add(rol)
        sin_rol = usuario_factory(rol="miembro")
        proy = proyecto_factory()
        for u, dia in ((con_rol, Q1_JUN), (sin_rol, Q1_JUN + datetime.timedelta(days=1))):
            SesionProyecto.objects.create(usuario=u, proyecto=proy, inicio=_aw(dia, 10), fin=_aw(dia, 13),
                                          duracion_min=180, estado="cerrada")
            Jornada.objects.create(usuario=u, fecha=dia, entrada_en=_aw(dia, 9), salida_en=_aw(dia, 18),
                                   estado="cerrada")
        return cfg, con_rol, sin_rol, proy

    def test_sin_sueldos_da_exactamente_lo_mismo(self, usuario_factory, proyecto_factory, monkeypatch):
        from apps.los_proyectos import mano_obra
        cfg, con_rol, sin_rol, proy = self._escenario(usuario_factory, proyecto_factory)
        for u in (con_rol, sin_rol):
            assert mano_obra.costo_hora_de(u, cfg, Q1_JUN) == _costo_hora_viejo(u, cfg)
        nuevo = mano_obra.horas_por_proyecto(Q1_JUN, datetime.date(2026, 6, 15))
        monkeypatch.setattr(mano_obra, "costo_hora_de", lambda u, c=None, f=None: _costo_hora_viejo(u, c))
        viejo = mano_obra.horas_por_proyecto(Q1_JUN, datetime.date(2026, 6, 15))
        assert nuevo == viejo
        assert nuevo[proy.pk]["costo"] == pytest.approx(3 * 120 + 3 * 80)

    def test_con_sueldo_cuesta_sueldo_entre_horas_de_su_horario(self, usuario_factory, proyecto_factory, svc):
        from apps.los_proyectos import mano_obra
        cfg, con_rol, sin_rol, proy = self._escenario(usuario_factory, proyecto_factory)
        _sueldo(sin_rol, "9900", datetime.date(2026, 1, 1))  # 99 h en la 1ª de junio → $100/h
        assert svc.horas_laborales_quincena(sin_rol, Q1_JUN) == D("99")
        assert mano_obra.costo_hora_de(sin_rol, cfg, Q1_JUN) == D("100.00")
        assert mano_obra.costo_hora_de(con_rol, cfg, Q1_JUN) == D("120.00")  # sin sueldo: su rol
        r = mano_obra.horas_por_proyecto(Q1_JUN, datetime.date(2026, 6, 15))
        assert r[proy.pk]["costo"] == pytest.approx(3 * 120 + 3 * 100)

    def test_baja_o_sin_horario_cae_a_la_tarifa(self, usuario_factory, proyecto_factory, svc):
        from apps.checador.models import HorarioLaboral
        from apps.los_proyectos import mano_obra
        cfg, _, sin_rol, _ = self._escenario(usuario_factory, proyecto_factory)
        _sueldo(sin_rol, "9900", datetime.date(2026, 1, 1))
        _sueldo(sin_rol, "0", datetime.date(2026, 6, 1), en_nomina=False)
        assert mano_obra.costo_hora_de(sin_rol, cfg, Q1_JUN) == D("80.00")
        HorarioLaboral.objects.all().delete()
        _sueldo(sin_rol, "9900", datetime.date(2026, 6, 16))
        assert mano_obra.costo_hora_de(sin_rol, cfg, Q2_JUN) == D("80.00")


# ── Permiso sembrado «como hoy» ───────────────────────────────────────────


class TestSiembra:
    def test_catalogo_y_defaults(self):
        from cuentas.context_processors import MODULOS_VISIBLES
        from lib.permisos_defaults import CATALOGO_PERMISOS, DEFAULTS_POR_ROL
        todo = ["ver", "editar", "cerrar", "pagar", "sueldos"]
        assert CATALOGO_PERMISOS["nomina"] == todo
        for rol in ("super_admin", "dueno", "contador"):
            assert DEFAULTS_POR_ROL[rol]["nomina"] == todo
        assert "nomina" not in DEFAULTS_POR_ROL["disenador"]
        assert "nomina" in MODULOS_VISIBLES

    def test_como_hoy(self, usuario_factory):
        from django.apps import apps as django_apps

        from cuentas.models.permiso_usuario import PermisoUsuario
        from cuentas.models.rol import Rol
        mig = importlib.import_module("apps.checador.migrations.0010_seed_permisos_nomina")
        rol_dueno, _ = Rol.objects.get_or_create(clave="dueno", defaults={"nombre": "Dueño", "permisos": {}})
        rol_conta, _ = Rol.objects.get_or_create(clave="contador", defaults={"nombre": "Contador", "permisos": {}})
        rol_conta.permisos = {**(rol_conta.permisos or {}), "tesoreria": ["ver"]}
        rol_conta.save()
        sa = usuario_factory(rol="super_admin")
        dueno_con_teso = usuario_factory(rol="miembro")
        dueno_con_teso.roles_extra.add(rol_dueno)
        conta_por_rol = usuario_factory(rol="miembro")        # tesorería por el JSON del rol
        conta_por_rol.roles_extra.add(rol_conta)
        conta_sin_teso = usuario_factory(rol="miembro")        # alguien le apagó Tesorería
        conta_sin_teso.roles_extra.add(rol_conta)
        disenador = usuario_factory(rol="disenador")
        PermisoUsuario.objects.filter(modulo="nomina").delete()
        PermisoUsuario.objects.filter(modulo="tesoreria").delete()
        PermisoUsuario.objects.create(usuario=dueno_con_teso, modulo="tesoreria", permiso="ver", activo=True)
        PermisoUsuario.objects.create(usuario=conta_sin_teso, modulo="tesoreria", permiso="ver", activo=False)
        mig.sembrar(django_apps, None)

        def filas(u):
            return dict(PermisoUsuario.objects.filter(usuario=u, modulo="nomina").values_list("permiso", "activo"))
        todo = {a: True for a in mig.TODO}
        assert filas(sa) == todo
        assert filas(dueno_con_teso) == todo
        assert filas(conta_por_rol) == todo
        # El JSON del rol ya trae nómina: la fila APAGADA impide que se la dé.
        assert filas(conta_sin_teso) == {a: False for a in mig.TODO}
        assert filas(disenador) == {}
        rol_conta.refresh_from_db()
        assert set(rol_conta.permisos["nomina"]) == set(mig.TODO)
        from lib.permisos import invalidar_cache_permisos, puede_ver_nomina
        invalidar_cache_permisos()
        assert puede_ver_nomina(conta_por_rol) and not puede_ver_nomina(conta_sin_teso)
        assert not puede_ver_nomina(disenador)


# ── El Chalán / MCP / Portavoz ────────────────────────────────────────────


class TestChalan:
    def test_nomina_quincena_gateada(self, svc, ana, jefe):
        import capacidades
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        r = capacidades.ejecutar("nomina_quincena", {"fecha": "2026-06-10"}, jefe)
        assert r["quincena"] == "1ª quincena de junio 2026" and r["neto_total"] == 8000.0
        assert r["personas"][0]["neto"] == 8000.0
        assert capacidades.ejecutar("nomina_quincena", {}, ana)["error"] == "sin_permiso"
        assert "nomina_quincena" not in {c.nombre for c in capacidades.listar(ana)}

    def test_mi_recibo_solo_lo_mio_y_cerrado(self, svc, ana, beto):
        import capacidades
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        _sueldo(beto, "9100", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        assert capacidades.ejecutar("mi_recibo", {}, ana)["recibo"] is None
        svc.cerrar_periodo(p)
        assert capacidades.ejecutar("mi_recibo", {}, ana)["neto"] == 8000.0
        assert capacidades.ejecutar("mi_recibo", {}, beto)["neto"] == 9100.0
        assert "mi_recibo" in {c.nombre for c in capacidades.listar(ana)}

    def test_catalogo_declara_que_no_se_opera_por_chat(self):
        from apps.el_dictado.prompt import SYSTEM_PROMPT

        from lib.dictado_catalogo import COMANDOS_DICTADO, COMANDOS_PROHIBIDOS, CONSULTAS_CHAT
        nombres = " ".join(c["nombre"] for c in CONSULTAS_CHAT)
        assert "nomina_quincena" in nombres and "mi_recibo" in nombres
        assert any("NO se pide por chat" in c["que"] and "Nómina" in c["nombre"] for c in CONSULTAS_CHAT)
        assert "operar_nomina" in {c["tipo"] for c in COMANDOS_PROHIBIDOS}
        assert not any("nomina" in c["tipo"] for c in COMANDOS_DICTADO)
        assert "nomina_quincena" in SYSTEM_PROMPT and "mi_recibo" in SYSTEM_PROMPT

    def test_mcp(self, monkeypatch, svc, ana, jefe):
        from cuentas.models.permiso_usuario import PermisoUsuario
        from mcp_despacho import herramientas
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        svc.cerrar_periodo(p)
        monkeypatch.setenv(herramientas.ENV_USUARIO, jefe.email)
        assert herramientas.nomina_quincena("2026-06-01")["recibos"] == 1
        PermisoUsuario.objects.create(usuario=ana, modulo="mcp", permiso="usar", activo=True)
        monkeypatch.setenv(herramientas.ENV_USUARIO, ana.email)
        assert herramientas.mi_recibo()["neto"] == 8000.0
        with pytest.raises(herramientas.ErrorAccesoMCP):
            herramientas.nomina_quincena()

    def test_eventos_tipados(self, svc, ana, jefe, monkeypatch):
        from typing import get_args

        from django.db import transaction

        from lib import portavoz
        from lib.portavoz_eventos import EventoTipo
        assert {"nomina.periodo_cerrado", "nomina.recibo_pagado"} <= set(get_args(EventoTipo))
        emitidos = []
        monkeypatch.setattr(transaction, "on_commit", lambda fn, using=None, robust=False: fn())
        monkeypatch.setattr(portavoz, "emitir", lambda ev: emitidos.append(ev))
        _sueldo(ana, "8000", datetime.date(2026, 1, 1))
        p = _periodo(svc, Q1_JUN)
        _calcular(svc, p)
        svc.cerrar_periodo(p)
        svc.marcar_pagado(_recibo(p, ana), fecha=datetime.date(2026, 6, 16), actor=jefe)
        tipos = [e.tipo for e in emitidos]
        assert "nomina.periodo_cerrado" in tipos and "nomina.recibo_pagado" in tipos
