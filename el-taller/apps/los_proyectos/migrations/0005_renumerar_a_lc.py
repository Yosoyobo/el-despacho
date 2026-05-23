"""Renumera proyectos de PRY-NNNNNN a LC-NNNN en orden de creación.

Decisión S-LC-Feedback-V2: códigos correlativos legibles. Para el go-live
productivo, el management command `resetear_contador_proyectos` limpia
demos y reinicia en LC-0001.

La migración:
- Recorre proyectos en orden cronológico (pk asc) y reasigna codigo a
  LC-0001, LC-0002, ...
- Re-genera slug usando lib.slug.generar_slug_proyecto.
- Emite evento Portavoz `proyecto.codigo_renumerado` con {viejo, nuevo}
  para auditoría (sólo si Redis disponible; el evento no es crítico).
- Idempotente: si todos los proyectos ya están en formato LC-, no hace nada.
"""

from __future__ import annotations

from django.db import migrations


def _renumerar(apps, schema_editor):
    Proyecto = apps.get_model("proyectos", "Proyecto")
    # Si ya están todos en LC-, nada que hacer (idempotencia).
    pendientes = Proyecto.objects.exclude(codigo__startswith="LC-")
    if not pendientes.exists():
        return

    # Renumera TODOS los proyectos en orden de pk para tener un correlativo
    # consistente, no solo los que tenían PRY-.
    pks = list(Proyecto.objects.order_by("pk").values_list("pk", "codigo"))

    # Para evitar colisiones de unicidad intermedias, primero ponemos códigos
    # temporales y luego los definitivos.
    for i, (pk, _codigo) in enumerate(pks, start=1):
        Proyecto.objects.filter(pk=pk).update(
            codigo=f"__tmp_lc_{i}__",
            slug=f"__tmp_lc_{i}__",
        )

    cambios = []
    for i, (pk, codigo_viejo) in enumerate(pks, start=1):
        nuevo = f"LC-{i:04d}"
        Proyecto.objects.filter(pk=pk).update(codigo=nuevo, slug=nuevo.lower())
        cambios.append((pk, codigo_viejo, nuevo))

    # Best-effort: emite evento Portavoz si está disponible. NO levanta
    # si Redis está caído — la migración no debe abortar por eso.
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        for pk, viejo, nuevo in cambios:
            emitir(EventoPortavoz(
                tipo="proyecto.codigo_renumerado",
                actor_id=None, actor_email="migracion",
                payload={"proyecto_id": pk, "viejo": viejo, "nuevo": nuevo},
            ))
    except Exception:
        pass


def _reverse(apps, schema_editor):
    """Migración no reversible: PRY-xxxxxx originales no se preservan."""
    raise migrations.RunPython.noop


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0004_estados_lc_y_proyectoproducto"),
    ]

    operations = [
        migrations.RunPython(_renumerar, _reverse),
    ]
