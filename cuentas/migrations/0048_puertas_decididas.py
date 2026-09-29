"""Las puertas que Oscar decidió el 2026-09-28 — sobre los DATOS.

Sólo datos, sin esquema (Bug I). Idempotente. Reversa: no-op.

**Comentarios: quien tiene por `roles_extra` un rol del sistema los lee como
ese rol.** La regla vieja de comentarios (hasta 2026.09.04) leía el rol PRIMARIO
(`Usuario.rol`), no los roles asignados, y la 0047 lo conservó «como hoy»:
`pizarron.ver_comentarios` / `ver_internos` sólo se sembraron por rol primario.
Así, un «Director» (clave `dueno`) sobre primario `miembro` no leía ningún
comentario. Decisión de Oscar: que los lea.

Regla general (no por pk ni por correo), una por acción:

  · `ver_comentarios` — la regla vieja se la daba a los cuatro roles del
    sistema (super_admin, dueño, contador, diseñador). Quien NO tiene uno de
    ellos de primario pero SÍ asignado recibe la fila encendida.
  · `ver_internos` — la regla vieja se la daba a super_admin, dueño y contador
    (leen los internos ajenos; el diseñador sólo los suyos). Mismo criterio.

`ver_internos` también, y no sólo `ver_comentarios`, porque «leer como el rol
que tiene» es leer como dueño: con sólo `ver_comentarios` el Director vería los
públicos y sus propios internos, menos que cualquier dueño. Además el rol
«Director» de producción traía `pizarron.ver_internos` en su JSON (Oscar se lo
había puesto); la 0047 lo quitó —y apagó la fila de la persona— sólo porque
entonces nadie leía esa acción.

Se ENCIENDE aunque haya una fila apagada: la grilla de El Directorio escribe
una fila por cada acción del catálogo al guardarse, así que una fila apagada no
distingue «lo quitó Oscar» de «nadie lo marcó». La decisión de Oscar es
explícita, así que gana.

Con la foto de producción del 2026-09-28 sólo toca al usuario 4 (Director sobre
`miembro`): `ver_comentarios` y `ver_internos` encendidas.
`tests/test_puertas_decididas.py` fija el antes/después por persona.

**Ojo con el nombre del campo**: en `PermisoUsuario` se llama `permiso`, NO
`accion` (0046 lo documenta).
"""

from __future__ import annotations

from django.db import migrations

ROLES_SISTEMA = ("super_admin", "dueno", "contador", "disenador")
_R_FIN = frozenset({"super_admin", "dueno", "contador"})
_R_TODOS = frozenset(ROLES_SISTEMA)

# (modulo, permiso) → roles a los que la regla vieja se lo daba.
COMENTARIOS = {
    ("pizarron", "ver_comentarios"): _R_TODOS,
    ("pizarron", "ver_internos"): _R_FIN,
}


def planear_comentarios(usuarios, roles, filas):
    """Plan puro (sin base) — lo usan la migración y su prueba.

    `usuarios`: [{"id", "rol", "roles": [rol_id, …]}]
    `roles`:    [{"id", "clave"}]
    `filas`:    {(usuario_id, modulo, permiso): activo}

    Devuelve [(usuario_id, modulo, permiso, True)] a escribir.
    """
    claves = {r["id"]: r["clave"] for r in roles}
    out = []
    for u in usuarios:
        primario = u["rol"] or ""
        asignados = {claves[r] for r in u["roles"] if r in claves}
        for (modulo, permiso), conjunto in COMENTARIOS.items():
            if primario in conjunto or not (asignados & conjunto):
                continue
            if filas.get((u["id"], modulo, permiso)) is not True:
                out.append((u["id"], modulo, permiso, True))
    return out


def aplicar(apps, schema_editor):
    Rol = apps.get_model("cuentas", "Rol")
    Usuario = apps.get_model("cuentas", "Usuario")
    PermisoUsuario = apps.get_model("cuentas", "PermisoUsuario")

    roles = [{"id": r.pk, "clave": r.clave} for r in Rol.objects.all().order_by("pk")]
    usuarios = [
        {"id": u.pk, "rol": u.rol,
         "roles": list(u.roles_extra.values_list("pk", flat=True))}
        for u in Usuario.objects.all().order_by("pk")
    ]
    filas = {
        (uid, m, p): activo
        for uid, m, p, activo in PermisoUsuario.objects.filter(modulo="pizarron")
        .values_list("usuario_id", "modulo", "permiso", "activo")
    }
    for uid, modulo, permiso, activo in planear_comentarios(usuarios, roles, filas):
        PermisoUsuario.objects.update_or_create(
            usuario_id=uid, modulo=modulo, permiso=permiso,
            defaults={"activo": activo},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0047_permisos_sin_rol_literal")]
    operations = [migrations.RunPython(aplicar, noop)]
