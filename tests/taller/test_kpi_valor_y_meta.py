"""La base para juzgar KPIs: su número y cómo se lee (2026-09-29).

Hasta esta fecha la foto diaria se saltaba todo valor de texto y los KPIs de
dinero («$12,345») nunca tuvieron historia. `numero_de` es la única forma de
sacar el número; los metadatos dicen hacia dónde es mejor y si acumula.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from apps.taller_home.kpi_valor import formatear, numero_de, numero_del_resultado


@pytest.mark.parametrize("entrada, esperado", [
    (12, 12.0), (12.5, 12.5), (Decimal("3.25"), 3.25),
    ("$12,345", 12345.0), ("$-5", -5.0), ("-$5", -5.0), ("32%", 32.0),
    ("32.5 %", 32.5), ("1.5 h", 1.5), ("12 días", 12.0), ("0", 0.0),
    ("—", None), ("?", None), ("", None), (None, None), (True, None),
])
def test_numero_de(entrada, esperado):
    assert numero_de(entrada) == esperado


def test_el_numero_explicito_manda_sobre_el_valor_pintado():
    assert numero_del_resultado({"valor": "$1,000", "numero": 999.5}) == 999.5
    assert numero_del_resultado({"valor": "$1,000"}) == 1000.0
    assert numero_del_resultado(None) is None


def test_cero_es_cero_y_vacio_no_es_cero():
    # Regla «vacío hereda, 0 es cero»: un «—» no se vuelve 0.
    assert numero_de("$0") == 0.0
    assert numero_de("—") is None


@pytest.mark.parametrize("numero, formato, esperado", [
    (1234.4, "dinero", "$1,234"), (32.0, "pct", "32%"), (32.5, "pct", "32.5%"),
    (2.0, "dias", "2 días"), (1.5, "horas", "1.5 h"), (7, "numero", "7"),
    (None, "dinero", "—"),
])
def test_formatear(numero, formato, esperado):
    assert formatear(numero, formato) == esperado


def test_cada_slug_de_los_metadatos_existe_en_el_catalogo():
    from apps.taller_home import kpi_meta
    from apps.taller_home.kpis import KPIS

    slugs = {k.slug for k in KPIS}
    nombrados = set(kpi_meta._BAJA) | set(kpi_meta._NEUTRO) | set(kpi_meta._PERSONAL) \
        | set(kpi_meta._ACOTADO)
    for grupo in (*kpi_meta._ACUMULA.values(), *kpi_meta._FORMATO.values()):
        nombrados |= set(grupo)
    assert nombrados - slugs == set()


def test_los_metadatos_llegan_al_catalogo():
    from apps.taller_home.kpis import KPIS

    assert next(k for k in KPIS if k.slug == "ingresos-mes").acumula == "mes"
    assert next(k for k in KPIS if k.slug == "cxc-total").direccion == "baja"
    assert next(k for k in KPIS if k.slug == "mis-tareas-vencidas").personal is True


def test_admite_meta_segun_ambito():
    from apps.taller_home.kpis import kpi_por_slug

    ingresos = kpi_por_slug("ingresos-mes")
    assert ingresos.admite_meta("despacho")
    assert not ingresos.admite_meta("cliente")
    mis = kpi_por_slug("mis-tareas-vencidas")
    assert not mis.admite_meta("despacho")
    assert mis.admite_meta("persona")
    assert not kpi_por_slug("accesos-hoy").admite_meta("despacho")  # neutro


def test_los_slugs_del_catalogo_son_unicos():
    from apps.taller_home.kpis import KPIS

    slugs = [k.slug for k in KPIS]
    assert len(slugs) == len(set(slugs))
