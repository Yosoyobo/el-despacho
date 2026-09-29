"""DSL de KPIs v1 → v2: toda definición que validaba antes sigue validando,
se normaliza IGUAL (es lo que se guarda en `KPICustom.definicion_json`) y da
el MISMO número.

Estas pruebas se escribieron contra el motor v1 ANTES de tocarlo: los números
esperados salieron de él. Si el v2 los cambia, rompe los KPIs de producción.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def datos(usuario_factory, cliente_factory):
    """Un despacho chico con fechas relativas a hoy (las ventanas son de hoy)."""
    from apps.el_pizarron.models import Tarea
    from apps.los_proyectos.models import Proyecto, ProyectoAsignacion
    from apps.recados.models import Recado
    from apps.tesoreria.models import CentroDeCosto, Egreso, Ingreso
    from buzon.models import MensajeBuzon

    hoy = timezone.localdate()
    ahora = timezone.now()
    ana = usuario_factory(rol="dueno", email="ana@lc.mx")
    beto = usuario_factory(rol="disenador", email="beto@lc.mx")
    cli = cliente_factory(razon_social="Heladería")
    cliente_factory(razon_social="Cafetería", activo=False, estado="inactivo")

    p1 = Proyecto.objects.create(cliente=cli, nombre="A", estado="en_proceso_diseno",
                                 monto_cotizado=Decimal("1000.00"))
    p2 = Proyecto.objects.create(cliente=cli, nombre="B", estado="en_proceso_produccion",
                                 monto_cotizado=Decimal("2500.50"))
    p3 = Proyecto.objects.create(cliente=cli, nombre="C", estado="entregado",
                                 monto_cotizado=None, archivado=True)
    Proyecto.objects.filter(pk=p3.pk).update(creado_en=ahora - timedelta(days=400))
    ProyectoAsignacion.objects.create(proyecto=p1, usuario=beto)
    ProyectoAsignacion.objects.create(proyecto=p2, usuario=beto)
    ProyectoAsignacion.objects.create(proyecto=p2, usuario=ana)

    for i, (prio, autor) in enumerate([("alta", ana), ("alta", beto), ("baja", ana), ("media", ana)]):
        Tarea.objects.create(proyecto=p1, titulo=f"t{i}", prioridad=prio, creado_por=autor,
                             asignada_a=beto, fecha_compromiso=hoy)

    cc = CentroDeCosto.objects.create(slug="op", nombre="Operación")
    egresos = [
        (Decimal("120.00"), "Uber al cliente", "pagado", hoy, False),
        (Decimal("80.00"), "UBER aeropuerto", "pendiente", hoy - timedelta(days=3), False),
        (Decimal("999.00"), "Papelería", "pagado", hoy - timedelta(days=20), False),
        (Decimal("50.00"), "Uber anulado", "pagado", hoy, True),
        (Decimal("5000.00"), "Renta vieja", "pagado", hoy - timedelta(days=500), False),
    ]
    for monto, desc, estado, fecha, anulado in egresos:
        Egreso.objects.create(monto=monto, descripcion=desc, estado_pago=estado, fecha=fecha,
                              anulado=anulado, centro_de_costo=cc, creado_por=ana)
    for monto, fecha, autor in [(Decimal("300.00"), hoy, ana), (Decimal("700.00"), hoy, beto),
                                (Decimal("100.00"), hoy - timedelta(days=45), ana)]:
        Ingreso.objects.create(monto=monto, descripcion="pago", fecha=fecha, cliente=cli,
                               creado_por=autor)

    Recado.objects.create(autor=ana, cuerpo="uno")
    Recado.objects.create(autor=ana, cuerpo="dos")
    Recado.objects.create(autor=beto, cuerpo="tres")
    MensajeBuzon.objects.create(autor=ana, tipo="problema", asunto="x", cuerpo="x")
    MensajeBuzon.objects.create(autor=beto, tipo="problema", asunto="y", cuerpo="y")
    MensajeBuzon.objects.create(autor=beto, tipo="idea", asunto="z", cuerpo="z")
    return {"ana": ana, "beto": beto, "hoy": hoy}


# (definición v1, quién la ve, número que daba el v1)
CASOS = [
    ({"entidad": "proyecto"}, None, 3),
    ({"entidad": "proyecto", "filtros": [{"campo": "archivado", "op": "eq", "valor": False}]}, None, 2),
    ({"entidad": "proyecto", "filtros": [{"campo": "estado", "op": "in",
                                          "valor": ["en_proceso_diseno", "entregado"]}]}, None, 2),
    ({"entidad": "proyecto", "ventana_tiempo": "este_ano"}, None, 2),
    ({"entidad": "proyecto", "alcance_usuario": "mio"}, "beto", 2),
    ({"entidad": "proyecto", "alcance_usuario": "mio"}, "ana", 1),
    ({"entidad": "proyecto", "agregacion": "sum", "campo": "monto_cotizado"}, None, 3500.5),
    ({"entidad": "proyecto", "agregacion": "avg", "campo": "monto_cotizado"}, None, 1750.25),
    ({"entidad": "proyecto", "agregacion": "max", "campo": "monto_cotizado",
      "alcance_usuario": "mio"}, "ana", 2500.5),
    ({"entidad": "tarea", "filtros": [{"campo": "prioridad", "op": "eq", "valor": "alta"}]}, None, 2),
    ({"entidad": "tarea", "alcance_usuario": "mio"}, "ana", 3),
    ({"entidad": "tarea", "alcance_usuario": "mio",
      "filtros": [{"campo": "prioridad", "op": "in", "valor": ["alta", "media"]}]}, "ana", 2),
    ({"entidad": "cliente", "filtros": [{"campo": "activo", "op": "eq", "valor": True}]}, None, 1),
    ({"entidad": "cliente", "filtros": [{"campo": "estado", "op": "in",
                                         "valor": ["inactivo"]}]}, None, 1),
    ({"entidad": "egreso", "agregacion": "sum", "campo": "monto"}, None, 6249.0),
    ({"entidad": "egreso", "agregacion": "sum", "campo": "monto", "ventana_tiempo": "ultimos_30d",
      "filtros": [{"campo": "anulado", "op": "eq", "valor": False}]}, None, 1199.0),
    ({"entidad": "egreso", "agregacion": "sum", "campo": "monto", "ventana_tiempo": "ultimos_7d",
      "filtros": [{"campo": "descripcion", "op": "contiene", "valor": "uber"},
                  {"campo": "anulado", "op": "eq", "valor": False}]}, None, 200.0),
    ({"entidad": "egreso", "filtros": [{"campo": "estado_pago", "op": "in",
                                        "valor": ["pendiente"]}]}, None, 1),
    ({"entidad": "egreso", "agregacion": "min", "campo": "monto", "alcance_usuario": "mio"}, "ana", 50.0),
    ({"entidad": "egreso", "filtros": [{"campo": "proveedor_nombre", "op": "eq", "valor": ""}]}, None, 5),
    ({"entidad": "ingreso", "agregacion": "sum", "campo": "monto", "ventana_tiempo": "ultimos_7d"}, None, 1000.0),
    ({"entidad": "ingreso", "agregacion": "avg", "campo": "monto", "alcance_usuario": "mio"}, "ana", 200.0),
    ({"entidad": "ingreso", "agregacion": "sum", "campo": "monto",
      "filtros": [{"campo": "descripcion", "op": "contiene", "valor": "nada"}]}, None, 0),
    ({"entidad": "recado"}, None, 3),
    ({"entidad": "recado", "alcance_usuario": "mio"}, "beto", 1),
    ({"entidad": "buzon_mensaje", "filtros": [{"campo": "tipo", "op": "eq", "valor": "problema"}]}, None, 2),
    ({"entidad": "buzon_mensaje", "alcance_usuario": "mio"}, "beto", 2),
]


@pytest.mark.parametrize(("definicion", "quien", "esperado"), CASOS)
def test_v1_da_el_mismo_numero(datos, definicion, quien, esperado):
    from lib.kpi_dsl import ejecutar

    usuario = datos[quien] if quien else None
    res = ejecutar(definicion, usuario=usuario)
    assert res["valor"] == esperado
    assert isinstance(res["valor"], type(esperado))
    assert res["nota"] == ""


@pytest.mark.parametrize(("definicion", "_q", "_e"), CASOS)
def test_v1_se_normaliza_igual(definicion, _q, _e):
    """Lo que se guarda en `definicion_json` no cambia de forma: las mismas
    seis llaves, sin llaves v2 cuando la definición no las usa."""
    from lib.kpi_dsl import validar

    n = validar(definicion)
    assert set(n) == {"entidad", "agregacion", "campo", "filtros", "ventana_tiempo", "alcance_usuario"}
    assert n["filtros"] == [
        {"campo": f["campo"], "op": f.get("op", "eq"), "valor": f["valor"]}
        for f in definicion.get("filtros", [])
    ]
    assert validar(n) == n  # idempotente


def test_v1_link_de_la_entidad(datos):
    from lib.kpi_dsl import ejecutar
    assert ejecutar({"entidad": "egreso"})["link"] == "/tesoreria/egresos/"
    assert ejecutar({"entidad": "tarea"})["link"] == "/tareas/"
