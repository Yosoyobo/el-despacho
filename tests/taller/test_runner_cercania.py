"""S-Chalan-Barrido — El Runner por cercanía geográfica.

La auto-asignación elige al runner MÁS CERCANO al destino (si se conoce la
ubicación) en vez del menos cargado. Las coordenadas se reusan de las visitas/
jornadas que ya registra El Checador (cero costo, sin geocodificación de paga).
Si no hay destino o ninguna posición de runner es conocida, cae a menos cargado.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _tarea(proyecto, **kw):
    from apps.el_pizarron.models import Tarea
    defaults = dict(titulo="Entregar lona", tipo="entrega", estado="pendiente")
    defaults.update(kw)
    return Tarea.objects.create(proyecto=proyecto, **defaults)


def _visita(usuario, lat, lng, *, cliente=None):
    from apps.checador.models import Visita
    return Visita.objects.create(
        usuario=usuario, lat=lat, lng=lng, cliente=cliente,
        tipo="cliente" if cliente else "otro",
        registrado_en=timezone.now(),
    )


def _hacer_runner(*usuarios):
    """S-Roles-V2: runner es opt-in vía el rol "Runner" (sembrado en cuentas/0033)."""
    from cuentas.models.rol import Rol
    r = Rol.objects.get(nombre="Runner")
    for u in usuarios:
        u.roles_extra.add(r)


def test_ubicacion_actual_de_usa_ultima_visita(usuario_factory):
    from apps.el_pizarron import runners
    u = usuario_factory(rol="disenador", email="pos@lc.mx")
    _visita(u, 19.41, -99.17)
    pos = runners.ubicacion_actual_de(u)
    assert pos == (19.41, -99.17)


def test_destino_hereda_de_visita_al_cliente(proyecto_factory):
    from apps.el_pizarron import runners
    p = proyecto_factory(estado="en_proceso_diseno")
    # alguien visitó antes al cliente del proyecto y quedó geolocalizado
    from cuentas.models.usuario import Usuario
    quien = Usuario.objects.create(email="visitante@lc.mx", nombre_completo="V", rol="disenador")
    _visita(quien, 19.40, -99.16, cliente=p.cliente)
    t = _tarea(p)
    assert runners.ubicacion_destino_de_tarea(t) == (19.40, -99.16)


def test_destino_pin_explicito_gana(proyecto_factory):
    from apps.el_pizarron import runners
    p = proyecto_factory(estado="en_proceso_diseno")
    t = _tarea(p, destino_lat=20.0, destino_lng=-100.0)
    # aunque hubiera visita al cliente, el pin explícito manda
    from cuentas.models.usuario import Usuario
    quien = Usuario.objects.create(email="v2@lc.mx", nombre_completo="V", rol="disenador")
    _visita(quien, 19.40, -99.16, cliente=p.cliente)
    assert runners.ubicacion_destino_de_tarea(t) == (20.0, -100.0)


def test_auto_asigna_mas_cercano(proyecto_factory, usuario_factory):
    from apps.el_pizarron import runners
    p = proyecto_factory(estado="en_proceso_diseno")
    lejos = usuario_factory(rol="disenador", email="lejos@lc.mx")
    cerca = usuario_factory(rol="disenador", email="cerca@lc.mx")
    _hacer_runner(lejos, cerca)
    _visita(lejos, 19.50, -99.30)   # ~16 km del destino
    _visita(cerca, 19.405, -99.165)  # ~ pocos cientos de metros
    t = _tarea(p, destino_lat=19.40, destino_lng=-99.16)
    elegido = runners.asignar_runner_auto(t)
    assert elegido == cerca
    t.refresh_from_db()
    assert t.runner_id == cerca.pk
    assert t.runner_auto is True


def test_auto_cae_a_menos_cargado_sin_posiciones(proyecto_factory, usuario_factory):
    """Destino conocido pero ningún runner tiene posición → menos cargado."""
    from apps.el_pizarron import runners
    p = proyecto_factory(estado="en_proceso_diseno")
    a = usuario_factory(rol="disenador", email="na@lc.mx")
    b = usuario_factory(rol="disenador", email="nb@lc.mx")  # otro candidato con 0 carga
    _hacer_runner(a, b)
    _tarea(p, runner=a)  # a ya carga 1
    t = _tarea(p, destino_lat=19.40, destino_lng=-99.16)
    elegido = runners.asignar_runner_auto(t)
    assert elegido is not None
    assert elegido != a  # a carga 1; cayó al menos cargado (otro con 0)
    assert runners.pendientes_runner(elegido) <= 1  # solo la recién asignada
