"""S2b.5 — DSL acotado para KPIs custom.

Validador + ejecutor: garantizan que el DSL NUNCA permita SQL/ORM libre.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


# ── Validador ─────────────────────────────────────────────────────────


def test_validar_entidad_desconocida_rechaza():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="Entidad"):
        validar({"entidad": "secretos_militares"})


def test_validar_count_minimo_normaliza():
    from lib.kpi_dsl import validar
    n = validar({"entidad": "proyecto"})
    assert n["entidad"] == "proyecto"
    assert n["agregacion"] == "count"
    assert n["campo"] is None
    assert n["filtros"] == []
    assert n["ventana_tiempo"] == "siempre"
    assert n["alcance_usuario"] == "todos"


def test_validar_sum_requiere_campo():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="requiere `campo`"):
        validar({"entidad": "egreso", "agregacion": "sum"})


def test_validar_sum_campo_no_numerico_rechaza():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="no es agregable"):
        validar({"entidad": "tarea", "agregacion": "sum", "campo": "titulo"})


def test_validar_filtro_campo_no_filtrable_rechaza():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="no permitido"):
        validar({"entidad": "proyecto",
                 "filtros": [{"campo": "monto_cotizado", "op": "eq", "valor": 1}]})


def test_validar_filtro_op_invalida_rechaza():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError):
        validar({"entidad": "proyecto",
                 "filtros": [{"campo": "estado", "op": "regex", "valor": ".*"}]})


def test_validar_filtro_in_requiere_lista():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="lista"):
        validar({"entidad": "proyecto",
                 "filtros": [{"campo": "estado", "op": "in", "valor": "x"}]})


def test_validar_ventana_invalida_rechaza():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="Ventana"):
        validar({"entidad": "proyecto", "ventana_tiempo": "ultimos_3_anios"})


def test_validar_alcance_mio_sin_soporte_rechaza():
    from lib.kpi_dsl import ValidacionError, validar
    with pytest.raises(ValidacionError, match="alcance_usuario"):
        validar({"entidad": "cliente", "alcance_usuario": "mio"})


# ── Ejecutor ──────────────────────────────────────────────────────────


def test_ejecutar_count_proyectos(usuario_factory):
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto

    from lib.kpi_dsl import ejecutar

    cli = Cliente.objects.create(razon_social="X")
    Proyecto.objects.create(cliente=cli, nombre="A", estado="en_proceso_diseno")
    Proyecto.objects.create(cliente=cli, nombre="B", estado="esperando_respuesta")

    res = ejecutar({"entidad": "proyecto"})
    assert res["valor"] == 2


def test_ejecutar_filtro_in_funciona():
    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto

    from lib.kpi_dsl import ejecutar

    cli = Cliente.objects.create(razon_social="X")
    Proyecto.objects.create(cliente=cli, nombre="A", estado="en_proceso_diseno")
    Proyecto.objects.create(cliente=cli, nombre="B", estado="esperando_respuesta")
    Proyecto.objects.create(cliente=cli, nombre="C", estado="entregado")

    res = ejecutar({
        "entidad": "proyecto",
        "filtros": [{"campo": "estado", "op": "in", "valor": ["en_proceso_diseno", "esperando_respuesta"]}],
    })
    assert res["valor"] == 2


def test_ejecutar_sum_egresos(usuario_factory):
    from datetime import date

    from apps.tesoreria.models import CentroDeCosto, Egreso

    from lib.kpi_dsl import ejecutar
    u = usuario_factory(rol="dueno")
    cc = CentroDeCosto.objects.create(slug="x", nombre="X")
    Egreso.objects.create(monto=100, descripcion="a", centro_de_costo=cc, creado_por=u, fecha=date(2026, 5, 1))
    Egreso.objects.create(monto=200, descripcion="b", centro_de_costo=cc, creado_por=u, fecha=date(2026, 5, 1))

    res = ejecutar({"entidad": "egreso", "agregacion": "sum", "campo": "monto"})
    assert res["valor"] == 300.0


def test_ejecutar_alcance_mio(usuario_factory):
    from apps.recados.models import Recado

    from lib.kpi_dsl import ejecutar
    u1 = usuario_factory(rol="dueno", email="a@a.com")
    u2 = usuario_factory(rol="dueno", email="b@a.com")
    Recado.objects.create(autor=u1, cuerpo="m1")
    Recado.objects.create(autor=u1, cuerpo="m2")
    Recado.objects.create(autor=u2, cuerpo="m3")

    res = ejecutar({"entidad": "recado", "alcance_usuario": "mio"}, usuario=u1)
    assert res["valor"] == 2


def test_ejecutor_ventana_tiempo_filtra():
    """este_mes filtra por fecha del campo de fecha de la entidad."""
    from datetime import date

    from apps.la_cartera.models import Cliente
    from apps.los_proyectos.models import Proyecto

    from lib.kpi_dsl import ejecutar

    cli = Cliente.objects.create(razon_social="X")
    p = Proyecto.objects.create(cliente=cli, nombre="A", estado="en_proceso_diseno")
    # Forzar fecha vieja para que ventana 'este_mes' lo excluya.
    Proyecto.objects.filter(pk=p.pk).update(creado_en=date(2020, 1, 1))

    # 'siempre' lo cuenta.
    assert ejecutar({"entidad": "proyecto", "ventana_tiempo": "siempre"})["valor"] == 1
    # 'este_mes' no lo cuenta.
    assert ejecutar({"entidad": "proyecto", "ventana_tiempo": "este_mes"})["valor"] == 0
