"""Cada estado de cotización declara qué significa para el negocio (su fase).

Escrita a mano: makemigrations agrega AlterField espurios de BigAutoField (§14).

La data migration reparte las fases de los estados que ya existen. Los que
sembró el sistema se conocen por slug; los que agregó el despacho a mano se
deducen de su nombre, y lo que no se reconoce queda como "armada" — que es lo
prudente: no lo cuenta ni como ganado ni como perdido, y se corrige de un clic
en Gerencia.
"""

from __future__ import annotations

import unicodedata

from django.db import migrations, models

SEED_POR_SLUG = {
    "generada": "armada",
    "enviada": "enviada",
    "aprobada": "ganada",
    "pagada": "ganada",
    "anticipo": "ganada",
    "rechazada": "perdida",
    "anulada": "perdida",
}

PISTAS = (
    ("perdida", ("rechaz", "perdid", "anul", "cancel", "declin", "desist", "no va")),
    ("ganada", ("pagad", "aprobad", "ganad", "acept", "autoriz", "anticipo",
                "cerrad", "adjudic", "firmad")),
    ("enviada", ("enviad", "mandad", "present", "revision", "espera", "seguim")),
)


def _plano(texto: str) -> str:
    """minúsculas y sin acentos, para que 'Revisión' case con 'revision'."""
    limpio = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in limpio if not unicodedata.combining(c)).lower()


def deducir_fase(slug: str, label: str) -> str:
    conocido = SEED_POR_SLUG.get(_plano(slug))
    if conocido:
        return conocido
    texto = f"{_plano(slug)} {_plano(label)}"
    for fase, pistas in PISTAS:
        if any(p in texto for p in pistas):
            return fase
    return "armada"


def repartir_fases(apps, schema_editor):
    Estado = apps.get_model("cotizaciones", "EstadoCotizacion")
    for estado in Estado.objects.all():
        fase = deducir_fase(estado.slug, estado.label)
        if estado.fase != fase:
            estado.fase = fase
            estado.save(update_fields=["fase"])

    # El flujo necesita un destino para "ya se la mandé al cliente". Si el
    # despacho no tiene ningún paso activo que signifique eso (Learning Center
    # había apagado "Enviada"), se vuelve a prender el del sistema. Es un clic
    # revertirlo en Gerencia, pero sin él no habría dónde poner la cotización
    # al enviarla y no se podría medir el silencio del cliente.
    if not Estado.objects.filter(fase="enviada", activo=True).exists():
        enviada = Estado.objects.filter(slug="enviada").first()
        if enviada:
            enviada.activo = True
            enviada.fase = "enviada"
            enviada.save(update_fields=["activo", "fase"])
        else:
            Estado.objects.create(
                slug="enviada", label="Enviada", fase="enviada",
                descripcion="El cliente ya la tiene; esperamos respuesta.",
                color="#465fff", orden=20, terminal=False, activo=True,
                sistema=True,
            )


def atras(apps, schema_editor):
    """Nada que deshacer: el campo se va con el AddField."""


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0018_item_informativo"),
    ]

    operations = [
        migrations.AddField(
            model_name="estadocotizacion",
            name="fase",
            field=models.CharField(
                choices=[
                    ("armada", "Armada — todavía no se le manda al cliente"),
                    ("enviada", "Enviada — el cliente la tiene, esperamos respuesta"),
                    ("ganada", "Ganada — el cliente dijo que sí"),
                    ("perdida", "Perdida — ya no va"),
                ],
                db_index=True,
                default="armada",
                help_text=(
                    "Qué significa este paso para el negocio. De aquí salen la "
                    "conversión y el conteo de oportunidades perdidas."
                ),
                max_length=12,
            ),
        ),
        migrations.RunPython(repartir_fases, atras),
    ]
