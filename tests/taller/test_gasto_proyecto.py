"""Fase 2 (LC 2026-07) — Registrar Gasto desde proyecto.

Cubre: métodos curados (sin cheque, con efectivo personal), coerción defensiva
a «Por reembolsar» cuando el método es personal, y el prefill del form de egreso
desde un proyecto (líder → solicitó, centro insumos-de-proyecto).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.taller]


def _proveedor():
    from apps.el_catalogo.models import Proveedor
    return Proveedor.objects.create(razon_social="Insumos SA", activo=True)


def _centro():
    from apps.tesoreria.models import CentroDeCosto
    return CentroDeCosto.objects.filter(activo=True).first() or CentroDeCosto.objects.create(
        nombre="Insumos de proyecto", slug="insumos-de-proyecto", naturaleza="proyecto",
    )


def _datos(prov, centro, *, metodo, estado):
    return {
        "fecha": "2026-07-08", "subtotal": "100.00", "moneda": "MXN",
        "descripcion": "Vinil", "proveedor": prov.pk, "centro_de_costo": centro.pk,
        "estado_pago": estado, "metodo": metodo,
    }


def test_metodos_curados_sin_cheque():
    from apps.tesoreria.forms import EgresoForm
    form = EgresoForm()
    valores = [v for v, _ in form.fields["metodo"].choices]
    assert "cheque" not in valores
    assert "efectivo_personal" in valores
    assert "tarjeta_empresa" in valores
    assert valores[0] == "tarjeta_empresa"  # default primero


@pytest.mark.parametrize("metodo", ["tarjeta_personal", "efectivo_personal"])
def test_metodo_personal_fuerza_por_reembolsar(metodo):
    from apps.tesoreria.forms import EgresoForm
    prov, centro = _proveedor(), _centro()
    form = EgresoForm(data=_datos(prov, centro, metodo=metodo, estado="pagado"))
    assert form.is_valid(), form.errors
    assert form.cleaned_data["estado_pago"] == "por_reembolsar"


def test_metodo_empresa_respeta_pagado():
    from apps.tesoreria.forms import EgresoForm
    prov, centro = _proveedor(), _centro()
    form = EgresoForm(data=_datos(prov, centro, metodo="tarjeta_empresa", estado="pagado"))
    assert form.is_valid(), form.errors
    assert form.cleaned_data["estado_pago"] == "pagado"


def test_prefill_desde_proyecto(client, cliente_factory, usuario_factory):
    from apps.los_proyectos.models import Proyecto, ProyectoAsignacion
    autor = usuario_factory(rol="super_admin")
    lider = usuario_factory(rol="disenador")
    client.force_login(autor)
    cli = cliente_factory(creado_por=autor)
    proy = Proyecto.objects.create(nombre="Lonas", cliente=cli, creado_por=autor)
    ProyectoAsignacion.objects.create(proyecto=proy, usuario=lider, rol_en_proyecto="lider")
    resp = client.get(f"/tesoreria/egresos/nuevo/?proyecto={proy.pk}")
    assert resp.status_code == 200
    assert resp.context["gasto_proyecto"] is True
    form = resp.context["form"]
    assert str(form["proyecto"].value()) == str(proy.pk)
    assert str(form["solicitado_por"].value()) == str(lider.pk)
