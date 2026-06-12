"""S-LC-Feedback-V6 Bloque 1: EstadoTarea configurable + tipo/hora en Tarea +
'Atrasada' automática (derivada, no almacenada)."""

from datetime import date, time, timedelta

import pytest
from django.core.exceptions import ValidationError

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


@pytest.fixture()
def proyecto(usuario_factory, cliente_factory):
    from apps.los_proyectos.models import Proyecto
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    return Proyecto.objects.create(nombre="Proyecto X", cliente=cli, creado_por=admin)


def _tarea(proyecto, **kwargs):
    from apps.el_pizarron.models import Tarea
    defaults = {"titulo": "T", "creado_por": proyecto.creado_por}
    defaults.update(kwargs)
    return Tarea.objects.create(proyecto=proyecto, **defaults)


def test_seed_estados_base():
    """La migración 0004 siembra pendiente/en_curso/completada; bloqueada NO."""
    from apps.el_pizarron.models import EstadoTarea
    slugs = set(EstadoTarea.objects.values_list("slug", flat=True))
    assert {"pendiente", "en_curso", "completada"} <= slugs
    assert "bloqueada" not in slugs
    assert "atrasada" not in slugs  # derivada, nunca almacenada
    assert EstadoTarea.objects.get(slug="completada").terminal is True


def test_color_hex_valido_e_invalido():
    from apps.el_pizarron.models import EstadoTarea
    e = EstadoTarea(slug="qa", label="QA", color="#ff00aa")
    e.full_clean()  # no levanta
    e2 = EstadoTarea(slug="qa2", label="QA2", color="rojo")
    with pytest.raises(ValidationError):
        e2.full_clean()


def test_atrasada_derivada_por_fecha_vencida(proyecto):
    t = _tarea(proyecto, fecha_compromiso=date.today() - timedelta(days=2))
    assert t.esta_atrasada is True
    assert t.get_estado_display() == "Pendiente"  # el estado NO muta


def test_terminal_excluye_atrasada(proyecto):
    t = _tarea(proyecto, estado="completada",
               fecha_compromiso=date.today() - timedelta(days=5))
    assert t.esta_atrasada is False


def test_sin_fecha_no_atrasada(proyecto):
    t = _tarea(proyecto, fecha_compromiso=None)
    assert t.esta_atrasada is False


def test_hora_cuenta_para_atrasada(proyecto):
    """Hoy con hora ya pasada → atrasada; hoy con hora futura → no."""
    t1 = _tarea(proyecto, fecha_compromiso=date.today(), hora=time(0, 1))
    assert t1.esta_atrasada is True
    t2 = _tarea(proyecto, fecha_compromiso=date.today(), hora=time(23, 59))
    assert t2.esta_atrasada is False


def test_alta_con_tipo_y_hora(client, usuario_factory, proyecto):
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    resp = client.post(
        f"/proyectos/{proyecto.pk}/tareas/nueva",
        {"titulo": "Entregar lonas", "descripcion": "", "estado": "pendiente",
         "prioridad": "media", "tipo": "entrega",
         "asignada_a": admin.pk,
         "fecha_compromiso": date.today().isoformat(), "hora": "14:30"},
        follow=True,
    )
    assert resp.status_code == 200
    from apps.el_pizarron.models import Tarea
    t = Tarea.objects.get(titulo="Entregar lonas")
    assert t.tipo == "entrega"
    assert t.hora == time(14, 30)


def test_form_estado_dinamico_excluye_inactivos(proyecto):
    from apps.el_pizarron.forms import TareaForm
    from apps.el_pizarron.models import EstadoTarea
    from apps.el_pizarron.models.estado_tarea import invalidar_mapa_estados_tarea
    EstadoTarea.objects.create(slug="oculto", label="Oculto", activo=False)
    invalidar_mapa_estados_tarea()
    form = TareaForm()
    slugs = {c[0] for c in form.fields["estado"].choices}
    assert "pendiente" in slugs
    assert "oculto" not in slugs


def test_estado_visible_filtros(proyecto):
    """Los filtros de template pintan 'Atrasada' en amarillo encima del estado."""
    from apps.el_pizarron.templatetags.tareas_extras import (
        COLOR_ATRASADA,
        color_estado_tarea_de,
        estado_visible_tarea,
    )
    t = _tarea(proyecto, fecha_compromiso=date.today() - timedelta(days=1))
    assert estado_visible_tarea(t) == "Atrasada"
    assert color_estado_tarea_de(t) == COLOR_ATRASADA
    t2 = _tarea(proyecto, estado="en_curso")
    assert estado_visible_tarea(t2) == "En curso"
