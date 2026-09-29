"""Revive la última llave de cada persona (decisión de Oscar, 2026-09-29).

Hasta hoy el enlace servía una sola vez y caducaba (20 min / 72 h); los clientes
guardaban el correo y al volver el botón ya no abría. Desde hoy la llave no
caduca ni se gasta y pide el correo al que se mandó. Para que los correos que YA
les llegaron vuelvan a servir, la llave más reciente de cada acceso activo queda
viva (sin caducidad) y las demás se anulan: antes también servía sólo la última.

Las de accesos revocados o de clientes archivados se anulan todas.

Sólo datos (§14 Bug I): el esquema está en 0004. Idempotente.
"""

from django.db import migrations
from django.utils import timezone


def revivir(apps, schema_editor):
    Enlace = apps.get_model("portal", "EnlaceAcceso")
    Acceso = apps.get_model("portal", "AccesoCliente")
    ahora = timezone.now()
    for acceso in Acceso.objects.select_related("cliente").all():
        vivo = acceso.activo and acceso.cliente.activo
        enlaces = Enlace.objects.filter(acceso=acceso).order_by("-creado_en", "-pk")
        ultimo = enlaces.first() if vivo else None
        if ultimo is not None and ultimo.anulado_en is None:
            Enlace.objects.filter(pk=ultimo.pk).update(expira_en=None)
        enlaces.exclude(pk=getattr(ultimo, "pk", None)).filter(anulado_en__isnull=True).update(anulado_en=ahora)


class Migration(migrations.Migration):
    dependencies = [("portal", "0004_llave_fija_y_documentos")]
    operations = [migrations.RunPython(revivir, migrations.RunPython.noop)]
