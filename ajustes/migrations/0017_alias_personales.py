"""El alias puede tener dueño: se le agrega la columna.

**Esta migración sólo toca el ESQUEMA. La siembra de los 12 alias vive en la
`0018`, y están separadas a propósito.**

Por qué: PostgreSQL guarda la creación de índices de una migración para el
final de su transacción. Si en la MISMA migración se agrega una llave foránea
(que trae índice) y además se insertan filas, cuando toca crear el índice ya hay
eventos de disparador pendientes por esas inserciones y Postgres se niega:

    cannot CREATE INDEX "ajustes_alias_remitente" because it has pending trigger events

Y no se ve en las pruebas, porque corren sobre SQLite, que no tiene esa
restricción: sólo aparece al desplegar. Lo cazó el smoke test del stack en
Docker (§13), que es justo para lo que existe. Regla: **una migración cambia el
esquema o mueve datos, no las dos cosas sobre la misma tabla.**
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ajustes', '0016_alias_remitente'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='aliasremitente',
            name='usuario',
            field=models.ForeignKey(blank=True, help_text='Si lo llenas, el alias es de esa persona y nadie más puede enviar desde él.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='alias_propios', to=settings.AUTH_USER_MODEL),
        ),
    ]
