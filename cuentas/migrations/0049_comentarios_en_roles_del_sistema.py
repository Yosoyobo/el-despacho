"""Los comentarios vuelven al JSON de los roles del sistema — que sea regla, no foto.

Decisión de Oscar (2026-09-28): Alex (Director sobre primario `miembro`) lee los
comentarios «por rol asignado». La 0048 lo arregló por persona para quien ya
tenía el rol; esta migración lo vuelve REGLA: el rol mismo trae las acciones,
así que quien reciba mañana «Director» (clave `dueno`) lee igual que Alex, y
«ver como rol» enseña lo mismo.

Sólo el JSON de los cuatro roles del sistema (por `clave`); los personalizados
no se tocan (configuración de Oscar). Queda igual que la regla vieja de
comentarios, ahora leída por rol asignado:

  · `pizarron.ver_comentarios` — super_admin, dueño, contador, diseñador.
  · `pizarron.ver_internos`    — super_admin, dueño, contador (el diseñador lee
    los públicos y sus propios internos, no los ajenos: se le quita si la trae).

Es lo que la 0047 había sacado (paso 2) porque la regla de entonces leía el rol
PRIMARIO. Con la foto de producción del 2026-09-28 nadie cambia respecto a lo
que dejó la 0048: el único que tiene asignado un rol del sistema sin tenerlo de
primario es Alex, y ya tiene sus filas encendidas.

Sólo datos (Bug I). Idempotente. Reversa: no-op.
"""

from __future__ import annotations

from django.db import migrations

# clave del rol → (¿ver_comentarios?, ¿ver_internos?)
REGLA = {
    "super_admin": (True, True),
    "dueno": (True, True),
    "contador": (True, True),
    "disenador": (True, False),
}


def planear(roles):
    """Plan puro. `roles`: [{"id", "clave", "permisos"}] → {rol_id: permisos}
    sólo de los que cambian."""
    out = {}
    for rol in roles:
        if rol["clave"] not in REGLA:
            continue
        mapa = {m: sorted(a) for m, a in (rol["permisos"] or {}).items()}
        acciones = set(mapa.get("pizarron") or [])
        for accion, debe in zip(("ver_comentarios", "ver_internos"), REGLA[rol["clave"]], strict=True):
            (acciones.add if debe else acciones.discard)(accion)
        nuevo = {**mapa}
        if acciones:
            nuevo["pizarron"] = sorted(acciones)
        else:
            nuevo.pop("pizarron", None)
        if nuevo != mapa:
            out[rol["id"]] = nuevo
    return out


def aplicar(apps, schema_editor):
    Rol = apps.get_model("cuentas", "Rol")
    roles = [{"id": r.pk, "clave": r.clave, "permisos": r.permisos or {}}
             for r in Rol.objects.all().order_by("pk")]
    nuevos = planear(roles)
    for rol in Rol.objects.filter(pk__in=list(nuevos)):
        rol.permisos = nuevos[rol.pk]
        rol.save(update_fields=["permisos"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0048_puertas_decididas")]
    operations = [migrations.RunPython(aplicar, noop)]
