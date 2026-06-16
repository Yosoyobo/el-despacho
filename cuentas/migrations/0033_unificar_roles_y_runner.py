"""S-Roles-V2 (Oscar): unifica el sistema de roles + Runner opt-in.

Dos cambios coordinados, idempotentes:

1. **Runner opt-in.** `(runner, recibir)` deja de ser default de todos. Se
   quita de los permisos JSON de los roles sistema, se borran las filas
   PermisoUsuario(runner) sembradas por 0032, y se asegura un rol "Runner"
   (sistema) que es el único que concede runner. Resultado: solo quien tenga el
   rol Runner aparece en el dropdown de asignación.

2. **Anti-lockout de la unificación de roles.** Tras eliminar el dropdown de
   "rol primario" en el Directorio, los roles se asignan solo por los checkboxes
   (roles_extra). Para que NADIE pierda acceso, a cada usuario se le agrega como
   rol_extra el rol sistema que corresponde a su `rol` primario actual
   (super_admin/dueno/contador/disenador). Así su super_admin queda pre-marcado y
   sus permisos persisten por el rol. `miembro` no agrega nada.
"""

from __future__ import annotations

from django.db import migrations

_ROLES_PRIMARIOS = ("super_admin", "dueno", "contador", "disenador")


def aplicar(apps, schema_editor):
    Rol = apps.get_model("cuentas", "Rol")
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")

    # 1a. Quita "runner" del JSON de TODOS los roles (ningún rol lo concede salvo "Runner").
    for rol in Rol.objects.all():
        permisos = rol.permisos or {}
        if "runner" in permisos and rol.nombre != "Runner":
            permisos.pop("runner", None)
            rol.permisos = permisos
            rol.save(update_fields=["permisos"])

    # 1b. Asegura el rol "Runner" (único que concede runner.recibir).
    runner_rol, creado = Rol.objects.get_or_create(
        nombre="Runner",
        defaults={
            "descripcion": "Reparte entregas/recolecciones. Quien lo tenga aparece para asignación de runner.",
            "permisos": {"runner": ["recibir"]},
            "sistema": True,
        },
    )
    if not creado:
        permisos = runner_rol.permisos or {}
        acciones = set(permisos.get("runner") or [])
        acciones.add("recibir")
        permisos["runner"] = sorted(acciones)
        runner_rol.permisos = permisos
        if not runner_rol.sistema:
            runner_rol.sistema = True
        runner_rol.save(update_fields=["permisos", "sistema"])

    # 1c. Borra las filas PermisoUsuario(runner) sembradas por 0032 (ya no son default).
    PermisoUsuario.objects.filter(modulo="runner").delete()

    # 2. Anti-lockout: cada usuario conserva su rol actual como rol_extra.
    roles_por_nombre = {r.nombre: r for r in Rol.objects.filter(nombre__in=_ROLES_PRIMARIOS)}
    for u in Usuario.objects.all().order_by("pk"):
        rol = roles_por_nombre.get(u.rol)
        if rol is not None:
            u.roles_extra.add(rol)


def revertir(apps, schema_editor):
    # No se re-siembra PermisoUsuario(runner) ni se re-quitan roles_extra:
    # el estado destino es el deseado. Reversa = no-op seguro.
    pass


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0032_seed_permisos_runner")]
    operations = [migrations.RunPython(aplicar, revertir)]
