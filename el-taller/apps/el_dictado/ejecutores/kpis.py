"""Ejecutor de metas de KPI por chat (S-KPIs-V2, 2026-09-29).

«Ponle meta de 250 mil a los ingresos del mes» hace lo mismo que La Gerencia →
Ajustes → KPIs → Metas, con las mismas reglas: el KPI tiene que admitir ese
tipo de meta, el valor tiene que ser mayor que cero y el periodo sale del KPI.
El catálogo, los tableros y los umbrales NO se tocan por chat.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from . import _gate, registrar
from .avanzados import _exigir
from .basicos import _resolver_cliente


@registrar("fijar_meta_kpi")
def fijar_meta_kpi(accion, usuario, contexto=None):
    """Payload: kpi_slug, valor, ambito? (despacho|persona|cliente),
    usuario_email?, cliente_slug?, quitar? (bool)."""
    from apps.taller_home.kpis import kpi_por_slug
    from apps.taller_home.metas import periodo_de
    from apps.taller_home.models import MetaKPI

    from cuentas.models.usuario import Usuario

    _gate(usuario, "puede_configurar_kpis", "poner metas de KPIs")
    payload = accion.payload or {}
    kpi = kpi_por_slug((payload.get("kpi_slug") or "").strip())
    _exigir(kpi is not None, "No encontré ese KPI (usa listar_kpis para ver los slugs).")
    ambito = (payload.get("ambito") or "despacho").strip()
    _exigir(ambito in ("despacho", "persona", "cliente"), "El ámbito es despacho, persona o cliente.")
    _exigir(kpi.admite_meta(ambito), f"«{kpi.titulo}» no admite una meta de ese tipo.")

    persona = cliente = None
    if ambito == "persona":
        persona = Usuario.objects.filter(
            email__iexact=(payload.get("usuario_email") or "").strip(), is_active=True,
        ).first()
        _exigir(persona is not None, "No encontré a esa persona.")
    elif ambito == "cliente":
        cliente = _resolver_cliente((payload.get("cliente_slug") or "").lower(), contexto)

    filtro = {"kpi_slug": kpi.slug, "ambito": ambito, "usuario": persona, "cliente": cliente}
    if payload.get("quitar"):
        borradas, _ = MetaKPI.objects.filter(**filtro).delete()
        _exigir(borradas > 0, "Ese KPI no tenía meta que quitar.")
        accion.entidad_tipo = "meta_kpi"
        return

    try:
        valor = Decimal(str(payload.get("valor")).replace(",", "").replace("$", "").strip())
    except (InvalidOperation, ValueError):
        valor = None
    _exigir(valor is not None and valor > 0, "La meta tiene que ser un número mayor que cero.")
    meta, _ = MetaKPI.objects.update_or_create(
        **filtro,
        defaults={"valor": valor, "periodo": periodo_de(kpi), "activa": True,
                  "actualizado_por": usuario, "avisado_periodo": ""},
    )
    accion.entidad_tipo = "meta_kpi"
    accion.entidad_id = meta.pk
